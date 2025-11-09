from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import select

from .database import get_session
from .models import TaskSet, PullRequest, AgentRun
from .schemas import Task, TaskMetadata, PullRequestSummary, PullRequestRecord, AgentRunRecord, AgentViolation


def save_task_set(tasks: List[Task]) -> TaskMetadata:
    now = datetime.now(timezone.utc)
    task_set_id = f"taskset-{now.isoformat().replace(":", "-")}"
    payload = [task.as_payload() for task in tasks]
    with get_session() as session:
        entry = TaskSet(task_set_id=task_set_id, created_at=now, task_count=len(payload), tasks=payload)
        session.add(entry)
        session.commit()
        session.refresh(entry)
    return TaskMetadata(task_set_id=task_set_id, created_at=entry.created_at, task_count=entry.task_count, path=f"taskset://{task_set_id}")


def load_latest_tasks_payload() -> Optional[dict]:
    with get_session() as session:
        statement = select(TaskSet).order_by(TaskSet.created_at.desc()).limit(1)
        result = session.exec(statement).first()
        if not result:
            return None
        metadata = TaskMetadata(task_set_id=result.task_set_id, created_at=result.created_at, task_count=result.task_count, path=f"taskset://{result.task_set_id}")
        return {"metadata": metadata, "tasks": result.tasks}


def load_pull_requests() -> List[PullRequestSummary]:
    with get_session() as session:
        prs = session.exec(select(PullRequest)).all()
        return [
            PullRequestSummary(
                id=pr.id,
                number=pr.number,
                title=pr.title,
                repository=pr.repository,
                author=pr.author,
                status=pr.status,
                files_changed=pr.files_changed,
                violations=pr.violations,
                lines_added=pr.lines_added,
                lines_removed=pr.lines_removed,
                last_run=pr.last_run,
            )
            for pr in prs
        ]


def load_pull_request_record(pr_id: str) -> Optional[PullRequestRecord]:
    with get_session() as session:
        pr = session.get(PullRequest, pr_id)
        if not pr:
            return None
        return PullRequestRecord(
            id=pr.id,
            number=pr.number,
            title=pr.title,
            repository=pr.repository,
            author=pr.author,
            status=pr.status,
            files_changed=pr.files_changed,
            violations=pr.violations,
            lines_added=pr.lines_added,
            lines_removed=pr.lines_removed,
            base_branch=pr.base_branch,
            head_branch=pr.head_branch,
            changed_files=pr.changed_files,
            last_run=pr.last_run,
        )


def upsert_pull_request(record: PullRequestRecord) -> PullRequestSummary:
    with get_session() as session:
        pr = session.get(PullRequest, record.id)
        if not pr:
            pr = PullRequest(
                id=record.id,
                repository=record.repository,
                number=record.number,
                title=record.title,
                author=record.author,
                status=record.status,
                files_changed=record.files_changed,
                violations=record.violations,
                lines_added=record.lines_added,
                lines_removed=record.lines_removed,
                base_branch=record.base_branch,
                head_branch=record.head_branch,
                changed_files=record.changed_files,
                last_run=record.last_run,
            )
            session.add(pr)
        else:
            pr.repository = record.repository
            pr.number = record.number
            pr.title = record.title
            pr.author = record.author
            pr.status = record.status
            pr.files_changed = record.files_changed
            pr.violations = record.violations
            pr.lines_added = record.lines_added
            pr.lines_removed = record.lines_removed
            pr.base_branch = record.base_branch
            pr.head_branch = record.head_branch
            pr.changed_files = record.changed_files
            pr.last_run = record.last_run
        session.commit()
        session.refresh(pr)
        return PullRequestSummary(
            id=pr.id,
            number=pr.number,
            title=pr.title,
            repository=pr.repository,
            author=pr.author,
            status=pr.status,
            files_changed=pr.files_changed,
            violations=pr.violations,
            lines_added=pr.lines_added,
            lines_removed=pr.lines_removed,
            last_run=pr.last_run,
        )


def save_agent_run(record: AgentRunRecord) -> None:
    with get_session() as session:
        entry = AgentRun(
            run_id=record.run_id,
            pull_request_id=record.pull_request_id,
            status=record.status,
            started_at=record.started_at,
            completed_at=record.completed_at,
            task_count=record.task_count,
            source=record.source,
            notes=record.notes,
            violations=[
                violation.model_dump(by_alias=True) if isinstance(violation, AgentViolation) else violation
                for violation in record.violations
            ],
        )
        session.merge(entry)
        pr = session.get(PullRequest, record.pull_request_id)
        if pr:
            pr.status = _map_run_status(record.status)
            pr.violations = len(record.violations)
            pr.last_run = record.completed_at or record.started_at
        session.commit()


def load_agent_run(pr_id: str) -> Optional[AgentRunRecord]:
    with get_session() as session:
        run = (
            session.exec(
                select(AgentRun)
                .where(AgentRun.pull_request_id == pr_id)
                .order_by(AgentRun.started_at.desc())
            ).first()
        )
        if not run:
            return None
        return AgentRunRecord(
            run_id=run.run_id,
            pull_request_id=run.pull_request_id,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            task_count=run.task_count,
            source=run.source,
            notes=run.notes,
            violations=run.violations,
        )


def _map_run_status(run_status: str) -> str:
    if run_status == "passed":
        return "ready"
    if run_status == "warnings":
        return "violations"
    if run_status in {"critical", "error"}:
        return "critical"
    return "pending"
