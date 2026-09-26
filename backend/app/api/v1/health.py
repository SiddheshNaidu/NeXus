from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.health import HealthResponse

router = APIRouter()

_VERSION = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns application and database status.",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Check application health and database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(tz=timezone.utc),
        database=db_status,
        version=_VERSION,
    )
