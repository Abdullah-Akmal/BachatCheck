from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from bachatcheck import __version__
from bachatcheck.db import get_session

router = APIRouter(tags=["health"])
log = structlog.get_logger()


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    """Liveness + database reachability.

    Always returns 200 so the process stays 'up' while the database is down.
    """
    try:
        session.execute(text("SELECT 1"))
        db_status: Literal["ok", "unavailable"] = "ok"
    except SQLAlchemyError as exc:
        log.warning("health.db_unavailable", error=str(exc.__class__.__name__))
        db_status = "unavailable"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=__version__,
        database=db_status,
    )
