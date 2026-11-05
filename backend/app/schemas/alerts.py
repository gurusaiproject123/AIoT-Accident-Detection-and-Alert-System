"""Pydantic request and response schemas for Section 7: Hospital Alerts & Live Updates.

All alert IDs represent rows in `public.incident_notifications` (not `incidents`).
One incident may have several historical hospital notification records across
escalation levels.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

NotificationStatus = Literal[
    "notified",
    "acknowledged",
    "accepted",
    "declined",
    "timed_out",
    "withdrawn",
]

RoutingReason = Literal["nearest", "timeout", "declined", "manual"]

IncidentLifecycleStatus = Literal[
    "cancellation_window",
    "cancelled",
    "notified",
    "escalated",
    "acknowledged",
    "accepted",
    "closed",
]


class AlertDeclineRequest(BaseModel):
    """Request payload for POST /api/alerts/{id}/decline."""

    reason: str = Field(..., min_length=1, max_length=500, description="Mandatory decline reason.")

    @field_validator("reason")
    @classmethod
    def _validate_non_blank_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A non-empty decline reason is required.")
        return cleaned


class ManualNotifyRequest(BaseModel):
    """Request payload for POST /api/admin/incidents/{id}/notify."""

    hospital_id: UUID = Field(..., description="Target active hospital UUID.")


class VehicleSummary(BaseModel):
    """Vehicle information attached to an incident alert when authorized."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    registration: str
    make: str | None = None
    model: str | None = None
    colour: str | None = None


class OwnerContactSummary(BaseModel):
    """Registered owner contact information attached to an assigned incident alert."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    full_name: str
    phone: str | None = None
    email: str | None = None
    relationship: str = "Registered owner"


class HospitalSummary(BaseModel):
    """Hospital metadata attached to a notification record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_active: bool = True


class IncidentAlertContext(BaseModel):
    """Incident details embedded inside an authorized hospital alert response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    device_id: UUID
    device_code: str | None = None
    detected_at: datetime
    status: IncidentLifecycleStatus
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    location_available: bool = True
    model_score: float | None = None
    impact_summary: str | None = None
    vehicle: VehicleSummary | None = None
    owner: OwnerContactSummary | None = None


class HospitalAlertResponse(BaseModel):
    """Serialized `incident_notifications` record with authorized incident context."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="UUID of the incident_notifications record (alert_id).")
    incident_id: UUID
    hospital_id: UUID
    hospital: HospitalSummary | None = None
    escalation_level: int = Field(..., ge=1)
    routing_reason: RoutingReason
    routed_by: UUID | None = None
    distance_km: float | None = None

    status: NotificationStatus
    hospital_display_status: Literal[
        "New", "Acknowledged", "Accepted", "Declined", "Timed out", "Withdrawn"
    ]
    notified_at: datetime
    response_deadline: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    responded_at: datetime | None = None
    responded_by: UUID | None = None
    decline_reason: str | None = None

    incident: IncidentAlertContext | None = None


class RoutingOutcomeResponse(BaseModel):
    """Result of routing or escalating an incident."""

    incident_id: UUID
    incident_code: str
    incident_status: IncidentLifecycleStatus
    resolved: bool
    reason: str
    alert: HospitalAlertResponse | None = None
    attempted_hospital_ids: list[UUID] = Field(default_factory=list)


class AlertActionResponse(BaseModel):
    """Response returned when an alert is acknowledged, accepted, or declined."""

    alert: HospitalAlertResponse
    incident_status: IncidentLifecycleStatus
    escalation: RoutingOutcomeResponse | None = None


class LiveSocketEvent(BaseModel):
    """Structured event broadcast over the authenticated `/api/ws` channel."""

    event: str
    timestamp: datetime
    incident_id: UUID | None = None
    hospital_id: UUID | None = None
    alert_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)

