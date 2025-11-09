from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .config import API_TOKEN, ensure_directories
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
