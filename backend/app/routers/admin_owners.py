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
from app.schemas.auth import CurrentUser
from app.schemas.owner import OwnerCreate, OwnerUpdate


router = APIRouter(
    prefix="/api/admin/owners",
    tags=["Admin - Vehicle Owners"],
    dependencies=[Depends(require_superuser)],
)


def owner_database_error(exc: APIError) -> HTTPException:
    """Translate database errors without exposing internal details."""

    if exc.code == "P0002":
        return HTTPException(
            status_code=404,
            detail="Registered owner not found.",
        )

    if exc.code == "42501":
        return HTTPException(
            status_code=403,
            detail="Owner management is not permitted.",
        )

    if exc.code == "23505":
        return HTTPException(
            status_code=409,
            detail="Owner details conflict with an existing record.",
        )

    if exc.code in {"23514", "23502", "23503", "22023", "22P02"}:
        return HTTPException(
            status_code=422,
            detail="Owner details do not satisfy database rules.",
        )

    return HTTPException(
        status_code=503,
        detail="The owner operation could not be completed.",
    )


@router.get("")
def list_owners(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List owner contact records. Superusers only."""

    db = get_supabase_admin()

    try:
        result = (
            db.table("vehicle_owners")
            .select(
                "id,full_name,phone,email,relationship,user_id",
                count="exact",
            )
            .order("full_name")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve registered owners.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
def register_owner(
    payload: OwnerCreate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Register contact details without creating an Auth account."""

    db = get_supabase_admin()

    try:
        result = db.rpc(
            "admin_register_owner",
            {
                "p_actor_id": str(user.id),
                "p_full_name": payload.full_name,
                "p_phone": payload.phone,
                "p_email": (
                    str(payload.email)
                    if payload.email is not None
                    else None
                ),
            },
        ).execute()

    except APIError as exc:
        raise owner_database_error(exc) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm registration. "
                "Check the owner list before retrying."
            ),
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="No owner registration result was returned.",
        )

    response.headers["Cache-Control"] = "no-store"

    return result.data[0]


@router.patch("/{owner_id}")
def update_owner(
    owner_id: UUID,
    payload: OwnerUpdate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Edit contact details while preserving the existing login link."""

    db = get_supabase_admin()

    changes = payload.model_dump(
        mode="json",
        exclude_unset=True,
    )

    try:
        result = db.rpc(
            "admin_update_owner",
            {
                "p_actor_id": str(user.id),
                "p_owner_id": str(owner_id),
                "p_data": changes,
            },
        ).execute()

    except APIError as exc:
        raise owner_database_error(exc) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm the update. "
                "Check the owner record before retrying."
            ),
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="No owner update result was returned.",
        )

    response.headers["Cache-Control"] = "no-store"

    return result.data[0]