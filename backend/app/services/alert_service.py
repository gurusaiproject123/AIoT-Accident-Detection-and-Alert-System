"""Hospital notification, response, and escalation service (Section 7).

Implements the business rules assigned to `backend-hospital-alerts` (Victor):
- After an uncancelled 30 second window, select an eligible participating
  hospital using valid location data (`alert_service.route_incident(...)`).
- Set a separate 180 second deadline for hospital acknowledgment.
- Keep acknowledgment distinct from acceptance; neither proves ambulance dispatch.
- Escalate declined or unanswered alerts to an eligible untried hospital.
  Preserve attempts and reasons.
- If location or an eligible destination is unavailable, record the unresolved
  routing state; do not invent a destination.
- Notify all signed-in staff of the assigned hospital and update the superuser
  monitoring view via the shared live WebSocket channel.
- Coordinate overall incident state via `incident_service.apply_hospital_response(...)`
  when `backend-incidents` is integrated, while providing a safe built-in
  transaction state updater so this module runs and tests independently.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.core.auth import AuthenticatedUser
from app.core.config import get_settings
from app.schemas.alerts import (
    AlertActionResponse,
    HospitalAlertResponse,
    HospitalSummary,
    IncidentAlertContext,
    IncidentLifecycleStatus,
    NotificationStatus,
    OwnerContactSummary,
    RoutingOutcomeResponse,
    RoutingReason,
    VehicleSummary,
)
from app.services.websocket_manager import LiveConnectionManager, live_manager

_DISPLAY_STATUS_MAP: dict[NotificationStatus, str] = {
    "notified": "New",
    "acknowledged": "Acknowledged",
    "accepted": "Accepted",
    "declined": "Declined",
    "timed_out": "Timed out",
    "withdrawn": "Withdrawn",
}


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Compute straight-line Haversine distance in kilometres."""
    r_earth = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return round(r_earth * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a))), 2)


def is_valid_coordinates(lat: float | None, lng: float | None) -> bool:
    """Return True if latitude and longitude are finite and within valid geographic bounds."""
    if lat is None or lng is None:
        return False
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


@dataclass
class HospitalRecord:
    id: UUID
    code: str
    name: str
    city: str = ""
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True


@dataclass
class IncidentRecord:
    id: UUID
    code: str
    device_id: UUID
    device_code: str = "ESP32-UNKNOWN"
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: IncidentLifecycleStatus = "cancellation_window"
    cancellation_window_seconds: int = 30
    cancellation_deadline: datetime | None = None
    cancellation_outcome: str = "pending"
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    model_score: float | None = None
    impact_summary: str | None = None
    vehicle: VehicleSummary | None = None
    owner: OwnerContactSummary | None = None
    owner_id: UUID | None = None
    unresolved_routing_reason: str | None = None


@dataclass
class NotificationRecord:
    id: UUID
    incident_id: UUID
    hospital_id: UUID
    escalation_level: int
    routing_reason: RoutingReason
    routed_by: UUID | None
    distance_km: float | None
    status: NotificationStatus
    notified_at: datetime
    response_deadline: datetime | None
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    responded_at: datetime | None = None
    responded_by: UUID | None = None
    decline_reason: str | None = None


@dataclass
class TimelineEntry:
    incident_id: UUID
    event_type: str
    message: str
    hospital_id: UUID | None
    actor_id: UUID | None
    actor_label: str
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    actor_id: UUID | None
    actor_label: str
    actor_role: str
    category: str
    action: str
    target_id: str
    target_label: str
    detail: str | None
    created_at: datetime


# Hook type for `incident_service.apply_hospital_response(...)` integration (Section 9)
IncidentResponseCallback = Callable[..., None]


class HospitalAlertService:
    """Thread-safe transactional service for hospital alerts, responses, and escalation."""

    def __init__(self, ws_manager: LiveConnectionManager | None = None) -> None:
        self._lock = threading.RLock()
        self._ws_manager = ws_manager or live_manager
        self._hospitals: dict[UUID, HospitalRecord] = {}
        self._incidents: dict[UUID, IncidentRecord] = {}
        self._notifications: dict[UUID, NotificationRecord] = {}
        self._timeline: list[TimelineEntry] = []
        self._audit_logs: list[AuditEntry] = []
        self._incident_response_hook: IncidentResponseCallback | None = None

    # ------------------------------------------------------------------
    # Cross-module integration & fixture helpers
    # ------------------------------------------------------------------

    def set_incident_response_hook(self, hook: IncidentResponseCallback | None) -> None:
        """Register `incident_service.apply_hospital_response` when `backend-incidents` is merged."""
        self._incident_response_hook = hook

    def reset_state(self) -> None:
        """Clear all in-memory records (used by automated test suites)."""
        with self._lock:
            self._hospitals.clear()
            self._incidents.clear()
            self._notifications.clear()
            self._timeline.clear()
            self._audit_logs.clear()

    def register_hospital_fixture(self, hospital: HospitalRecord) -> HospitalRecord:
        """Register or update a hospital record in the store."""
        with self._lock:
            self._hospitals[hospital.id] = hospital
            return hospital

    def register_incident_fixture(self, incident: IncidentRecord) -> IncidentRecord:
        """Register or update an incident record in the store."""
        with self._lock:
            if incident.cancellation_deadline is None:
                incident.cancellation_deadline = incident.detected_at + timedelta(
                    seconds=incident.cancellation_window_seconds
                )
            self._incidents[incident.id] = incident
            return incident

    @property
    def timeline_events(self) -> list[TimelineEntry]:
        with self._lock:
            return list(self._timeline)

    @property
    def audit_entries(self) -> list[AuditEntry]:
        with self._lock:
            return list(self._audit_logs)

    def get_incident(self, incident_id: UUID) -> IncidentRecord | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def list_incident_notifications(self, incident_id: UUID) -> list[HospitalAlertResponse]:
        with self._lock:
            rows = [
                n for n in self._notifications.values() if n.incident_id == incident_id
            ]
            rows.sort(key=lambda r: (r.escalation_level, r.notified_at))
            return [self._serialize_notification(r) for r in rows]

    # ------------------------------------------------------------------
    # Query operations (Section 7)
    # ------------------------------------------------------------------

    def list_hospital_alerts(
        self,
        caller: AuthenticatedUser,
        *,
        status_filter: NotificationStatus | None = None,
    ) -> list[HospitalAlertResponse]:
        """List notifications assigned strictly to the caller's verified hospital.

        Never trusts a hospital_id passed from the browser as authorization.
        """
        if caller.role != "hospital_staff" or caller.hospital_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only hospital staff assigned to a hospital can list hospital alerts.",
            )

        with self._lock:
            assigned_hospital_id = caller.hospital_id
            records = [
                n
                for n in self._notifications.values()
                if n.hospital_id == assigned_hospital_id
                and (status_filter is None or n.status == status_filter)
            ]
            records.sort(key=lambda n: n.notified_at, reverse=True)
            return [self._serialize_notification(n) for n in records]

    def get_authorized_alert(
        self,
        alert_id: UUID,
        caller: AuthenticatedUser,
    ) -> HospitalAlertResponse:
        """Return one notification (`incident_notifications`) if the caller is authorized.

        - Hospital staff may only read alerts assigned to their verified `hospital_id`.
        - Superusers may read any alert.
        - Other roles or staff from another hospital receive 403.
        """
        with self._lock:
            notif = self._notifications.get(alert_id)
            if notif is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Alert notification not found.",
                )
            self._enforce_alert_access(notif, caller, allow_superuser=True)
            return self._serialize_notification(notif)

    # ------------------------------------------------------------------
    # Routing and Escalation (Section 7 & Section 9)
    # ------------------------------------------------------------------

    def select_eligible_hospital(
        self,
        incident: IncidentRecord,
        *,
        exclude_hospital_ids: set[UUID] | None = None,
    ) -> tuple[HospitalRecord | None, float | None, str | None]:
        """Select the nearest active untried hospital with valid coordinates.

        Returns `(hospital, distance_km, unresolved_reason)`.
        If incident coordinates are missing/invalid or no eligible active
        hospital remains, returns `(None, None, reason)` — never invents a destination.
        """
        if not is_valid_coordinates(incident.latitude, incident.longitude):
            return (
                None,
                None,
                "Incident GPS location is unavailable or invalid; cannot select a hospital automatically.",
            )

        tried = set(exclude_hospital_ids or set())
        for n in self._notifications.values():
            if n.incident_id == incident.id:
                tried.add(n.hospital_id)

        candidates: list[tuple[float, str, HospitalRecord]] = []
        for hosp in self._hospitals.values():
            if not hosp.is_active:
                continue
            if hosp.id in tried:
                continue
            if not is_valid_coordinates(hosp.latitude, hosp.longitude):
                continue
            dist = haversine_distance_km(
                float(incident.latitude),
                float(incident.longitude),
                float(hosp.latitude),
                float(hosp.longitude),
            )
            candidates.append((dist, hosp.code, hosp))

        if not candidates:
            return (
                None,
                None,
                "No eligible untried active hospital is available for routing.",
            )

        candidates.sort(key=lambda item: (item[0], item[1]))
        best_dist, _, best_hospital = candidates[0]
        return best_hospital, best_dist, None

    async def route_incident(
        self,
        incident_id: UUID,
        *,
        routing_reason: RoutingReason = "nearest",
        now: datetime | None = None,
        force_after_window: bool = False,
    ) -> RoutingOutcomeResponse:
        """Shared service entry `alert_service.route_incident(...)` (Section 9).

        - Verifies the incident was not cancelled and its 30s cancellation window
          has expired (unless `force_after_window=True` in controlled tests).
        - Idempotent: if an active notification (`notified`, `acknowledged`, or `accepted`)
          already exists for this incident, returns that existing notification
          instead of duplicating routing.
        - Sets a separate 180s hospital acknowledgment deadline.
        - If location or an eligible hospital is unavailable, records the unresolved
          routing state without inventing a destination.
        """
        current_time = now or datetime.now(timezone.utc)
        broadcast_args: dict[str, Any] | None = None

        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Incident not found.",
                )

            if incident.status in ("cancelled", "closed"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incident {incident.code} is already {incident.status} and cannot be routed.",
                )

            if (
                not force_after_window
                and incident.status == "cancellation_window"
                and incident.cancellation_deadline is not None
                and current_time < incident.cancellation_deadline
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot notify hospitals before the 30 second cancellation window expires.",
                )

            # Idempotency check: if an active notification already exists, return it
            existing_active = next(
                (
                    n
                    for n in self._notifications.values()
                    if n.incident_id == incident.id
                    and n.status in ("notified", "acknowledged", "accepted")
                ),
                None,
            )
            if existing_active is not None:
                attempted_ids = [
                    n.hospital_id
                    for n in sorted(
                        (
                            r
                            for r in self._notifications.values()
                            if r.incident_id == incident.id
                        ),
                        key=lambda r: r.escalation_level,
                    )
                ]
                return RoutingOutcomeResponse(
                    incident_id=incident.id,
                    incident_code=incident.code,
                    incident_status=incident.status,
                    resolved=True,
                    reason="Active hospital notification already exists.",
                    alert=self._serialize_notification(existing_active),
                    attempted_hospital_ids=attempted_ids,
                )

            # Transition out of cancellation_window if needed
            if incident.status == "cancellation_window":
                incident.cancellation_outcome = "expired"
                self._record_timeline(
                    incident_id=incident.id,
                    event_type="window_expired",
                    message="30 second cancellation window expired without cancellation.",
                    hospital_id=None,
                    actor_id=None,
                    actor_label="System",
                    created_at=current_time,
                )

            prior_notifications = [
                n for n in self._notifications.values() if n.incident_id == incident.id
            ]
            next_level = (
                max((n.escalation_level for n in prior_notifications), default=0) + 1
            )
            max_level = get_settings().max_escalation_level

            if next_level > max_level:
                unresolved_msg = (
                    f"Maximum automatic escalation level ({max_level}) reached; "
                    "superuser action required."
                )
                return self._record_unresolved_routing(
                    incident, unresolved_msg, current_time
                )

            hospital, distance_km, unresolved_reason = self.select_eligible_hospital(
                incident
            )
            if hospital is None:
                return self._record_unresolved_routing(
                    incident,
                    unresolved_reason
                    or "No eligible hospital available for automatic routing.",
                    current_time,
                )

            notif = self._create_notification_locked(
                incident=incident,
                hospital=hospital,
                escalation_level=next_level,
                routing_reason=routing_reason,
                routed_by=None,
                actor_label="System",
                distance_km=distance_km,
                now=current_time,
            )
            serialized = self._serialize_notification(notif)
            attempted_ids = [
                n.hospital_id
                for n in sorted(
                    (
                        r
                        for r in self._notifications.values()
                        if r.incident_id == incident.id
                    ),
                    key=lambda r: r.escalation_level,
                )
            ]
            broadcast_args = {
                "hospital_id": hospital.id,
                "owner_id": incident.owner_id,
                "event": "alert.created" if next_level == 1 else "alert.escalated",
                "payload": {
                    "incident_id": str(incident.id),
                    "alert_id": str(notif.id),
                    "incident_status": incident.status,
                    "alert": serialized.model_dump(mode="json"),
                },
            }
            outcome = RoutingOutcomeResponse(
                incident_id=incident.id,
                incident_code=incident.code,
                incident_status=incident.status,
                resolved=True,
                reason=f"Assigned to {hospital.name} (level {next_level}).",
                alert=serialized,
                attempted_hospital_ids=attempted_ids,
            )

        if broadcast_args is not None:
            await self._ws_manager.broadcast_hospital_and_admins(**broadcast_args)
        return outcome

    async def manual_notify_hospital(
        self,
        incident_id: UUID,
        hospital_id: UUID,
        caller: AuthenticatedUser,
        *,
        now: datetime | None = None,
    ) -> RoutingOutcomeResponse:
        """Superuser manual routing endpoint `POST /api/admin/incidents/{id}/notify`."""
        if caller.role != "superuser" or caller.hospital_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a superuser can manually route an incident.",
            )

        current_time = now or datetime.now(timezone.utc)
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Incident not found.",
                )
            if incident.status in ("cancelled", "closed"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot route a {incident.status} incident.",
                )

            hospital = self._hospitals.get(hospital_id)
            if hospital is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target hospital not found.",
                )
            if not hospital.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Target hospital is inactive and cannot receive notifications.",
                )

            # Prevent duplicate active notification to the same hospital
            duplicate = next(
                (
                    n
                    for n in self._notifications.values()
                    if n.incident_id == incident.id and n.hospital_id == hospital.id
                ),
                None,
            )
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"{hospital.name} has already been notified for this incident.",
                )

            if any(
                n.status == "accepted"
                for n in self._notifications.values()
                if n.incident_id == incident.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another hospital has already accepted this incident.",
                )

            # Withdraw any currently open notification before manual rerouting
            for open_notif in self._notifications.values():
                if (
                    open_notif.incident_id == incident.id
                    and open_notif.status in ("notified", "acknowledged")
                ):
                    open_notif.status = "withdrawn"

            if incident.status == "cancellation_window":
                incident.cancellation_outcome = "expired"

            prior_notifications = [
                n for n in self._notifications.values() if n.incident_id == incident.id
            ]
            next_level = (
                max((n.escalation_level for n in prior_notifications), default=0) + 1
            )

            distance_km: float | None = None
            if is_valid_coordinates(
                incident.latitude, incident.longitude
            ) and is_valid_coordinates(hospital.latitude, hospital.longitude):
                distance_km = haversine_distance_km(
                    float(incident.latitude),
                    float(incident.longitude),
                    float(hospital.latitude),
                    float(hospital.longitude),
                )

            notif = self._create_notification_locked(
                incident=incident,
                hospital=hospital,
                escalation_level=next_level,
                routing_reason="manual",
                routed_by=caller.id,
                actor_label=caller.full_name or "Superuser",
                distance_km=distance_km,
                now=current_time,
            )
            serialized = self._serialize_notification(notif)
            attempted_ids = [
                n.hospital_id
                for n in sorted(
                    (
                        r
                        for r in self._notifications.values()
                        if r.incident_id == incident.id
                    ),
                    key=lambda r: r.escalation_level,
                )
            ]

        await self._ws_manager.broadcast_hospital_and_admins(
            hospital_id=hospital.id,
            owner_id=incident.owner_id,
            event="alert.routed_manually",
            payload={
                "incident_id": str(incident.id),
                "alert_id": str(notif.id),
                "incident_status": incident.status,
                "alert": serialized.model_dump(mode="json"),
            },
        )

        return RoutingOutcomeResponse(
            incident_id=incident.id,
            incident_code=incident.code,
            incident_status=incident.status,
            resolved=True,
            reason=f"Manually routed to {hospital.name} (level {next_level}).",
            alert=serialized,
            attempted_hospital_ids=attempted_ids,
        )

    # ------------------------------------------------------------------
    # Hospital staff response actions (Acknowledge / Accept / Decline)
    # ------------------------------------------------------------------

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        caller: AuthenticatedUser,
        *,
        now: datetime | None = None,
    ) -> AlertActionResponse:
        """Confirm receipt of an assigned hospital alert (`POST /api/alerts/{id}/acknowledge`).

        - Only staff assigned to that alert's hospital may acknowledge it.
        - Acknowledgment confirms receipt; it does NOT automatically accept the response.
        - Idempotent if already acknowledged by another staff member at the same hospital.
        - Rejects if the 180s acknowledgment deadline has already expired.
        """
        current_time = now or datetime.now(timezone.utc)
        should_escalate = False

        with self._lock:
            notif = self._get_notification_for_staff_locked(alert_id, caller)
            incident = self._incidents[notif.incident_id]
            hospital = self._hospitals[notif.hospital_id]

            if incident.status in ("cancelled", "closed"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incident {incident.code} is already {incident.status}.",
                )

            # Idempotent repeat acknowledgment by another staff member at the same hospital
            if notif.status == "acknowledged":
                return AlertActionResponse(
                    alert=self._serialize_notification(notif),
                    incident_status=incident.status,
                    escalation=None,
                )

            if notif.status != "notified":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Alert in status '{notif.status}' cannot be acknowledged.",
                )

            if (
                notif.response_deadline is not None
                and current_time > notif.response_deadline
            ):
                # Deadline already passed -> mark timed_out and escalate
                notif.status = "timed_out"
                self._record_timeline(
                    incident_id=incident.id,
                    event_type="timed_out",
                    message=f"No acknowledgment from {hospital.name} within {get_settings().hospital_ack_timeout_seconds} seconds.",
                    hospital_id=hospital.id,
                    actor_id=None,
                    actor_label="System",
                    created_at=current_time,
                )
                should_escalate = True
            else:
                notif.status = "acknowledged"
                notif.acknowledged_at = current_time
                notif.acknowledged_by = caller.id
                # Clear response_deadline once acknowledged (matches hospital frontend contract)
                notif.response_deadline = None

                self._apply_incident_response_locked(
                    incident=incident,
                    notification=notif,
                    new_incident_status="acknowledged",
                    actor=caller,
                    now=current_time,
                )

                self._record_timeline(
                    incident_id=incident.id,
                    event_type="acknowledged",
                    message=f"{hospital.name} acknowledged receipt of the alert.",
                    hospital_id=hospital.id,
                    actor_id=caller.id,
                    actor_label=caller.full_name or "Hospital staff",
                    created_at=current_time,
                )
                self._record_audit(
                    caller=caller,
                    category="incident",
                    action="Acknowledged alert",
                    target_id=str(incident.id),
                    target_label=incident.code,
                    detail=f"{hospital.name} acknowledged receipt.",
                    now=current_time,
                )
                serialized = self._serialize_notification(notif)

        if should_escalate:
            await self.route_incident(
                incident.id, routing_reason="timeout", now=current_time, force_after_window=True
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The 180 second acknowledgment window has expired and the alert was escalated.",
            )

        await self._ws_manager.broadcast_hospital_and_admins(
            hospital_id=notif.hospital_id,
            owner_id=incident.owner_id,
            event="alert.acknowledged",
            payload={
                "incident_id": str(incident.id),
                "alert_id": str(notif.id),
                "incident_status": incident.status,
                "alert": serialized.model_dump(mode="json"),
            },
        )

        return AlertActionResponse(
            alert=serialized,
            incident_status=incident.status,
            escalation=None,
        )

    async def accept_alert(
        self,
        alert_id: UUID,
        caller: AuthenticatedUser,
        *,
        now: datetime | None = None,
    ) -> AlertActionResponse:
        """Record willingness to respond (`POST /api/alerts/{id}/accept`).

        - Requires the alert to be `acknowledged` first (acknowledgment is distinct from acceptance).
        - Idempotent if already `accepted` by the same hospital.
        """
        current_time = now or datetime.now(timezone.utc)

        with self._lock:
            notif = self._get_notification_for_staff_locked(alert_id, caller)
            incident = self._incidents[notif.incident_id]
            hospital = self._hospitals[notif.hospital_id]

            if incident.status in ("cancelled", "closed"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incident {incident.code} is already {incident.status}.",
                )

            if notif.status == "accepted":
                return AlertActionResponse(
                    alert=self._serialize_notification(notif),
                    incident_status=incident.status,
                    escalation=None,
                )

            if notif.status == "notified":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Alert must be acknowledged before it can be accepted.",
                )

            if notif.status != "acknowledged":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Alert in status '{notif.status}' cannot be accepted.",
                )

            if any(
                other.status == "accepted" and other.id != notif.id
                for other in self._notifications.values()
                if other.incident_id == incident.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another hospital has already accepted this incident.",
                )

            notif.status = "accepted"
            notif.responded_at = current_time
            notif.responded_by = caller.id

            # Withdraw any other open notifications for this incident
            for other in self._notifications.values():
                if (
                    other.incident_id == incident.id
                    and other.id != notif.id
                    and other.status in ("notified", "acknowledged")
                ):
                    other.status = "withdrawn"

            self._apply_incident_response_locked(
                incident=incident,
                notification=notif,
                new_incident_status="accepted",
                actor=caller,
                now=current_time,
            )

            self._record_timeline(
                incident_id=incident.id,
                event_type="accepted",
                message=f"{hospital.name} accepted the response.",
                hospital_id=hospital.id,
                actor_id=caller.id,
                actor_label=caller.full_name or "Hospital staff",
                created_at=current_time,
            )
            self._record_audit(
                caller=caller,
                category="incident",
                action="Accepted response",
                target_id=str(incident.id),
                target_label=incident.code,
                detail=f"{hospital.name} accepted the emergency response.",
                now=current_time,
            )
            serialized = self._serialize_notification(notif)

        await self._ws_manager.broadcast_hospital_and_admins(
            hospital_id=notif.hospital_id,
            owner_id=incident.owner_id,
            event="alert.accepted",
            payload={
                "incident_id": str(incident.id),
                "alert_id": str(notif.id),
                "incident_status": incident.status,
                "alert": serialized.model_dump(mode="json"),
            },
        )

        return AlertActionResponse(
            alert=serialized,
            incident_status=incident.status,
            escalation=None,
        )

    async def decline_alert(
        self,
        alert_id: UUID,
        reason: str,
        caller: AuthenticatedUser,
        *,
        now: datetime | None = None,
    ) -> AlertActionResponse:
        """Decline an alert with a mandatory reason and escalate once (`POST /api/alerts/{id}/decline`).

        - Requires a non-empty reason.
        - Requires the alert to have been acknowledged first (per Hospital Dashboard spec:
          "Decline with a mandatory reason after acknowledgment").
        - Idempotent on retries: if this alert was already declined, returns the existing
          state and current escalation outcome without creating duplicate routing.
        """
        cleaned_reason = reason.strip()
        if not cleaned_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A decline reason is required.",
            )

        current_time = now or datetime.now(timezone.utc)
        already_declined = False

        with self._lock:
            notif = self._get_notification_for_staff_locked(alert_id, caller)
            incident = self._incidents[notif.incident_id]
            hospital = self._hospitals[notif.hospital_id]

            if incident.status in ("cancelled", "closed"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incident {incident.code} is already {incident.status}.",
                )

            if notif.status == "declined":
                already_declined = True
                serialized = self._serialize_notification(notif)
            elif notif.status == "notified":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Alert must be acknowledged before it can be declined.",
                )
            elif notif.status != "acknowledged":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Alert in status '{notif.status}' cannot be declined.",
                )
            else:
                notif.status = "declined"
                notif.responded_at = current_time
                notif.responded_by = caller.id
                notif.decline_reason = cleaned_reason

                self._record_timeline(
                    incident_id=incident.id,
                    event_type="declined",
                    message=f"{hospital.name} declined: {cleaned_reason}",
                    hospital_id=hospital.id,
                    actor_id=caller.id,
                    actor_label=caller.full_name or "Hospital staff",
                    created_at=current_time,
                )
                self._record_audit(
                    caller=caller,
                    category="incident",
                    action="Declined response",
                    target_id=str(incident.id),
                    target_label=incident.code,
                    detail=f"{hospital.name}: {cleaned_reason}",
                    now=current_time,
                )
                serialized = self._serialize_notification(notif)

        if already_declined:
            # Idempotent retry: do not create a second escalation
            existing_next = next(
                (
                    n
                    for n in sorted(
                        (
                            r
                            for r in self._notifications.values()
                            if r.incident_id == incident.id
                            and r.escalation_level > notif.escalation_level
                        ),
                        key=lambda r: r.escalation_level,
                    )
                ),
                None,
            )
            attempted_ids = [
                n.hospital_id
                for n in sorted(
                    (r for r in self._notifications.values() if r.incident_id == incident.id),
                    key=lambda r: r.escalation_level,
                )
            ]
            escalation = RoutingOutcomeResponse(
                incident_id=incident.id,
                incident_code=incident.code,
                incident_status=incident.status,
                resolved=existing_next is not None,
                reason="Decline already processed.",
                alert=self._serialize_notification(existing_next) if existing_next else None,
                attempted_hospital_ids=attempted_ids,
            )
            return AlertActionResponse(
                alert=serialized,
                incident_status=incident.status,
                escalation=escalation,
            )

        await self._ws_manager.broadcast_hospital_and_admins(
            hospital_id=notif.hospital_id,
            owner_id=incident.owner_id,
            event="alert.declined",
            payload={
                "incident_id": str(incident.id),
                "alert_id": str(notif.id),
                "incident_status": incident.status,
                "reason": cleaned_reason,
                "alert": serialized.model_dump(mode="json"),
            },
        )

        escalation = await self.route_incident(
            incident.id,
            routing_reason="declined",
            now=current_time,
            force_after_window=True,
        )

        return AlertActionResponse(
            alert=serialized,
            incident_status=self._incidents[incident.id].status,
            escalation=escalation,
        )

    # ------------------------------------------------------------------
    # Durable deadline worker processing (Section 7)
    # ------------------------------------------------------------------

    async def process_due_deadlines(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Process expired 30s cancellation windows and 180s hospital acknowledgment deadlines.

        Safe to run repeatedly and across worker restarts because deadlines are stored
        as absolute timestamps on the incident and notification records.
        """
        current_time = now or datetime.now(timezone.utc)
        windows_routed: list[UUID] = []
        timed_out_alerts: list[UUID] = []
        escalations: list[RoutingOutcomeResponse] = []

        # 1. Find incidents whose 30s cancellation window has expired
        with self._lock:
            due_incidents = [
                inc.id
                for inc in self._incidents.values()
                if inc.status == "cancellation_window"
                and inc.cancellation_deadline is not None
                and current_time >= inc.cancellation_deadline
            ]

        for inc_id in due_incidents:
            outcome = await self.route_incident(
                inc_id, routing_reason="nearest", now=current_time, force_after_window=True
            )
            windows_routed.append(inc_id)
            escalations.append(outcome)

        # 2. Find unacknowledged notifications whose 180s response_deadline has expired
        timed_out_incidents: list[ tuple[UUID, UUID, HospitalAlertResponse] ] = []
        with self._lock:
            for notif in list(self._notifications.values()):
                if (
                    notif.status == "notified"
                    and notif.response_deadline is not None
                    and current_time >= notif.response_deadline
                ):
                    incident = self._incidents[notif.incident_id]
                    if incident.status in ("cancelled", "closed"):
                        notif.status = "withdrawn"
                        continue
                    hospital = self._hospitals[notif.hospital_id]
                    notif.status = "timed_out"
                    self._record_timeline(
                        incident_id=incident.id,
                        event_type="timed_out",
                        message=(
                            f"No acknowledgment from {hospital.name} within "
                            f"{get_settings().hospital_ack_timeout_seconds} seconds."
                        ),
                        hospital_id=hospital.id,
                        actor_id=None,
                        actor_label="System",
                        created_at=current_time,
                    )
                    self._record_audit(
                        caller=None,
                        category="incident",
                        action="Alert timed out",
                        target_id=str(incident.id),
                        target_label=incident.code,
                        detail=f"No acknowledgment from {hospital.name} before deadline.",
                        now=current_time,
                    )
                    timed_out_alerts.append(notif.id)
                    timed_out_incidents.append(
                        (incident.id, notif.hospital_id, self._serialize_notification(notif))
                    )

        for inc_id, old_hosp_id, serialized_timeout in timed_out_incidents:
            inc = self._incidents[inc_id]
            await self._ws_manager.broadcast_hospital_and_admins(
                hospital_id=old_hosp_id,
                owner_id=inc.owner_id,
                event="alert.timed_out",
                payload={
                    "incident_id": str(inc_id),
                    "alert_id": str(serialized_timeout.id),
                    "alert": serialized_timeout.model_dump(mode="json"),
                },
            )
            outcome = await self.route_incident(
                inc_id,
                routing_reason="timeout",
                now=current_time,
                force_after_window=True,
            )
            escalations.append(outcome)

        return {
            "processed_at": current_time.isoformat(),
            "windows_routed": [str(i) for i in windows_routed],
            "timed_out_alerts": [str(a) for a in timed_out_alerts],
            "escalations": [e.model_dump(mode="json") for e in escalations],
        }

    # ------------------------------------------------------------------
    # Internal helpers (must be called under self._lock)
    # ------------------------------------------------------------------

    def _enforce_alert_access(
        self,
        notif: NotificationRecord,
        caller: AuthenticatedUser,
        *,
        allow_superuser: bool,
    ) -> None:
        if allow_superuser and caller.role == "superuser" and caller.hospital_id is None:
            return
        if (
            caller.role == "hospital_staff"
            and caller.hospital_id is not None
            and caller.hospital_id == notif.hospital_id
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access alerts for this hospital.",
        )

    def _get_notification_for_staff_locked(
        self,
        alert_id: UUID,
        caller: AuthenticatedUser,
    ) -> NotificationRecord:
        if caller.role != "hospital_staff" or caller.hospital_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Hospital staff access is required for alert response actions.",
            )
        notif = self._notifications.get(alert_id)
        if notif is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert notification not found.",
            )
        self._enforce_alert_access(notif, caller, allow_superuser=False)
        return notif

    def _create_notification_locked(
        self,
        *,
        incident: IncidentRecord,
        hospital: HospitalRecord,
        escalation_level: int,
        routing_reason: RoutingReason,
        routed_by: UUID | None,
        actor_label: str,
        distance_km: float | None,
        now: datetime,
    ) -> NotificationRecord:
        ack_timeout = get_settings().hospital_ack_timeout_seconds
        notif = NotificationRecord(
            id=uuid4(),
            incident_id=incident.id,
            hospital_id=hospital.id,
            escalation_level=escalation_level,
            routing_reason=routing_reason,
            routed_by=routed_by,
            distance_km=distance_km,
            status="notified",
            notified_at=now,
            response_deadline=now + timedelta(seconds=ack_timeout),
        )
        self._notifications[notif.id] = notif
        incident.unresolved_routing_reason = None

        new_inc_status: IncidentLifecycleStatus = (
            "escalated" if escalation_level > 1 else "notified"
        )
        self._apply_incident_response_locked(
            incident=incident,
            notification=notif,
            new_incident_status=new_inc_status,
            actor=None,
            now=now,
        )

        event_type = "escalated" if escalation_level > 1 else "notified"
        if routing_reason == "manual":
            msg = f"Manually routed to {hospital.name} (level {escalation_level})."
        elif escalation_level > 1:
            msg = f"Escalated to {hospital.name} (level {escalation_level}, reason: {routing_reason})."
        else:
            msg = f"{hospital.name} notified (nearest active hospital)."

        self._record_timeline(
            incident_id=incident.id,
            event_type=event_type,
            message=msg,
            hospital_id=hospital.id,
            actor_id=routed_by,
            actor_label=actor_label,
            created_at=now,
            metadata={
                "escalation_level": escalation_level,
                "routing_reason": routing_reason,
                "distance_km": distance_km,
            },
        )
        self._record_audit(
            caller=None,
            actor_id_override=routed_by,
            actor_label_override=actor_label,
            actor_role_override="superuser" if routed_by else "system",
            category="incident",
            action="Routed incident" if routing_reason == "manual" else "Notified hospital",
            target_id=str(incident.id),
            target_label=incident.code,
            detail=msg,
            now=now,
        )
        return notif

    def _record_unresolved_routing(
        self,
        incident: IncidentRecord,
        reason: str,
        now: datetime,
    ) -> RoutingOutcomeResponse:
        incident.status = "escalated"
        incident.unresolved_routing_reason = reason
        self._record_timeline(
            incident_id=incident.id,
            event_type="escalated",
            message=f"Unresolved routing: {reason}",
            hospital_id=None,
            actor_id=None,
            actor_label="System",
            created_at=now,
            metadata={"reason": "unresolved_routing", "detail": reason},
        )
        self._record_audit(
            caller=None,
            category="incident",
            action="Routing unresolved",
            target_id=str(incident.id),
            target_label=incident.code,
            detail=reason,
            now=now,
        )
        attempted_ids = [
            n.hospital_id
            for n in sorted(
                (r for r in self._notifications.values() if r.incident_id == incident.id),
                key=lambda r: r.escalation_level,
            )
        ]
        return RoutingOutcomeResponse(
            incident_id=incident.id,
            incident_code=incident.code,
            incident_status=incident.status,
            resolved=False,
            reason=reason,
            alert=None,
            attempted_hospital_ids=attempted_ids,
        )

    def _apply_incident_response_locked(
        self,
        *,
        incident: IncidentRecord,
        notification: NotificationRecord,
        new_incident_status: IncidentLifecycleStatus,
        actor: AuthenticatedUser | None,
        now: datetime,
    ) -> None:
        """Update overall incident state and notify `incident_service.apply_hospital_response` if wired."""
        if incident.status not in ("cancelled", "closed"):
            if new_incident_status == "acknowledged" and incident.status == "accepted":
                pass
            else:
                incident.status = new_incident_status

        if self._incident_response_hook is not None:
            self._incident_response_hook(
                incident_id=incident.id,
                notification_id=notification.id,
                hospital_id=notification.hospital_id,
                notification_status=notification.status,
                incident_status=incident.status,
                actor_id=actor.id if actor else None,
                timestamp=now,
            )

    def _record_timeline(
        self,
        *,
        incident_id: UUID,
        event_type: str,
        message: str,
        hospital_id: UUID | None,
        actor_id: UUID | None,
        actor_label: str,
        created_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._timeline.append(
            TimelineEntry(
                incident_id=incident_id,
                event_type=event_type,
                message=message,
                hospital_id=hospital_id,
                actor_id=actor_id,
                actor_label=actor_label,
                created_at=created_at,
                metadata=metadata or {},
            )
        )

    def _record_audit(
        self,
        *,
        caller: AuthenticatedUser | None,
        category: str,
        action: str,
        target_id: str,
        target_label: str,
        detail: str | None,
        now: datetime,
        actor_id_override: UUID | None = None,
        actor_label_override: str | None = None,
        actor_role_override: str | None = None,
    ) -> None:
        actor_id = caller.id if caller else actor_id_override
        actor_label = (
            (caller.full_name or "Authorized user")
            if caller
            else (actor_label_override or "System")
        )
        actor_role = caller.role if caller else (actor_role_override or "system")
        self._audit_logs.append(
            AuditEntry(
                actor_id=actor_id,
                actor_label=actor_label,
                actor_role=actor_role,
                category=category,
                action=action,
                target_id=target_id,
                target_label=target_label,
                detail=detail,
                created_at=now,
            )
        )

    def _serialize_notification(self, notif: NotificationRecord) -> HospitalAlertResponse:
        hosp = self._hospitals.get(notif.hospital_id)
        inc = self._incidents.get(notif.incident_id)
        hosp_summary = (
            HospitalSummary(
                id=hosp.id,
                code=hosp.code,
                name=hosp.name,
                city=hosp.city,
                latitude=hosp.latitude,
                longitude=hosp.longitude,
                is_active=hosp.is_active,
            )
            if hosp
            else None
        )
        inc_context = (
            IncidentAlertContext(
                id=inc.id,
                code=inc.code,
                device_id=inc.device_id,
                device_code=inc.device_code,
                detected_at=inc.detected_at,
                status=inc.status,
                latitude=inc.latitude,
                longitude=inc.longitude,
                location_label=inc.location_label,
                location_available=is_valid_coordinates(inc.latitude, inc.longitude),
                model_score=inc.model_score,
                impact_summary=inc.impact_summary,
                vehicle=inc.vehicle,
                owner=inc.owner,
            )
            if inc
            else None
        )
        display_status = _DISPLAY_STATUS_MAP[notif.status]
        return HospitalAlertResponse(
            id=notif.id,
            incident_id=notif.incident_id,
            hospital_id=notif.hospital_id,
            hospital=hosp_summary,
            escalation_level=notif.escalation_level,
            routing_reason=notif.routing_reason,
            routed_by=notif.routed_by,
            distance_km=notif.distance_km,
            status=notif.status,
            hospital_display_status=display_status,  # type: ignore[arg-type]
            notified_at=notif.notified_at,
            response_deadline=notif.response_deadline,
            acknowledged_at=notif.acknowledged_at,
            acknowledged_by=notif.acknowledged_by,
            responded_at=notif.responded_at,
            responded_by=notif.responded_by,
            decline_reason=notif.decline_reason,
            incident=inc_context,
        )


# Shared singleton instance imported as `alert_service` across backend modules (Section 9)
alert_service = HospitalAlertService()

