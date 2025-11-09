from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import TASKS_DIR, PRS_DIR, RUNS_DIR
from .schemas import (
    Task,
    TaskMetadata,
    PullRequestSummary,
    PullRequestRecord,
    AgentRunRecord,
)

TASK_INDEX_FILE = TASKS_DIR / "index.json"
PR_INDEX_FILE = PRS_DIR / "pull_requests.json"


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def save_task_set(tasks: List[Task]) -> TaskMetadata:
    timestamp = datetime.now(timezone.utc).isoformat().replace(":", "-")
    task_set_id = f"taskset-{timestamp}"
    file_path = TASKS_DIR / f"{task_set_id}.json"
    payload = [task.as_payload() for task in tasks]
    _write_json(file_path, payload)

    metadata = {
        "task_set_id": task_set_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(tasks),
        "path": str(file_path.relative_to(TASKS_DIR.parent)),
    }

    index = _read_json(TASK_INDEX_FILE, [])
    index.append(metadata)
    _write_json(TASK_INDEX_FILE, index)

    return TaskMetadata(**metadata)


def get_latest_task_metadata() -> Optional[TaskMetadata]:
    index = _read_json(TASK_INDEX_FILE, [])
    if not index:
        return None
    latest = max(index, key=lambda item: item["created_at"])
    return TaskMetadata(**latest)


def load_tasks_from_metadata(meta: TaskMetadata) -> List[dict]:
    file_path = TASKS_DIR.parent / meta.path
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    return json.loads(file_path.read_text(encoding="utf-8"))


def load_latest_tasks_payload() -> Optional[dict]:
    meta = get_latest_task_metadata()
    if not meta:
        return None
    return {
        "metadata": meta,
        "tasks": load_tasks_from_metadata(meta),
    }


def load_pull_requests() -> List[PullRequestSummary]:
    items = _read_json(PR_INDEX_FILE, [])
    return [PullRequestSummary(**item) for item in items]


def load_pull_request_record(pr_id: str) -> Optional[PullRequestRecord]:
    items = _read_json(PR_INDEX_FILE, [])
    for item in items:
        if item.get("id") == pr_id:
            return PullRequestRecord(**item)
    return None


def upsert_pull_request(record: PullRequestRecord) -> PullRequestSummary:
    items = _read_json(PR_INDEX_FILE, [])
    payload = record.model_dump(by_alias=True)
    updated = False
    for idx, existing in enumerate(items):
        if existing.get("id") == record.id:
            items[idx] = payload
            updated = True
            break
    if not updated:
        items.append(payload)
    _write_json(PR_INDEX_FILE, items)
    return PullRequestSummary(**payload)


def save_agent_run(record: AgentRunRecord) -> None:
    payload = record.model_dump(by_alias=True)
    run_path = RUNS_DIR / f"{record.run_id}.json"
    _write_json(run_path, payload)
    latest_path = RUNS_DIR / f"{record.pull_request_id}-latest.json"
    _write_json(latest_path, payload)
    _update_pull_request_from_run(record)


def load_agent_run(pr_id: str) -> Optional[AgentRunRecord]:
    latest_path = RUNS_DIR / f"{pr_id}-latest.json"
    if not latest_path.exists():
        return None
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    return AgentRunRecord(**payload)


def _update_pull_request_from_run(record: AgentRunRecord) -> None:
    items = _read_json(PR_INDEX_FILE, [])
    changed = False
    mapped_status = _map_run_status(record.status)
    last_run_time = (record.completed_at or record.started_at).isoformat()
    for entry in items:
        if entry.get("id") == record.pull_request_id:
            entry["status"] = mapped_status
            entry["violations"] = len(record.violations)
            entry["lastRun"] = last_run_time
            changed = True
            break
    if changed:
        _write_json(PR_INDEX_FILE, items)


def _map_run_status(run_status: str) -> str:
    if run_status == "passed":
        return "ready"
    if run_status == "warnings":
        return "violations"
    if run_status in {"critical", "error"}:
        return "critical"
    return "pending"
