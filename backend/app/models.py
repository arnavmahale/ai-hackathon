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


class ScanResult(SQLModel, table=True):
    pr_id: str = Field(primary_key=True)
    repository: str
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    head_sha: Optional[str] = None
    files_changed: int = Field(default=0)
    lines_added: int = Field(default=0)
    lines_removed: int = Field(default=0)
    changed_files: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="pending")
    summary: Optional[str] = None
    violations: List[dict] = Field(default_factory=list, sa_column=Column(JSON))
    run_started_at: Optional[datetime] = None
    run_completed_at: Optional[datetime] = None
