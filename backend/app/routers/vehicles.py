from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from httpx import HTTPError
from postgrest.exceptions import APIError
from app.core.database import get_supabase_admin
from app.core.permissions import require_car_owner
from app.schemas.auth import CurrentUser
from app.services.owner_registry import VEHICLE_COLUMNS, active_device, owned_vehicle, owner_scope

router = APIRouter(prefix="/api/vehicles", tags=["Owner - Vehicles"],
                   dependencies=[Depends(require_car_owner)])


@router.get("")
def list_my_vehicles(response: Response, limit: int = Query(20, ge=1, le=100),
                     offset: int = Query(0, ge=0), user: CurrentUser = Depends(require_car_owner)):
    try:
        db = get_supabase_admin()
        owner_id = owner_scope(db, user)
        result = (db.table("vehicles").select(VEHICLE_COLUMNS, count="exact").eq("owner_id", owner_id)
                  .order("registration").order("id").range(offset, offset + limit - 1).execute())
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to retrieve your vehicles.") from None
    response.headers["Cache-Control"] = "no-store"
    return {"items": result.data, "total": result.count, "limit": limit, "offset": offset}


@router.get("/{vehicle_id}")
def get_my_vehicle(vehicle_id: UUID, response: Response, user: CurrentUser = Depends(require_car_owner)):
    try:
        vehicle = owned_vehicle(get_supabase_admin(), vehicle_id, user)
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to retrieve your vehicle.") from None
    response.headers["Cache-Control"] = "no-store"
    return vehicle


def age_seconds(value, now):
    if not value:
        return None
    try:
        recorded = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if recorded.tzinfo is None:
            return None
        return (now - recorded).total_seconds()
    except (ValueError, TypeError, AttributeError):
        return None


@router.get("/{vehicle_id}/status")
def get_my_vehicle_status(vehicle_id: UUID, response: Response, user: CurrentUser = Depends(require_car_owner)):
    try:
        db = get_supabase_admin()
        vehicle = owned_vehicle(db, vehicle_id, user)
        device = active_device(db, vehicle_id)
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to retrieve vehicle status.") from None
    now = datetime.now(timezone.utc)
    heartbeat_age = age_seconds(device.get("last_seen_at"), now) if device else None
    online = heartbeat_age is not None and -5 <= heartbeat_age <= 60
    gps = {"status": "unavailable", "latitude": None, "longitude": None, "recorded_at": None}
    if device and device.get("last_latitude") is not None and device.get("last_longitude") is not None:
        gps_age = age_seconds(device.get("last_location_at"), now)
        gps = {"status": "fix" if gps_age is not None and 0 <= gps_age <= 60 else "stale",
               "latitude": device["last_latitude"], "longitude": device["last_longitude"],
               "recorded_at": device.get("last_location_at")}
    response.headers["Cache-Control"] = "no-store"
    return {"vehicle_id": vehicle["id"], "device": device,
            "connection_status": "unassigned" if not device else "fault" if online and device.get("status") == "fault" else "online" if online else "offline",
            "gps": gps, "checked_at": now.isoformat()}


@router.get("/{vehicle_id}/motion/latest")
def get_latest_motion(vehicle_id: UUID, response: Response, user: CurrentUser = Depends(require_car_owner)):
    """Latest uploaded IMU sample for the current active device of an owned car."""
    try:
        db = get_supabase_admin()
        owned_vehicle(db, vehicle_id, user)
        device = active_device(db, vehicle_id)
        rows = [] if not device else (db.table("sensor_readings")
            .select("recorded_at,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z")
            .eq("device_id", str(device["id"])).order("recorded_at", desc=True).limit(1).execute().data)
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to retrieve uploaded motion readings.") from None
    response.headers["Cache-Control"] = "no-store"
    return {"vehicle_id": str(vehicle_id), "sample": rows[0] if rows else None,
            "acceleration_unit": "m/s^2", "rotation_unit": "deg/s"}
