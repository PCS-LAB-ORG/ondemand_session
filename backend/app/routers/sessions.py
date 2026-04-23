from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.models.session import (
    Session,
    SessionListResponse,
    SessionStatus,
)
from app.services import k8s_manager, session_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _verify_ownership(device_id: str, session_name: str) -> None:
    """Verify the device owns this session name."""
    owner = await session_store.get_session_name_owner(session_name)
    if owner is None or owner != device_id:
        raise HTTPException(status_code=403, detail="Not authorized for this session name")


@router.post("", response_model=Session, status_code=201)
async def create_session(
    x_device_id: str = Header(..., description="Auto-generated device identifier"),
    x_session_name: str = Header(..., description="User-chosen session name"),
):
    await _verify_ownership(x_device_id, x_session_name)

    session_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.session_ttl_hours)

    session = Session(
        id=session_id,
        user_id=x_device_id,
        session_name=x_session_name,
        status=SessionStatus.PENDING,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        access_url=None,
    )
    await session_store.store_session(session)

    try:
        k8s_manager.create_session_pod(session_id)
        k8s_manager.create_session_service(session_id)
        access_url = k8s_manager.create_session_ingress(session_id, x_session_name)
        session = await session_store.update_session(
            session_id, {"access_url": access_url}
        )
    except Exception as e:
        await session_store.update_session(
            session_id, {"status": SessionStatus.FAILED}
        )
        raise HTTPException(status_code=500, detail=f"Failed to provision session: {e}")

    return session


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    x_device_id: str = Header(..., description="Auto-generated device identifier"),
    x_session_name: str = Header(..., description="User-chosen session name"),
):
    await _verify_ownership(x_device_id, x_session_name)
    sessions = await session_store.list_sessions_for_user(x_device_id)

    for s in sessions:
        if s.status == SessionStatus.PENDING:
            phase = k8s_manager.get_pod_status(s.id)
            if phase == "Running":
                await session_store.update_session(
                    s.id, {"status": SessionStatus.RUNNING}
                )
                s.status = SessionStatus.RUNNING
            elif phase in ("Failed", "Unknown", None):
                await session_store.update_session(
                    s.id, {"status": SessionStatus.FAILED}
                )
                s.status = SessionStatus.FAILED

    return SessionListResponse(sessions=sessions)


@router.get("/{session_id}", response_model=Session)
async def get_session(
    session_id: str,
    x_device_id: str = Header(..., description="Auto-generated device identifier"),
    x_session_name: str = Header(..., description="User-chosen session name"),
):
    await _verify_ownership(x_device_id, x_session_name)

    session = await session_store.get_session(session_id)
    if session is None or session.user_id != x_device_id:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status == SessionStatus.PENDING:
        phase = k8s_manager.get_pod_status(session_id)
        if phase == "Running":
            session = await session_store.update_session(
                session_id, {"status": SessionStatus.RUNNING}
            )
        elif phase in ("Failed", "Unknown", None):
            session = await session_store.update_session(
                session_id, {"status": SessionStatus.FAILED}
            )

    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    x_device_id: str = Header(..., description="Auto-generated device identifier"),
    x_session_name: str = Header(..., description="User-chosen session name"),
):
    await _verify_ownership(x_device_id, x_session_name)

    session = await session_store.get_session(session_id)
    if session is None or session.user_id != x_device_id:
        raise HTTPException(status_code=404, detail="Session not found")

    k8s_manager.delete_session_resources(session_id)
    await session_store.delete_session(session_id)
