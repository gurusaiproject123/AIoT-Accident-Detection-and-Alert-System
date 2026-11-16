"""Read the durable notifications created by the database deadline worker."""
import asyncio
import logging
from uuid import UUID

from fastapi import HTTPException
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.auth import AuthenticatedUser
from app.core.database import get_supabase_admin
from app.schemas.alerts import AlertActionResponse, HospitalAlertResponse, NotificationStatus

logger = logging.getLogger(__name__)
DISPLAY_STATUS = {
    "notified": "New", "acknowledged": "Acknowledged", "accepted": "Accepted",
    "declined": "Declined", "timed_out": "Timed out", "withdrawn": "Withdrawn",
}
SELECT = "*,hospital:hospitals(*),incident:incidents(*)"


def serialize_alert(row: dict) -> HospitalAlertResponse:
    row = dict(row)
    row["hospital_display_status"] = DISPLAY_STATUS[row["status"]]
    if row.get("incident"):
        incident = dict(row["incident"])
        incident["location_available"] = (
            incident.get("latitude") is not None and incident.get("longitude") is not None
        )
        row["incident"] = incident
    return HospitalAlertResponse.model_validate(row)


class HospitalInbox:
    async def acknowledge_alert(self, alert_id: UUID, caller: AuthenticatedUser):
        return await asyncio.to_thread(self._acknowledge_alert, alert_id, caller)

    def _acknowledge_alert(self, alert_id: UUID, caller: AuthenticatedUser):
        if caller.role != "hospital_staff" or caller.hospital_id is None:
            raise HTTPException(403, "A verified hospital assignment is required.")
        # Check assignment before invoking the transactional database operation.
        self.get_authorized_alert(alert_id, caller)
        try:
            get_supabase_admin().rpc("hospital_acknowledge_notification", {
                "p_actor_id": str(caller.id),
                "p_notification_id": str(alert_id),
            }).execute()
        except APIError as exc:
            errors = {
                "42501": (403, "You are not authorized to acknowledge this notification."),
                "P0002": (404, "Notification not found for your hospital."),
                "23514": (409, "This alert has expired or changed state. Refresh the hospital inbox."),
                "40001": (409, "The notification changed concurrently. Refresh and retry."),
                "40P01": (409, "The notification changed concurrently. Refresh and retry."),
            }
            if exc.code in errors:
                code, message = errors[exc.code]
                raise HTTPException(code, message) from None
            logger.exception("Database hospital acknowledgment failed")
            raise HTTPException(503, "Unable to confirm acknowledgment. Refresh before retrying.") from None
        except HTTPError:
            logger.exception("Database hospital acknowledgment request failed")
            raise HTTPException(503, "Unable to confirm acknowledgment. Refresh before retrying.") from None
        alert = self.get_authorized_alert(alert_id, caller)
        if alert.incident is None:
            raise HTTPException(503, "Acknowledgment processed, but incident details could not be loaded. Refresh the inbox.")
        return AlertActionResponse(alert=alert, incident_status=alert.incident.status)

    def list_hospital_alerts(self, caller: AuthenticatedUser, *, status_filter: NotificationStatus | None = None):
        if caller.role != "hospital_staff" or caller.hospital_id is None:
            raise HTTPException(403, "A verified hospital assignment is required.")
        try:
            db = get_supabase_admin()
            rows = []
            while True:
                query = db.table("incident_notifications").select(SELECT).eq("hospital_id", str(caller.hospital_id))
                if status_filter is not None:
                    query = query.eq("status", status_filter)
                batch = query.order("notified_at", desc=True).order("id").range(len(rows), len(rows) + 99).execute().data or []
                rows.extend(batch)
                if len(batch) < 100:
                    return [serialize_alert(row) for row in rows]
        except (APIError, HTTPError):
            logger.exception("Unable to read hospital inbox")
            raise HTTPException(503, "Unable to load hospital notifications. Please retry.") from None

    def get_authorized_alert(self, alert_id: UUID, caller: AuthenticatedUser):
        if caller.role not in {"hospital_staff", "superuser"} or (
            caller.role == "hospital_staff" and caller.hospital_id is None
        ):
            raise HTTPException(403, "Hospital access is required.")
        try:
            query = get_supabase_admin().table("incident_notifications").select(SELECT).eq("id", str(alert_id))
            if caller.role == "hospital_staff":
                query = query.eq("hospital_id", str(caller.hospital_id))
            rows = query.execute().data or []
        except (APIError, HTTPError):
            logger.exception("Unable to read hospital notification")
            raise HTTPException(503, "Unable to load hospital notification. Please retry.") from None
        if not rows:
            raise HTTPException(404, "Notification not found for your hospital.")
        return serialize_alert(rows[0])


hospital_inbox = HospitalInbox()
