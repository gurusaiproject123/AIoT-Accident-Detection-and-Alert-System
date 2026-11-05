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
from app.core.permissions import require_car_owner
from app.schemas.auth import CurrentUser


router = APIRouter(
    prefix="/api/vehicles",
    tags=["Owner - Vehicles"],
    dependencies=[Depends(require_car_owner)],
)


def owner_vehicle_error(exc: APIError) -> HTTPException:
    if exc.code == "42501":
        return HTTPException(
            status_code=403,
            detail="Active car-owner access is required.",
        )

    if exc.code == "P0002":
        return HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    return HTTPException(
        status_code=503,
        detail="Unable to retrieve your vehicle data.",
    )


@router.get("")
def list_my_vehicles(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_car_owner),
):
    """List only cars linked to the signed-in owner."""

    db = get_supabase_admin()

    try:
        result = (
            db.rpc(
                "owner_read_vehicles",
                {"p_actor_id": str(user.id)},
                count="exact",
            )
            .order("registration")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )

    except APIError as exc:
        raise owner_vehicle_error(exc) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve your vehicles.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{vehicle_id}")
def get_my_vehicle(
    vehicle_id: UUID,
    response: Response,
    user: CurrentUser = Depends(require_car_owner),
):
    """Retrieve one owned car."""

    db = get_supabase_admin()

    try:
        result = (
            db.rpc(
                "owner_read_vehicles",
                {"p_actor_id": str(user.id)},
            )
            .eq("id", str(vehicle_id))
            .limit(1)
            .execute()
        )

    except APIError as exc:
        raise owner_vehicle_error(exc) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve your vehicle.",
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found.",
        )

    response.headers["Cache-Control"] = "no-store"

    return result.data[0]


@router.get("/{vehicle_id}/status")
def get_my_vehicle_status(
    vehicle_id: UUID,
    response: Response,
    user: CurrentUser = Depends(require_car_owner),
):
    """Retrieve device and recorded GPS status for an owned car."""

    db = get_supabase_admin()

    try:
        result = db.rpc(
            "owner_read_vehicle_status",
            {
                "p_actor_id": str(user.id),
                "p_vehicle_id": str(vehicle_id),
            },
        ).execute()

    except APIError as exc:
        raise owner_vehicle_error(exc) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve vehicle status.",
        ) from None

    if not isinstance(result.data, dict):
        raise HTTPException(
            status_code=503,
            detail="Vehicle status returned an unexpected result.",
        )

    response.headers["Cache-Control"] = "no-store"

    return result.data