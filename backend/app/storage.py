from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import select

from .database import get_session
from .models import TaskSet, ScanResult
from .schemas import (
    Task,
    TaskMetadata,
    PullRequestSummary,
    PullRequestDetail,
    PullRequestRecord,
    AgentRunRecord,
    AgentViolation,
)


def save_task_set(tasks: List[Task]) -> TaskMetadata:
    now = datetime.now(timezone.utc)
    task_set_id = f"taskset-{now.isoformat().replace(':', '-')}"
    payload = [task.as_payload() for task in tasks]
    with get_session() as session:
        entry = TaskSet(task_set_id=task_set_id, created_at=now, task_count=len(payload), tasks=payload)
        session.add(entry)
        session.commit()
        session.refresh(entry)
    return TaskMetadata(
        task_set_id=task_set_id,
        created_at=entry.created_at,
        task_count=entry.task_count,
        path=f"taskset://{task_set_id}",
    )


def load_latest_tasks_payload() -> Optional[dict]:
    with get_session() as session:
        statement = select(TaskSet).order_by(TaskSet.created_at.desc()).limit(1)
        result = session.exec(statement).first()
        if not result:
            return None
        metadata = TaskMetadata(
            task_set_id=result.task_set_id,
            created_at=result.created_at,
            task_count=result.task_count,
            path=f"taskset://{result.task_set_id}",
        )
        return {"metadata": metadata, "tasks": result.tasks}


def load_pull_requests() -> List[PullRequestSummary]:
    with get_session() as session:
        rows = session.exec(select(ScanResult).order_by(ScanResult.run_completed_at.desc().nulls_last())).all()
        return [
            PullRequestSummary(
                id=row.pr_id,
                number=row.number,
                title=row.title,
                repository=row.repository,
                author=row.author,
                status=row.status,
                files_changed=row.files_changed,
                violations=len(row.violations or []),
                lines_added=row.lines_added,
                lines_removed=row.lines_removed,
                last_run=row.run_completed_at,
            )
            for row in rows
        ]


def load_pull_request_record(pr_id: str) -> Optional[PullRequestDetail]:
    with get_session() as session:
        row = session.get(ScanResult, pr_id)
        if not row:
            return None
        return PullRequestDetail(
            id=row.pr_id,
            number=row.number,
            title=row.title,
            repository=row.repository,
            author=row.author,
            status=row.status,
            files_changed=row.files_changed,
            violations=len(row.violations or []),
            lines_added=row.lines_added,
            lines_removed=row.lines_removed,
            base_branch=row.base_branch,
            head_branch=row.head_branch,
            head_sha=row.head_sha,
            changed_files=row.changed_files,
            last_run=row.run_completed_at,
            result=row.violations or [],
            summary=row.summary,
        )


def upsert_scan_result(record: PullRequestRecord) -> PullRequestSummary:
    with get_session() as session:
        row = session.get(ScanResult, record.id)
        if not row:
            row = ScanResult(
                pr_id=record.id,
                repository=record.repository,
                number=record.number,
                title=record.title,
                author=record.author,
                base_branch=record.base_branch,
                head_branch=record.head_branch,
                head_sha=record.head_sha,
                files_changed=record.files_changed,
                lines_added=record.lines_added,
                lines_removed=record.lines_removed,
                changed_files=record.changed_files,
                status="pending",
            )
            session.add(row)
        else:
            row.repository = record.repository
            row.number = record.number
            row.title = record.title
            row.author = record.author
            row.base_branch = record.base_branch
            row.head_branch = record.head_branch
            row.head_sha = record.head_sha
            row.files_changed = record.files_changed
            row.lines_added = record.lines_added
            row.lines_removed = record.lines_removed
            row.changed_files = record.changed_files
        session.commit()
        session.refresh(row)
        return PullRequestSummary(
            id=row.pr_id,
            number=row.number,
            title=row.title,
            repository=row.repository,
            author=row.author,
            status=row.status,
            files_changed=row.files_changed,
            violations=len(row.violations or []),
            lines_added=row.lines_added,
            lines_removed=row.lines_removed,
            last_run=row.run_completed_at,
        )


def save_scan_result(record: AgentRunRecord) -> None:
    with get_session() as session:
        row = session.get(ScanResult, record.pull_request_id)
        if not row:
            row = ScanResult(
                pr_id=record.pull_request_id,
                repository="",
                number=0,
                title="",
                author="",
                base_branch="",
                head_branch="",
            )
            session.add(row)
        row.status = _map_run_status(record.status)
        row.summary = record.notes
        row.run_started_at = record.started_at
        row.run_completed_at = record.completed_at or record.started_at
        row.violations = [
            violation.model_dump(by_alias=True) if isinstance(violation, AgentViolation) else violation
            for violation in record.violations
        ]
        session.commit()


def load_scan_result(pr_id: str) -> Optional[AgentRunRecord]:
    with get_session() as session:
        row = session.get(ScanResult, pr_id)
        if not row or not row.run_started_at:
            return None
        return AgentRunRecord(
            run_id=f"{row.pr_id}-latest",
            pull_request_id=row.pr_id,
            status=row.status,
            started_at=row.run_started_at,
            completed_at=row.run_completed_at,
            task_count=0,
            source="webhook",
            notes=row.summary,
            violations=row.violations or [],
        )


def _map_run_status(status: str) -> str:
    if status == "passed":
        return "ready"
    if status == "warnings":
        return "violations"
    if status in {"critical", "error"}:
        return "critical"
    return status or "pending"
