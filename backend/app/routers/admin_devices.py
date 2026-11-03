import hashlib
import secrets
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
from app.schemas.device import (
    DeviceCreate,
    DevicePage,
    DeviceUpdate,
    DeviceWriteResult,
)


router = APIRouter(
    prefix="/api/admin/devices",
    tags=["Admin - Devices"],
    dependencies=[Depends(require_superuser)],
)

PUBLIC_COLUMNS = (
    "id,device_code,vehicle_id,label,status,gps_status,"
    "firmware_version,last_seen_at,last_latitude,last_longitude,"
    "last_location_at,is_active,registered_by,created_at,updated_at"
)


def save_device_record(
    user: CurrentUser,
    data: dict,
    device_id: UUID | None = None,
    rotate_secret: bool = False,
):
    db = get_supabase_admin()

    device_secret = None
    secret_hash = None

    if device_id is None or rotate_secret:
        device_secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(
            device_secret.encode("utf-8")
        ).hexdigest()

    try:
        result = db.rpc(
            "admin_save_device",
            {
                "p_actor_id": str(user.id),
                "p_data": data,
                "p_device_id": (
                    str(device_id) if device_id is not None else None
                ),
                "p_secret_hash": secret_hash,
            },
        ).execute()

    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(
                status_code=404,
                detail="Device not found.",
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Device management is not permitted.",
            ) from None

        if exc.code == "23505":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The device code already exists or the vehicle "
                    "already has a registered device."
                ),
            ) from None

        if exc.code == "23514":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Device change conflicts with a database rule. "
                    "End open controller sessions before rebinding, "
                    "deactivation or credential rotation."
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
                detail="Invalid device configuration or vehicle assignment.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="The device operation could not be completed.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm the operation. Check the device list. "
                "If a new credential was saved but not received, "
                "rotate it before provisioning the device."
            ),
        ) from None

    if not isinstance(result.data, dict):
        raise HTTPException(
            status_code=503,
            detail="No valid device result was returned.",
        )

    return {
        "device": result.data,
        "device_secret": device_secret,
    }


@router.get("", response_model=DevicePage)
def list_devices(
    response: Response,
    vehicle_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    db = get_supabase_admin()

    try:
        query = db.table("devices").select(
            PUBLIC_COLUMNS,
            count="exact",
        )

        if vehicle_id is not None:
            query = query.eq("vehicle_id", str(vehicle_id))

        result = (
            query
            .order("device_code")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve devices.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201, response_model=DeviceWriteResult)
def register_device(
    payload: DeviceCreate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    result = save_device_record(
        user=user,
        data=payload.model_dump(mode="json"),
    )

    response.headers["Cache-Control"] = "no-store"

    return result


@router.patch("/{device_id}", response_model=DeviceWriteResult)
def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    changes = payload.model_dump(
        mode="json",
        exclude_unset=True,
        exclude={"rotate_secret"},
    )

    result = save_device_record(
        user=user,
        data=changes,
        device_id=device_id,
        rotate_secret=payload.rotate_secret,
    )

    response.headers["Cache-Control"] = "no-store"

    return result