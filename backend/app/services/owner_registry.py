"""Owner-scoped reads; no service-role query may omit the verified owner link."""
from fastapi import HTTPException
from httpx import HTTPError
from postgrest.exceptions import APIError
from app.core.database import get_supabase_admin

VEHICLE_COLUMNS = "id,registration,make,model,colour,owner_id"
DEVICE_COLUMNS = ("id,device_code,vehicle_id,label,is_active,status,gps_status,firmware_version,"
                  "last_seen_at,last_latitude,last_longitude,last_location_at")


def owner_scope(db, user):
    if user.role != "car_owner" or user.status != "active" or not user.owner_id:
        raise HTTPException(403, "Active linked car-owner access is required.")
    owners = (db.table("vehicle_owners").select("id").eq("id", str(user.owner_id))
              .eq("user_id", str(user.id)).limit(1).execute().data)
    if not owners:
        raise HTTPException(403, "Owner login assignment changed. Sign in again.")
    return str(owners[0]["id"])


def owned_vehicle(db, vehicle_id, user):
    owner_id = owner_scope(db, user)
    rows = (db.table("vehicles").select(VEHICLE_COLUMNS).eq("id", str(vehicle_id))
            .eq("owner_id", owner_id).limit(1).execute().data)
    if not rows:
        raise HTTPException(404, "Owned vehicle not found.")
    return rows[0]


def active_device(db, vehicle_id, required=False):
    rows = (db.table("devices").select(DEVICE_COLUMNS).eq("vehicle_id", str(vehicle_id))
            .eq("is_active", True).limit(2).execute().data)
    if len(rows) > 1:
        raise HTTPException(409, "Multiple active devices are bound to this car. Ask the administrator to correct the assignment.")
    if not rows and required:
        raise HTTPException(409, "No active device is bound to this vehicle.")
    return rows[0] if rows else None


def drive_assignment(vehicle_id, user):
    try:
        db = get_supabase_admin()
        owned_vehicle(db, vehicle_id, user)
        return str(active_device(db, vehicle_id, required=True)["id"])
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to verify vehicle assignment.") from None
