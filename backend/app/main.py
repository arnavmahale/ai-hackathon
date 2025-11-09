from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import API_TOKEN, ensure_directories
from .security import verify_github_signature
from .github_client import fetch_pull_request_files
from .schemas import (
    TaskIngestRequest,
    TaskIngestResponse,
    PullRequestListResponse,
    PullRequestSummary,
    PullRequestDetail,
    PullRequestIngestRequest,
    AgentRunIngestRequest,
    AgentRunRecord,
)
from . import storage

ensure_directories()

app = FastAPI(title="Guardians API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


def require_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not API_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@app.get("/healthz")
def healthcheck():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": app.version,
    }


@app.post("/tasks", response_model=TaskIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_tasks(payload: TaskIngestRequest, _: None = Depends(require_token)):
    if not payload.tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one task is required")
    metadata = storage.save_task_set(payload.tasks)
    return metadata


@app.get("/tasks/current")
def get_current_tasks():
    latest = storage.load_latest_tasks_payload()
    if not latest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No task sets found")
    return {
        "metadata": latest["metadata"],
        "tasks": latest["tasks"],
    }


@app.get("/pull-requests", response_model=PullRequestListResponse)
def list_pull_requests():
    items = storage.load_pull_requests()
    return PullRequestListResponse(items=items)


@app.post("/pull-requests", response_model=PullRequestSummary, status_code=status.HTTP_201_CREATED)
def ingest_pull_request(payload: PullRequestIngestRequest, _: None = Depends(require_token)):
    record = payload.to_record()
    summary = storage.upsert_pull_request(record)
    return summary


@app.get("/pull-requests/{pr_id}", response_model=PullRequestDetail)
def get_pull_request(pr_id: str):
    record = storage.load_pull_request_record(pr_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PR not found")
    return record


@app.post("/agent-runs", response_model=AgentRunRecord, status_code=status.HTTP_202_ACCEPTED)
def ingest_agent_run(payload: AgentRunIngestRequest, _: None = Depends(require_token)):
    record = payload.to_record()
    storage.save_agent_run(record)
    return record


@app.get("/agent-results/{pr_id}", response_model=AgentRunRecord)
def get_agent_results(pr_id: str):
    record = storage.load_agent_run(pr_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Results not found")
    return record
@app.post("/github/webhook", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    raw_body = await request.body()
    verify_github_signature(raw_body, x_hub_signature_256)

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": "unsupported event"}

    payload = await request.json()
    action = payload.get("action")
    if action not in {"opened", "reopened", "synchronize"}:
        return {"status": "ignored", "reason": f"action {action}"}

    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    changed_files = fetch_pull_request_files(repo.get("full_name", ""), pr.get("number"))

    pr_payload = PullRequestIngestRequest(
        repository=repo.get("full_name", ""),
        number=pr.get("number"),
        title=pr.get("title", ""),
        author=pr.get("user", {}).get("login", ""),
        base_branch=pr.get("base", {}).get("ref", ""),
        head_branch=pr.get("head", {}).get("ref", ""),
        files_changed=pr.get("changed_files", 0),
        lines_added=pr.get("additions", 0),
        lines_removed=pr.get("deletions", 0),
        changed_files=changed_files,
    )
    storage.upsert_pull_request(pr_payload.to_record())
    return {"status": "accepted"}
