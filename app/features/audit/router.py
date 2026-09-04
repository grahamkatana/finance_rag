from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import UserScope, get_user_scope
from app.core.database import get_db
from app.features.audit.service import AuditService

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/queries")
async def get_query_events(
    client_id: str = Query(default=None),
    max_faithfulness: float = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_user_scope),
):
    # Non-admins only ever see their own events.
    effective_client_id = client_id if scope.is_admin else str(scope.user_id)

    service = AuditService(db=db)
    events = await service.get_query_events(
        client_id=effective_client_id,
        max_faithfulness=max_faithfulness,
        limit=limit,
        offset=offset,
    )
    return {
        "events": events,
        "total": len(events),
        "limit": limit,
        "offset": offset,
    }


@router.get("/ingestions")
async def get_ingestion_events(
    client_id: str = Query(default=None),
    status: str = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_user_scope),
):
    # Non-admins only ever see their own events.
    effective_client_id = client_id if scope.is_admin else str(scope.user_id)

    service = AuditService(db=db)
    events = await service.get_ingestion_events(
        client_id=effective_client_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "events": events,
        "total": len(events),
        "limit": limit,
        "offset": offset,
    }