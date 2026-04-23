from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.models.session import ClaimRequest, ClaimResponse
from app.services import session_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/claim", response_model=ClaimResponse)
async def claim_session_name(
    body: ClaimRequest,
    x_device_id: str = Header(..., description="Auto-generated device identifier"),
):
    """Claim a session name for this device. Returns 409 if already taken by another device."""
    ok = await session_store.claim_session_name(body.session_name, x_device_id)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail="Session name already exists",
        )
    return ClaimResponse(ok=True, session_name=body.session_name)
