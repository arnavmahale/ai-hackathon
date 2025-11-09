from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict


class SourceFile(BaseModel):
    name: str
    size: int = Field(ge=0)
    mime: Optional[str] = None


class Task(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    description: str
    category: str
    severity: str
    check_type: str = Field(alias="checkType")
    file_types: List[str] = Field(alias="fileTypes")
    example_violation: str = Field(alias="exampleViolation")
    suggested_fix: str = Field(alias="suggestedFix")
    doc_reference: str = Field(alias="docReference")

    def as_payload(self) -> dict:
        return self.model_dump(by_alias=True)


class TaskIngestRequest(BaseModel):
    tasks: List[Task]
    source_files: Optional[List[SourceFile]] = Field(default=None, alias="sourceFiles")


class TaskMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_set_id: str = Field(alias="taskSetId")
    created_at: datetime = Field(alias="createdAt")
    task_count: int = Field(alias="taskCount")
    path: str


class TaskIngestResponse(TaskMetadata):
    pass


class PullRequestSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    number: int
    title: str
    repository: str
    author: str
    status: str
    files_changed: int = Field(alias="filesChanged")
    violations: int
    lines_added: int = Field(alias="linesAdded")
    lines_removed: int = Field(alias="linesRemoved")
    last_run: Optional[datetime] = Field(default=None, alias="lastRun")


class PullRequestRecord(PullRequestSummary):
    base_branch: str = Field(alias="baseBranch")
    head_branch: str = Field(alias="headBranch")
    head_sha: Optional[str] = Field(default=None, alias="headSha")
    changed_files: List[str] = Field(default_factory=list, alias="changedFiles")


class PullRequestIngestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    repository: str = Field(alias="repo")
    number: int = Field(alias="pr_number")
    title: str
    author: str
    base_branch: str = Field(alias="baseBranch")
    head_branch: str = Field(alias="headBranch")
    head_sha: Optional[str] = Field(default=None, alias="headSha")
    files_changed: int = Field(alias="filesChanged")
    lines_added: int = Field(alias="linesAdded")
    lines_removed: int = Field(alias="linesRemoved")
    changed_files: List[str] = Field(default_factory=list, alias="changedFiles")
    status: str = "pending"
    violations: int = 0
    pr_id: Optional[str] = Field(default=None, alias="id")

    def to_record(self) -> PullRequestRecord:
        pr_id = self.pr_id or f"{self.repository}#PR-{self.number}"
        return PullRequestRecord(
            id=pr_id,
            number=self.number,
            title=self.title,
            repository=self.repository,
            author=self.author,
            status=self.status,
            files_changed=self.files_changed,
            violations=self.violations,
            lines_added=self.lines_added,
            lines_removed=self.lines_removed,
            base_branch=self.base_branch,
            head_branch=self.head_branch,
            head_sha=self.head_sha,
            changed_files=self.changed_files,
        )


class PullRequestListResponse(BaseModel):
    items: List[PullRequestSummary]


class PullRequestDetail(PullRequestRecord):
    result: List[dict] = Field(default_factory=list)
    summary: Optional[str] = None


class AgentViolation(BaseModel):
    task_id: str = Field(alias="taskId")
    message: str
    file: str
    line: int
    severity: str
    suggested_fix: Optional[str] = Field(default=None, alias="suggestedFix")


class AgentRunRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(alias="runId")
    pull_request_id: str = Field(alias="pullRequestId")
    status: str
    started_at: datetime = Field(alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")
    task_count: int = Field(default=0, alias="taskCount")
    source: str = "github_action"
    notes: Optional[str] = None
    violations: List[AgentViolation] = Field(default_factory=list)


class AgentRunIngestRequest(BaseModel):
    run_id: Optional[str] = Field(default=None, alias="runId")
    pull_request_id: str = Field(alias="pullRequestId")
    status: str
    started_at: Optional[datetime] = Field(default=None, alias="startedAt")
    completed_at: Optional[datetime] = Field(default=None, alias="completedAt")
    task_count: int = Field(default=0, alias="taskCount")
    source: str = "github_action"
    notes: Optional[str] = None
    violations: List[AgentViolation] = Field(default_factory=list)

    def to_record(self) -> AgentRunRecord:
        now = datetime.now(timezone.utc)
        return AgentRunRecord(
            run_id=self.run_id or f"run-{uuid4()}",
            pull_request_id=self.pull_request_id,
            status=self.status,
            started_at=self.started_at or now,
            completed_at=self.completed_at,
            task_count=self.task_count,
            source=self.source,
            notes=self.notes,
            violations=self.violations,
        )
