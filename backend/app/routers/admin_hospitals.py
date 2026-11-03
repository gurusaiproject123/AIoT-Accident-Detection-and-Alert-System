from app.schemas.auth import CurrentUser
from app.schemas.hospital import HospitalCreate
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin
from app.core.permissions import require_superuser


router = APIRouter(
    prefix="/api/admin/hospitals",
    tags=["Admin - Hospitals"],
    dependencies=[Depends(require_superuser)],
)


@router.get("")
def list_hospitals(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    db = get_supabase_admin()

    try:
        result = (
            db.table("hospitals")
            .select("id,code,name,city,is_active", count="exact")
            .order("name")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )
    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve hospitals.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }
@router.post("", status_code=201)
def register_hospital(
    payload: HospitalCreate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    db = get_supabase_admin()

    try:
        result = db.rpc(
            "admin_register_hospital",
            {
                "p_actor_id": str(user.id),
                "p_data": payload.model_dump(mode="json"),
            },
        ).execute()

    except APIError as exc:
        if exc.code == "23505":
            raise HTTPException(
                status_code=409,
                detail="A hospital with conflicting unique details exists.",
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Hospital registration is not permitted.",
            ) from None

        if exc.code in {"23514", "23502", "22P02"}:
            raise HTTPException(
                status_code=422,
                detail="Hospital details do not satisfy database rules.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Hospital registration could not be completed.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm registration. "
                "Check the hospital list before retrying."
            ),
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="No registration result was returned.",
        )

    response.headers["Cache-Control"] = "no-store"

    return result.data[0]