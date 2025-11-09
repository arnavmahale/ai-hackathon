from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class TaskSet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_set_id: str = Field(index=True, unique=True)
    created_at: datetime
    task_count: int
    tasks: List[dict] = Field(default_factory=list, sa_column=Column(JSON))


class PullRequest(SQLModel, table=True):
    id: str = Field(primary_key=True)
    repository: str
    number: int
    title: str
    author: str
    status: str = Field(default="pending")
    files_changed: int = Field(default=0)
    violations: int = Field(default=0)
    lines_added: int = Field(default=0)
    lines_removed: int = Field(default=0)
    base_branch: str
    head_branch: str
    changed_files: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    last_run: Optional[datetime] = None


class AgentRun(SQLModel, table=True):
    run_id: str = Field(primary_key=True)
    pull_request_id: str = Field(foreign_key="pullrequest.id")
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    task_count: int = Field(default=0)
    source: str
    notes: Optional[str] = None
    violations: List[dict] = Field(default_factory=list, sa_column=Column(JSON))
