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
from app.schemas.vehicle import VehicleCreate, VehicleUpdate


router = APIRouter(
    prefix="/api/admin/vehicles",
    tags=["Admin - Vehicles"],
    dependencies=[Depends(require_superuser)],
)


def save_vehicle_record(
    user: CurrentUser,
    data: dict,
    vehicle_id: UUID | None = None,
):
    """Shared database operation for registration and editing."""

    db = get_supabase_admin()

    try:
        result = db.rpc(
            "admin_save_vehicle",
            {
                "p_actor_id": str(user.id),
                "p_data": data,
                "p_vehicle_id": (
                    str(vehicle_id)
                    if vehicle_id is not None
                    else None
                ),
            },
        ).execute()

    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(
                status_code=404,
                detail="Vehicle not found.",
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Vehicle management is not permitted.",
            ) from None

        if exc.code == "23505":
            raise HTTPException(
                status_code=409,
                detail="Vehicle details conflict with an existing record.",
            ) from None

        if exc.code == "23514":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The change conflicts with a database rule. "
                    "End open controller sessions before transfer. "
                    "An owner login must retain at least one car."
                ),
            ) from None

        if exc.code in {"40001", "40P01"}:
            raise HTTPException(
                status_code=409,
                detail="A concurrent change occurred. Refresh and retry.",
            ) from None

        if exc.code in {"22023", "22P02", "23502", "23503"}:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid vehicle details. Provide a registration "
                    "and an existing registered owner."
                ),
            ) from None

        raise HTTPException(
            status_code=503,
            detail="The vehicle operation could not be completed.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm the operation. "
                "Check the vehicle list before retrying."
            ),
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="No vehicle result was returned.",
        )

    return result.data[0]


@router.get("")
def list_vehicles(
    response: Response,
    owner_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List vehicles, optionally filtered by owner."""

    db = get_supabase_admin()

    try:
        query = db.table("vehicles").select(
            "id,registration,make,model,colour,owner_id",
            count="exact",
        )

        if owner_id is not None:
            query = query.eq("owner_id", str(owner_id))

        result = (
            query
            .order("registration")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve vehicles.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
def register_vehicle(
    payload: VehicleCreate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    vehicle = save_vehicle_record(
        user=user,
        data=payload.model_dump(mode="json"),
    )

    response.headers["Cache-Control"] = "no-store"

    return vehicle


@router.patch("/{vehicle_id}")
def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    vehicle = save_vehicle_record(
        user=user,
        data=payload.model_dump(
            mode="json",
            exclude_unset=True,
        ),
        vehicle_id=vehicle_id,
    )

    response.headers["Cache-Control"] = "no-store"

    return vehicle