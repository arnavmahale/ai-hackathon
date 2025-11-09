from __future__ import annotations
import asyncio
import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .github_client import fetch_file_content
from . import storage
from .schemas import AgentRunIngestRequest, AgentViolation

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "validate_code.py"
_running: set[str] = set()


def enqueue_scan(pr_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No running event loop; cannot enqueue scan for %s", pr_id)
        return
    loop.create_task(_run_scan_task(pr_id))


async def _run_scan_task(pr_id: str) -> None:
    if pr_id in _running:
        return
    _running.add(pr_id)
    try:
        await asyncio.to_thread(_run_scan_sync, pr_id)
    except Exception:  # pragma: no cover
        logger.exception("Agent runner failed for %s", pr_id)
    finally:
        _running.discard(pr_id)


def _run_scan_sync(pr_id: str) -> None:
    record = storage.load_pull_request_record(pr_id)
    if not record:
        logger.warning("No PR record found for %s", pr_id)
        return
    tasks_payload = storage.load_latest_tasks_payload()
    if not tasks_payload:
        logger.warning("No task set available; skipping scan for %s", pr_id)
        return
    tasks = tasks_payload["tasks"]
    if not tasks:
        logger.warning("Task list empty; skipping scan for %s", pr_id)
        return
    changed_files = record.changed_files or []
    if not changed_files:
        logger.info("No changed files for %s; marking passed.", pr_id)
        _save_runner_result(pr_id, [], True, len(tasks))
        return

    ref = record.head_sha or record.head_branch
    files_data = []
    for path in changed_files:
        content = fetch_file_content(record.repository, path, ref)
        if content is None:
            logger.warning("Unable to fetch %s for %s", path, pr_id)
            continue
        files_data.append((path, content))
    if not files_data:
        logger.warning("No file contents fetched for %s", pr_id)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps(tasks, indent=2), encoding="utf-8")
        temp_files: List[Path] = []
        path_map: Dict[str, str] = {}
        for rel_path, content in files_data:
            safe_rel = rel_path.lstrip("/\\")
            dest = tmp_path / safe_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            temp_files.append(dest)
            path_map[str(dest)] = rel_path

        cmd = [sys.executable, str(VALIDATOR_PATH), "--tasks", str(tasks_file), "--files", *[str(p) for p in temp_files], "--json"]
        start = datetime.now(timezone.utc)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(REPO_ROOT))
            output = result.stdout.strip()
            if not output:
                logger.warning("Validator produced no output for %s", pr_id)
                return
            report = json.loads(output)
        except subprocess.CalledProcessError as exc:
            logger.error("Validator failed for %s: %s\n%s", pr_id, exc, exc.stderr)
            return
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON from validator for %s: %s\n%s", pr_id, exc, result.stdout)
            return

    findings = report.get("findings", [])
    violations = _build_violations(findings, tasks, path_map)
    passed = bool(report.get("ALL_TASKS_MET"))
    _save_runner_result(pr_id, violations, passed, len(tasks), start)


def _build_violations(findings: List[dict], tasks: List[dict], path_map: Dict[str, str]) -> List[AgentViolation]:
    if not findings:
        return []
    title_map = {task.get("title") or task.get("name"): task for task in tasks}
    id_map = {task.get("id"): task for task in tasks}
    violations: List[AgentViolation] = []
    for finding in findings:
        task_name = finding.get("task")
        task_info = title_map.get(task_name) or id_map.get(task_name)
        severity = (task_info or {}).get("severity", "warning")
        task_id = (task_info or {}).get("id", task_name or "task")
        temp_path = finding.get("file")
        rel_path = path_map.get(temp_path, temp_path)
        violations.append(
            AgentViolation(
                task_id=task_id,
                message=finding.get("message", "Task violation detected."),
                file=rel_path,
                line=int(finding.get("line", 1)),
                severity=severity,
                suggested_fix=finding.get("fix"),
            )
        )
    return violations


def _save_runner_result(pr_id: str, violations: List[AgentViolation], passed: bool, task_count: int, start_time: Optional[datetime] = None) -> None:
    status = "passed" if passed else ("critical" if any(v.severity == "critical" for v in violations) else "warnings")
    start = start_time or datetime.now(timezone.utc)
    end = datetime.now(timezone.utc)
    notes = "All tasks passed." if passed else f"Detected {len(violations)} violation(s)."
    request = AgentRunIngestRequest(
        pullRequestId=pr_id,
        status=status,
        started_at=start,
        completed_at=end,
        task_count=task_count,
        source="backend_runner",
        notes=notes,
        violations=violations,
    )
    storage.save_scan_result(request.to_record())
    logger.info("Stored scan result for %s (%s)", pr_id, status)
