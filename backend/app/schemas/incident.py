from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IncidentStatus = Literal[
    "cancellation_window",
    "cancelled",
    "notified",
    "escalated",
    "acknowledged",
    "accepted",
    "closed",
]

CancellationOutcome = Literal[
    "pending",
    "expired",
    "cancelled",
]

GpsStatus = Literal[
    "fix",
    "stale",
    "none",
]

IncidentEventType = Literal[
    "detected",
    "window_started",
    "window_expired",
    "cancelled",
    "notified",
    "acknowledged",
    "accepted",
    "declined",
    "timed_out",
    "escalated",
    "false_alarm_reported",
    "note",
    "closed",
]

NotificationStatus = Literal[
    "notified",
    "acknowledged",
    "accepted",
    "declined",
    "timed_out",
    "withdrawn",
]

FalseAlarmReviewStatus = Literal[
    "open",
    "confirmed_false_alarm",
    "rejected",
]


class DetectionIncidentCreate(BaseModel):
    """Internal payload passed by the detection service to create an incident."""

    model_config = ConfigDict(extra="forbid")

    device_id: UUID
    vehicle_id: UUID | None = None
    prediction_id: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    detected_at: datetime | None = None
    occurred_at: datetime | None = None
    occurred_at_estimated: bool = False
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    location_label: str | None = Field(default=None, max_length=240)
    location_recorded_at: datetime | None = None
    location_accuracy_m: float | None = Field(default=None, ge=0.0)
    model_score: float | None = Field(default=None, ge=0.0, le=1.0)
    impact_summary: str | None = Field(default=None, max_length=500)
    cancellation_window_seconds: int = Field(default=30, ge=5, le=600)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> "DetectionIncidentCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "Both latitude and longitude must be provided together or omitted."
            )
        return self


class HospitalResponseUpdate(BaseModel):
    """Internal payload passed by alert_service when a hospital notification changes."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    hospital_id: UUID
    notification_id: UUID | None = None
    status: Literal[
        "notified",
        "acknowledged",
        "accepted",
        "declined",
        "timed_out",
        "escalated",
    ]
    escalation_level: int = Field(default=1, ge=1)
    routing_reason: Literal["nearest", "timeout", "declined", "manual"] = "nearest"
    actor_id: UUID | None = None
    actor_label: str | None = None
    actor_role: str = "hospital_staff"
    decline_reason: str | None = None
    distance_km: float | None = Field(default=None, ge=0.0)
    response_deadline: datetime | None = None


class IncidentCancelRequest(BaseModel):
    """Request body for owner or device false-alarm cancellation."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional explanation for cancelling during the 30s window.",
    )

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class IncidentNoteCreate(BaseModel):
    """Request body for adding an operational note to an incident."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Note body must not be blank.")
        if len(cleaned) > 2000:
            raise ValueError("Note body must not exceed 2000 characters.")
        return cleaned


class FalseAlarmReportCreate(BaseModel):
    """Request body for an assigned hospital to submit a false-alarm review report."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError(
                "False-alarm report reason must be at least 3 non-whitespace characters."
            )
        if len(cleaned) > 1000:
            raise ValueError(
                "False-alarm report reason must not exceed 1000 characters."
            )
        return cleaned


class IncidentCloseRequest(BaseModel):
    """Request body for responder or superuser incident closure."""

    model_config = ConfigDict(extra="forbid")

    closing_note: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)
    outcome: Literal[
        "resolved",
        "confirmed_false_alarm",
        "rejected_false_alarm",
        "Duplicate / test",
        "other",
    ] | str | None = Field(default=None, max_length=200)

    @field_validator("closing_note", "note", "outcome")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    def resolved_closing_note(self) -> str | None:
        note_text = self.closing_note or self.note
        if self.outcome and note_text:
            return f"[{self.outcome}] {note_text}"
        if self.outcome:
            return f"Outcome: {self.outcome}"
        return note_text


class IncidentTimelineEvent(BaseModel):
    id: int
    incident_id: UUID
    event_type: IncidentEventType
    message: str
    hospital_id: UUID | None = None
    actor_id: UUID | None = None
    actor_label: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class IncidentTimelineResponse(BaseModel):
    incident_id: UUID
    items: list[IncidentTimelineEvent]
    total: int


class IncidentNoteResponse(BaseModel):
    id: UUID
    incident_id: UUID
    hospital_id: UUID | None = None
    author_id: UUID | None = None
    author_label: str
    body: str
    created_at: datetime


class FalseAlarmReportResponse(BaseModel):
    id: UUID
    incident_id: UUID
    hospital_id: UUID | None = None
    reported_by: UUID | None = None
    reason: str
    review_status: FalseAlarmReviewStatus
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime


class IncidentNotificationSummary(BaseModel):
    id: UUID
    incident_id: UUID
    hospital_id: UUID
    hospital_name: str | None = None
    escalation_level: int
    routing_reason: str
    distance_km: float | None = None
    status: NotificationStatus
    notified_at: datetime
    response_deadline: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    responded_at: datetime | None = None
    responded_by: UUID | None = None
    decline_reason: str | None = None


class IncidentSummaryResponse(BaseModel):
    id: UUID
    code: str
    device_id: UUID
    vehicle_id: UUID | None = None
    prediction_id: int | None = None
    detected_at: datetime
    occurred_at: datetime | None = None
    occurred_at_estimated: bool = False
    latitude: float | None = None
    longitude: float | None = None
    location_label: str | None = None
    location_recorded_at: datetime | None = None
    location_accuracy_m: float | None = None
    gps_status: GpsStatus
    location_available: bool
    location_stale: bool
    location_status_label: str
    model_score: float | None = None
    impact_summary: str | None = None
    status: IncidentStatus
    cancellation_window_seconds: int
    cancellation_deadline: datetime | None = None
    cancellation_outcome: CancellationOutcome
    cancellation_resolved_at: datetime | None = None
    cancelled_by: UUID | None = None
    cancelled_by_label: str | None = None
    cancel_reason: str | None = None
    closed_at: datetime | None = None
    closed_by: UUID | None = None
    closing_note: str | None = None
    created_at: datetime
    updated_at: datetime


class IncidentDetailResponse(IncidentSummaryResponse):
    notifications: list[IncidentNotificationSummary] = Field(default_factory=list)
    notes: list[IncidentNoteResponse] = Field(default_factory=list)
    false_alarm_reports: list[FalseAlarmReportResponse] = Field(default_factory=list)


class IncidentListResponse(BaseModel):
    items: list[IncidentSummaryResponse]
    total: int
    limit: int
    offset: int

