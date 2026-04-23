from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from app.config import settings
from app.models.session import Session, SessionStatus


def _key(session_id: str) -> str:
    return f"session:{session_id}"


def _user_index_key(user_id: str) -> str:
    return f"user_sessions:{user_id}"


def _name_owner_key(session_name: str) -> str:
    return f"name_owner:{session_name}"


_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
    return _pool


# --- Session name ownership ---


async def claim_session_name(session_name: str, device_id: str) -> bool:
    """Try to claim a session name for a device.
    Returns True if the name is now owned by this device, False if taken by another.
    """
    r = await get_redis()
    existing_owner = await r.get(_name_owner_key(session_name))
    if existing_owner is None:
        await r.set(_name_owner_key(session_name), device_id)
        return True
    return existing_owner == device_id


async def get_session_name_owner(session_name: str) -> str | None:
    r = await get_redis()
    return await r.get(_name_owner_key(session_name))


async def release_session_name(session_name: str) -> None:
    r = await get_redis()
    await r.delete(_name_owner_key(session_name))


# --- Session CRUD ---


async def store_session(session: Session) -> None:
    r = await get_redis()
    await r.set(_key(session.id), session.model_dump_json())
    await r.sadd(_user_index_key(session.user_id), session.id)


async def get_session(session_id: str) -> Session | None:
    r = await get_redis()
    data = await r.get(_key(session_id))
    if data is None:
        return None
    return Session.model_validate_json(data)


async def update_session(session_id: str, updates: dict[str, Any]) -> Session | None:
    r = await get_redis()
    data = await r.get(_key(session_id))
    if data is None:
        return None
    obj = json.loads(data)
    obj.update(updates)
    session = Session.model_validate(obj)
    await r.set(_key(session_id), session.model_dump_json())
    return session


async def list_sessions_for_user(user_id: str) -> list[Session]:
    r = await get_redis()
    session_ids = await r.smembers(_user_index_key(user_id))
    sessions: list[Session] = []
    for sid in session_ids:
        data = await r.get(_key(sid))
        if data is not None:
            s = Session.model_validate_json(data)
            if s.status != SessionStatus.TERMINATED:
                sessions.append(s)
    return sessions


async def delete_session(session_id: str) -> str | None:
    """Delete session record and return the user_id, or None if not found."""
    r = await get_redis()
    data = await r.get(_key(session_id))
    if data is None:
        return None
    session = Session.model_validate_json(data)
    await r.delete(_key(session_id))
    await r.srem(_user_index_key(session.user_id), session_id)
    return session.user_id
