"""Device-authenticated recovery/status endpoint; no owner JWT is accepted here."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from httpx import HTTPError
from postgrest.exceptions import APIError
from app.core.database import get_supabase_admin
from app.core.device_security import AuthenticatedDevice, require_device

router = APIRouter(prefix="/api/devices", tags=["Device - Reporting"])


@router.get("/{device_id}/incident-state")
def read_device_incident_state(
    device_id: UUID,
    response: Response,
    device: AuthenticatedDevice = Depends(require_device),
):
    try:
        records = (
            get_supabase_admin().table("incidents")
            .select("id,status,cancellation_deadline,detected_at")
            .eq("device_id", str(device.id))
            .order("detected_at", desc=True).order("id", desc=True)
            .limit(1).execute().data
        )
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to retrieve device incident state.") from None

    now = datetime.now(timezone.utc)
    incident = None
    if records:
        item = records[0]
        remaining = 0.0
        if item["status"] == "cancellation_window" and item.get("cancellation_deadline"):
            deadline = datetime.fromisoformat(
                str(item["cancellation_deadline"]).replace("Z", "+00:00")
            )
            remaining = max(0.0, (deadline - now).total_seconds())
        incident = {
            **item,
            "can_cancel": item["status"] == "cancellation_window" and remaining > 0,
            "remaining_seconds": remaining,
        }
    response.headers["Cache-Control"] = "no-store"
    return {"incident": incident, "server_time": now.isoformat()}
