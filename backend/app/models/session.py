from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    TERMINATED = "terminated"


class Session(BaseModel):
    id: str
    user_id: str
    session_name: str
    status: SessionStatus
    created_at: str
    expires_at: str
    access_url: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[Session] = Field(default_factory=list)


class ClaimRequest(BaseModel):
    session_name: str


class ClaimResponse(BaseModel):
    ok: bool
    session_name: str
