from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
)
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin
from app.core.permissions import require_superuser


router = APIRouter(
    prefix="/api/admin/audit",
    tags=["Admin - Audit"],
    dependencies=[Depends(require_superuser)],
)


@router.get("")
def list_audit_logs(
    response: Response,
    actor_id: UUID | None = None,
    action: str | None = Query(
        default=None,
        min_length=1,
        max_length=200,
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return audit records to an authorised superuser."""

    db = get_supabase_admin()

    try:
        query = db.table("audit_logs").select(
            (
                "id,code,created_at,"
                "actor_id,actor_label,actor_role,"
                "category,action,"
                "target_type,target_id,target_label,"
                "detail,metadata"
            ),
            count="exact",
        )

        if actor_id is not None:
            query = query.eq("actor_id", str(actor_id))

        if action is not None:
            query = query.eq("action", action)

        result = (
            query
            .order("created_at", desc=True)
            .order("id", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve audit records.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }