"""Development authentication — Sprint 1.

In dev mode a caller identifies itself by sending:
    X-Dev-User-ID: <uuid>

The dependency resolves the UUID to a real User row. If the user does not
exist, it returns 401. This is intentionally the simplest mechanism that
makes permission logic testable end-to-end without building OAuth.

Replace this module in a future sprint when real authentication is wired.
"""
import uuid as _uuid

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UnauthorizedError
from app.db.models.users import User
from app.db.session import get_db


async def get_current_user(
    x_dev_user_id: str | None = Header(default=None, alias="X-Dev-User-ID"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — resolves the caller to a User row.

    Requires header:  X-Dev-User-ID: <uuid>
    Raises 401 if the header is missing or the user does not exist.
    """
    if x_dev_user_id is None:
        raise UnauthorizedError("X-Dev-User-ID header is required.")

    try:
        user_id = _uuid.UUID(x_dev_user_id)
    except ValueError:
        raise UnauthorizedError("X-Dev-User-ID must be a valid UUID.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("User not found.")

    return user
