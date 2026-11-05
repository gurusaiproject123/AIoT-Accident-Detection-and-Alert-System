from __future__ import annotations

import copy
import math
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from fastapi import HTTPException
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin
from app.core.device_security import AuthenticatedDevice
from app.schemas.auth import CurrentUser
from app.schemas.incident import (
    DetectionIncidentCreate,
    FalseAlarmReportCreate,
    HospitalResponseUpdate,
    IncidentCancelRequest,
    IncidentCloseRequest,
    IncidentNoteCreate,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime | str | None, fallback: datetime | None = None) -> datetime | None:
    if dt is None:
        return fallback
    if isinstance(dt, str):
        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_earth = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.asin(math.sqrt(max(0.0, min(1.0, a))))
    return round(r_earth * c, 2)


def compute_location_metadata(
    latitude: float | None,
    longitude: float | None,
    location_recorded_at: datetime | str | None,
    reference_time: datetime | str | None = None,
    stale_after_seconds: int = 120,
) -> dict[str, Any]:
    """Compute honest GPS freshness metadata without inventing missing coordinates."""

    if latitude is None or longitude is None:
        return {
            "gps_status": "none",
            "location_available": False,
            "location_stale": False,
            "location_status_label": "GPS location unavailable",
        }

    ref_dt = _ensure_utc(reference_time) or _utc_now()
    rec_dt = _ensure_utc(location_recorded_at)

    if rec_dt is None:
        return {
            "gps_status": "stale",
            "location_available": True,
            "location_stale": True,
            "location_status_label": "GPS timestamp missing; location marked stale",
        }

    age_seconds = (ref_dt - rec_dt).total_seconds()
    if age_seconds > stale_after_seconds:
        return {
            "gps_status": "stale",
            "location_available": True,
            "location_stale": True,
            "location_status_label": (
                f"Stale GPS location (recorded {int(age_seconds)}s before detection)"
            ),
        }

    return {
        "gps_status": "fix",
        "location_available": True,
        "location_stale": False,
        "location_status_label": "Valid GPS fix",
    }


class IncidentService:
    """Single owner of incident lifecycle transitions, cancellation, and history."""

    def __init__(self, use_memory_store: bool = False) -> None:
        self._lock = threading.RLock()
        self._use_memory_store = use_memory_store
        self._alert_router_callback: Callable[[dict[str, Any]], Any] | None = None
        self.reset_memory_store()

    def enable_memory_store(self, enabled: bool = True) -> None:
        with self._lock:
            self._use_memory_store = enabled

    def register_alert_router(
        self, callback: Callable[[dict[str, Any]], Any] | None
    ) -> None:
        with self._lock:
            self._alert_router_callback = callback

    def reset_memory_store(self) -> None:
        with self._lock:
            self._incident_seq = 1001
            self._event_seq = 1
            self._audit_seq = 1
            self._settings: dict[str, int] = {
                "cancellation_window_seconds": 30,
                "hospital_ack_timeout_seconds": 180,
                "max_escalation_level": 3,
                "gps_stale_after_seconds": 120,
            }
            self._hospitals: dict[UUID, dict[str, Any]] = {}
            self._owners: dict[UUID, dict[str, Any]] = {}
            self._vehicles: dict[UUID, dict[str, Any]] = {}
            self._devices: dict[UUID, dict[str, Any]] = {}
            self._incidents: dict[UUID, dict[str, Any]] = {}
            self._prediction_index: dict[int, UUID] = {}
            self._idempotency_index: dict[str, UUID] = {}
            self._notifications: dict[UUID, dict[str, Any]] = {}
            self._events: list[dict[str, Any]] = []
            self._notes: list[dict[str, Any]] = []
            self._false_alarm_reports: list[dict[str, Any]] = []
            self._audit_logs: list[dict[str, Any]] = []

    def export_durable_state(self) -> dict[str, Any]:
        """Export durable state snapshot so worker restart tests can verify persistence."""
        with self._lock:
            return copy.deepcopy(
                {
                    "incident_seq": self._incident_seq,
                    "event_seq": self._event_seq,
                    "audit_seq": self._audit_seq,
                    "settings": self._settings,
                    "hospitals": self._hospitals,
                    "owners": self._owners,
                    "vehicles": self._vehicles,
                    "devices": self._devices,
                    "incidents": self._incidents,
                    "prediction_index": self._prediction_index,
                    "idempotency_index": self._idempotency_index,
                    "notifications": self._notifications,
                    "events": self._events,
                    "notes": self._notes,
                    "false_alarm_reports": self._false_alarm_reports,
                    "audit_logs": self._audit_logs,
                }
            )

    def restore_durable_state(self, snapshot: dict[str, Any]) -> None:
        """Restore durable state snapshot after a simulated process/worker restart."""
        with self._lock:
            state = copy.deepcopy(snapshot)
            self._incident_seq = state["incident_seq"]
            self._event_seq = state["event_seq"]
            self._audit_seq = state["audit_seq"]
            self._settings = state["settings"]
            self._hospitals = state["hospitals"]
            self._owners = state["owners"]
            self._vehicles = state["vehicles"]
            self._devices = state["devices"]
            self._incidents = state["incidents"]
            self._prediction_index = state["prediction_index"]
            self._idempotency_index = state["idempotency_index"]
            self._notifications = state["notifications"]
            self._events = state["events"]
            self._notes = state["notes"]
            self._false_alarm_reports = state["false_alarm_reports"]
            self._audit_logs = state["audit_logs"]

    # ------------------------------------------------------------------
    # Test / Development Fixture Registration Helpers
    # ------------------------------------------------------------------
    def register_hospital_fixture(
        self,
        hospital_id: UUID,
        name: str,
        latitude: float,
        longitude: float,
        code: str = "HSP-001",
        is_active: bool = True,
    ) -> dict[str, Any]:
        with self._lock:
            record = {
                "id": hospital_id,
                "code": code,
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "is_active": is_active,
            }
            self._hospitals[hospital_id] = record
            return copy.deepcopy(record)

    def register_owner_vehicle_device_fixture(
        self,
        *,
        owner_id: UUID,
        owner_user_id: UUID | None,
        owner_name: str,
        vehicle_id: UUID,
        registration: str,
        device_id: UUID,
        device_code: str,
        secret_hash: str | None = None,
        is_active: bool = True,
    ) -> None:
        with self._lock:
            self._owners[owner_id] = {
                "id": owner_id,
                "user_id": owner_user_id,
                "full_name": owner_name,
            }
            self._vehicles[vehicle_id] = {
                "id": vehicle_id,
                "registration": registration,
                "owner_id": owner_id,
            }
            self._devices[device_id] = {
                "id": device_id,
                "device_code": device_code,
                "vehicle_id": vehicle_id,
                "secret_hash": secret_hash,
                "is_active": is_active,
            }

    def get_audit_logs(self, incident_id: UUID | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if incident_id is None:
                return copy.deepcopy(self._audit_logs)
            target = str(incident_id)
            return [
                copy.deepcopy(log)
                for log in self._audit_logs
                if log.get("target_id") == target
            ]

    # ------------------------------------------------------------------
    # Internal Event & Audit Helpers (In-Memory Store)
    # ------------------------------------------------------------------
    def _append_event_memory(
        self,
        *,
        incident_id: UUID,
        event_type: str,
        message: str,
        created_at: datetime,
        hospital_id: UUID | None = None,
        actor_id: UUID | None = None,
        actor_label: str = "System",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": self._event_seq,
            "incident_id": incident_id,
            "event_type": event_type,
            "message": message,
            "hospital_id": hospital_id,
            "actor_id": actor_id,
            "actor_label": actor_label,
            "metadata": metadata or {},
            "created_at": created_at,
        }
        self._event_seq += 1
        self._events.append(event)
        return event

    def _append_audit_memory(
        self,
        *,
        actor_id: UUID | None,
        actor_label: str,
        actor_role: str,
        category: str,
        action: str,
        target_type: str,
        target_id: str,
        target_label: str,
        detail: str | None,
        created_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": self._audit_seq,
            "code": f"AUD-{self._audit_seq:04d}",
            "created_at": created_at,
            "actor_id": actor_id,
            "actor_label": actor_label,
            "actor_role": actor_role,
            "category": category,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "target_label": target_label,
            "detail": detail,
            "metadata": metadata or {},
        }
        self._audit_seq += 1
        self._audit_logs.append(entry)
        return entry

    def _enrich_incident_dict(
        self,
        inc: dict[str, Any],
        *,
        include_details: bool = False,
        caller: CurrentUser | None = None,
    ) -> dict[str, Any]:
        detected_at = _ensure_utc(inc.get("detected_at")) or _utc_now()
        stale_seconds = self._settings.get("gps_stale_after_seconds", 120)
        loc_meta = compute_location_metadata(
            inc.get("latitude"),
            inc.get("longitude"),
            inc.get("location_recorded_at"),
            reference_time=detected_at,
            stale_after_seconds=stale_seconds,
        )
        enriched = {
            **copy.deepcopy(inc),
            **loc_meta,
        }
        if not include_details:
            return enriched

        inc_id = UUID(str(inc["id"]))
        if self._use_memory_store:
            all_notifs = [
                copy.deepcopy(n)
                for n in self._notifications.values()
                if n["incident_id"] == inc_id
            ]
            all_notifs.sort(key=lambda x: (x["escalation_level"], x["notified_at"]))
            all_notes = [
                copy.deepcopy(n)
                for n in self._notes
                if n["incident_id"] == inc_id
            ]
            all_reports = [
                copy.deepcopy(r)
                for r in self._false_alarm_reports
                if r["incident_id"] == inc_id
            ]
        else:
            db = get_supabase_admin()
            try:
                all_notifs = (
                    db.table("incident_notifications")
                    .select("*")
                    .eq("incident_id", str(inc_id))
                    .order("escalation_level")
                    .execute()
                    .data
                    or []
                )
                all_notes = (
                    db.table("incident_notes")
                    .select("*")
                    .eq("incident_id", str(inc_id))
                    .order("created_at")
                    .execute()
                    .data
                    or []
                )
                all_reports = (
                    db.table("false_alarm_reports")
                    .select("*")
                    .eq("incident_id", str(inc_id))
                    .order("created_at")
                    .execute()
                    .data
                    or []
                )
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to load incident details.",
                ) from None

        # Filter detail sub-collections by caller role (matching RLS policies)
        if caller is not None and caller.role == "hospital_staff":
            hosp_id_str = str(caller.hospital_id)
            all_notifs = [
                n for n in all_notifs if str(n.get("hospital_id")) == hosp_id_str
            ]
            all_notes = [
                n
                for n in all_notes
                if n.get("hospital_id") is None
                or str(n.get("hospital_id")) == hosp_id_str
            ]
            all_reports = [
                r
                for r in all_reports
                if str(r.get("hospital_id")) == hosp_id_str
            ]
        elif caller is not None and caller.role == "car_owner":
            all_notifs = []
            all_notes = []
            all_reports = []

        enriched["notifications"] = all_notifs
        enriched["notes"] = all_notes
        enriched["false_alarm_reports"] = all_reports
        return enriched

    # ------------------------------------------------------------------
    # Permission Helpers
    # ------------------------------------------------------------------
    def _get_incident_raw(self, incident_id: UUID) -> dict[str, Any]:
        if self._use_memory_store:
            inc = self._incidents.get(incident_id)
            if not inc:
                raise HTTPException(status_code=404, detail="Incident not found.")
            return inc

        db = get_supabase_admin()
        try:
            rows = (
                db.table("incidents")
                .select("*")
                .eq("id", str(incident_id))
                .limit(1)
                .execute()
                .data
            )
        except (APIError, HTTPError):
            raise HTTPException(
                status_code=503,
                detail="Unable to retrieve incident.",
            ) from None

        if not rows:
            raise HTTPException(status_code=404, detail="Incident not found.")
        return rows[0]

    def _owner_owns_vehicle(self, owner_id: UUID | None, vehicle_id: UUID | str | None) -> bool:
        if owner_id is None or vehicle_id is None:
            return False
        vid = UUID(str(vehicle_id))
        if self._use_memory_store:
            veh = self._vehicles.get(vid)
            return bool(veh and veh.get("owner_id") == owner_id)

        db = get_supabase_admin()
        try:
            rows = (
                db.table("vehicles")
                .select("id,owner_id")
                .eq("id", str(vid))
                .eq("owner_id", str(owner_id))
                .limit(1)
                .execute()
                .data
            )
            return bool(rows)
        except (APIError, HTTPError):
            raise HTTPException(
                status_code=503,
                detail="Unable to verify vehicle ownership.",
            ) from None

    def _hospital_assigned_to_incident(
        self, hospital_id: UUID | None, incident_id: UUID
    ) -> list[dict[str, Any]]:
        if hospital_id is None:
            return []
        if self._use_memory_store:
            return [
                n
                for n in self._notifications.values()
                if n["incident_id"] == incident_id and n["hospital_id"] == hospital_id
            ]

        db = get_supabase_admin()
        try:
            rows = (
                db.table("incident_notifications")
                .select("*")
                .eq("incident_id", str(incident_id))
                .eq("hospital_id", str(hospital_id))
                .execute()
                .data
            )
            return rows or []
        except (APIError, HTTPError):
            raise HTTPException(
                status_code=503,
                detail="Unable to verify hospital incident assignment.",
            ) from None

    def _assert_can_view_incident(
        self, user: CurrentUser, incident: dict[str, Any]
    ) -> None:
        inc_id = UUID(str(incident["id"]))
        if user.role == "superuser":
            return

        if user.role == "hospital_staff":
            if self._hospital_assigned_to_incident(user.hospital_id, inc_id):
                return
            raise HTTPException(
                status_code=403,
                detail="This incident is not assigned to your hospital.",
            )

        if user.role == "car_owner":
            if self._owner_owns_vehicle(user.owner_id, incident.get("vehicle_id")):
                return
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to view this incident.",
            )

        raise HTTPException(
            status_code=403,
            detail="Access to this incident is denied.",
        )

    # ------------------------------------------------------------------
    # 1. Shared Service Entry: Create Incident from Detection
    # ------------------------------------------------------------------
    def create_from_detection(
        self,
        payload: DetectionIncidentCreate | dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Create an incident in its 30s local cancellation window (idempotent on retries)."""

        data = (
            payload
            if isinstance(payload, DetectionIncidentCreate)
            else DetectionIncidentCreate.model_validate(payload)
        )
        current_time = _ensure_utc(now) or _utc_now()
        detected_at = _ensure_utc(data.detected_at, fallback=current_time) or current_time
        window_seconds = data.cancellation_window_seconds
        deadline = detected_at + timedelta(seconds=window_seconds)

        with self._lock:
            if self._use_memory_store:
                # 1. Deduplicate by prediction_id
                if data.prediction_id is not None and data.prediction_id in self._prediction_index:
                    existing_id = self._prediction_index[data.prediction_id]
                    return self._enrich_incident_dict(
                        self._incidents[existing_id], include_details=True
                    )

                # 2. Deduplicate by idempotency_key
                if data.idempotency_key and data.idempotency_key in self._idempotency_index:
                    existing_id = self._idempotency_index[data.idempotency_key]
                    return self._enrich_incident_dict(
                        self._incidents[existing_id], include_details=True
                    )

                # 3. Deduplicate overlapping active cancellation_window on same device
                for existing in self._incidents.values():
                    if (
                        existing["device_id"] == data.device_id
                        and existing["status"] == "cancellation_window"
                        and abs((existing["detected_at"] - detected_at).total_seconds()) < window_seconds
                    ):
                        if data.prediction_id is not None:
                            self._prediction_index[data.prediction_id] = existing["id"]
                        if data.idempotency_key:
                            self._idempotency_index[data.idempotency_key] = existing["id"]
                        return self._enrich_incident_dict(existing, include_details=True)

                device_row = self._devices.get(data.device_id)
                resolved_vehicle_id = data.vehicle_id or (
                    device_row.get("vehicle_id") if device_row else None
                )
                device_code = (
                    device_row.get("device_code", "unknown")
                    if device_row
                    else "unknown"
                )

                incident_id = uuid4()
                code = f"INC-{self._incident_seq}"
                self._incident_seq += 1

                record: dict[str, Any] = {
                    "id": incident_id,
                    "code": code,
                    "device_id": data.device_id,
                    "vehicle_id": resolved_vehicle_id,
                    "prediction_id": data.prediction_id,
                    "detected_at": detected_at,
                    "occurred_at": _ensure_utc(data.occurred_at),
                    "occurred_at_estimated": data.occurred_at_estimated,
                    "latitude": data.latitude,
                    "longitude": data.longitude,
                    "location_label": data.location_label,
                    "location_recorded_at": _ensure_utc(data.location_recorded_at),
                    "location_accuracy_m": data.location_accuracy_m,
                    "model_score": data.model_score,
                    "impact_summary": data.impact_summary,
                    "status": "cancellation_window",
                    "cancellation_window_seconds": window_seconds,
                    "cancellation_deadline": deadline,
                    "cancellation_outcome": "pending",
                    "cancellation_resolved_at": None,
                    "cancelled_by": None,
                    "cancelled_by_label": None,
                    "cancel_reason": None,
                    "closed_at": None,
                    "closed_by": None,
                    "closing_note": None,
                    "created_at": current_time,
                    "updated_at": current_time,
                }
                self._incidents[incident_id] = record
                if data.prediction_id is not None:
                    self._prediction_index[data.prediction_id] = incident_id
                if data.idempotency_key:
                    self._idempotency_index[data.idempotency_key] = incident_id

                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="detected",
                    message=f"Suspected accident detected by device {device_code}.",
                    created_at=detected_at,
                    actor_label="System",
                    metadata={"model_score": data.model_score},
                )
                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="window_started",
                    message=f"{window_seconds} second local cancellation window started.",
                    created_at=detected_at,
                    actor_label="System",
                    metadata={"cancellation_deadline": deadline.isoformat()},
                )
                return self._enrich_incident_dict(record, include_details=True)

            # Supabase mode
            db = get_supabase_admin()
            try:
                if data.prediction_id is not None:
                    existing_pred = (
                        db.table("incidents")
                        .select("*")
                        .eq("prediction_id", data.prediction_id)
                        .limit(1)
                        .execute()
                        .data
                    )
                    if existing_pred:
                        return self._enrich_incident_dict(
                            existing_pred[0], include_details=True
                        )

                existing_open = (
                    db.table("incidents")
                    .select("*")
                    .eq("device_id", str(data.device_id))
                    .eq("status", "cancellation_window")
                    .order("detected_at", desc=True)
                    .limit(1)
                    .execute()
                    .data
                )
                if existing_open:
                    prev_detected = _ensure_utc(existing_open[0].get("detected_at"))
                    if (
                        prev_detected
                        and abs((prev_detected - detected_at).total_seconds()) < window_seconds
                    ):
                        return self._enrich_incident_dict(
                            existing_open[0], include_details=True
                        )

                insert_row: dict[str, Any] = {
                    "device_id": str(data.device_id),
                    "detected_at": detected_at.isoformat(),
                    "status": "cancellation_window",
                    "cancellation_window_seconds": window_seconds,
                    "cancellation_deadline": deadline.isoformat(),
                    "cancellation_outcome": "pending",
                    "occurred_at_estimated": data.occurred_at_estimated,
                }
                if data.vehicle_id is not None:
                    insert_row["vehicle_id"] = str(data.vehicle_id)
                if data.prediction_id is not None:
                    insert_row["prediction_id"] = data.prediction_id
                if data.occurred_at is not None:
                    insert_row["occurred_at"] = _ensure_utc(data.occurred_at).isoformat()
                if data.latitude is not None and data.longitude is not None:
                    insert_row["latitude"] = data.latitude
                    insert_row["longitude"] = data.longitude
                if data.location_label is not None:
                    insert_row["location_label"] = data.location_label
                if data.location_recorded_at is not None:
                    insert_row["location_recorded_at"] = _ensure_utc(
                        data.location_recorded_at
                    ).isoformat()
                if data.location_accuracy_m is not None:
                    insert_row["location_accuracy_m"] = data.location_accuracy_m
                if data.model_score is not None:
                    insert_row["model_score"] = data.model_score
                if data.impact_summary is not None:
                    insert_row["impact_summary"] = data.impact_summary

                created = (
                    db.table("incidents")
                    .insert(insert_row)
                    .execute()
                    .data
                )
                if not created:
                    raise HTTPException(
                        status_code=503,
                        detail="Incident could not be created.",
                    )
                return self._enrich_incident_dict(created[0], include_details=True)
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to record suspected accident incident.",
                ) from None

    # ------------------------------------------------------------------
    # 2. List & Retrieve Incidents + Timeline
    # ------------------------------------------------------------------
    def list_incidents(
        self,
        user: CurrentUser,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        with self._lock:
            if self._use_memory_store:
                items: list[dict[str, Any]] = []
                for inc in self._incidents.values():
                    if status is not None and inc["status"] != status:
                        continue
                    if user.role == "superuser":
                        items.append(inc)
                    elif user.role == "hospital_staff":
                        if self._hospital_assigned_to_incident(
                            user.hospital_id, inc["id"]
                        ):
                            items.append(inc)
                    elif user.role == "car_owner":
                        if self._owner_owns_vehicle(
                            user.owner_id, inc.get("vehicle_id")
                        ):
                            items.append(inc)

                items.sort(
                    key=lambda x: (_ensure_utc(x["detected_at"]), str(x["id"])),
                    reverse=True,
                )
                total = len(items)
                sliced = [
                    self._enrich_incident_dict(i, include_details=False, caller=user)
                    for i in items[offset : offset + limit]
                ]
                return {
                    "items": sliced,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                }

            db = get_supabase_admin()
            try:
                if user.role == "superuser":
                    query = db.table("incidents").select("*", count="exact")
                    if status is not None:
                        query = query.eq("status", status)
                    result = (
                        query.order("detected_at", desc=True)
                        .order("id", desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    rows = result.data or []
                    total = result.count if result.count is not None else len(rows)
                elif user.role == "hospital_staff":
                    notif_rows = (
                        db.table("incident_notifications")
                        .select("incident_id")
                        .eq("hospital_id", str(user.hospital_id))
                        .execute()
                        .data
                        or []
                    )
                    incident_ids = list({r["incident_id"] for r in notif_rows})
                    if not incident_ids:
                        return {"items": [], "total": 0, "limit": limit, "offset": offset}
                    query = (
                        db.table("incidents")
                        .select("*", count="exact")
                        .in_("id", incident_ids)
                    )
                    if status is not None:
                        query = query.eq("status", status)
                    result = (
                        query.order("detected_at", desc=True)
                        .order("id", desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    rows = result.data or []
                    total = result.count if result.count is not None else len(rows)
                elif user.role == "car_owner":
                    veh_rows = (
                        db.table("vehicles")
                        .select("id")
                        .eq("owner_id", str(user.owner_id))
                        .execute()
                        .data
                        or []
                    )
                    vehicle_ids = [r["id"] for r in veh_rows]
                    if not vehicle_ids:
                        return {"items": [], "total": 0, "limit": limit, "offset": offset}
                    query = (
                        db.table("incidents")
                        .select("*", count="exact")
                        .in_("vehicle_id", vehicle_ids)
                    )
                    if status is not None:
                        query = query.eq("status", status)
                    result = (
                        query.order("detected_at", desc=True)
                        .order("id", desc=True)
                        .range(offset, offset + limit - 1)
                        .execute()
                    )
                    rows = result.data or []
                    total = result.count if result.count is not None else len(rows)
                else:
                    raise HTTPException(status_code=403, detail="Access denied.")

                return {
                    "items": [
                        self._enrich_incident_dict(r, include_details=False, caller=user)
                        for r in rows
                    ],
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                }
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to retrieve incidents.",
                ) from None

    def get_incident(self, incident_id: UUID, user: CurrentUser) -> dict[str, Any]:
        with self._lock:
            inc = self._get_incident_raw(incident_id)
            self._assert_can_view_incident(user, inc)
            return self._enrich_incident_dict(inc, include_details=True, caller=user)

    def get_timeline(self, incident_id: UUID, user: CurrentUser) -> dict[str, Any]:
        with self._lock:
            inc = self._get_incident_raw(incident_id)
            self._assert_can_view_incident(user, inc)

            if self._use_memory_store:
                events = [
                    copy.deepcopy(e)
                    for e in self._events
                    if e["incident_id"] == incident_id
                ]
                events.sort(key=lambda e: (_ensure_utc(e["created_at"]), e["id"]))
            else:
                db = get_supabase_admin()
                try:
                    events = (
                        db.table("incident_events")
                        .select("*")
                        .eq("incident_id", str(incident_id))
                        .order("created_at")
                        .order("id")
                        .execute()
                        .data
                        or []
                    )
                except (APIError, HTTPError):
                    raise HTTPException(
                        status_code=503,
                        detail="Unable to retrieve incident timeline.",
                    ) from None

            # Filter timeline events by role matching RLS policy `events_read`:
            # - superuser: all events
            # - hospital_staff: events where hospital_id is None or hospital_id == user.hospital_id
            # - car_owner: events where hospital_id is None
            if user.role == "hospital_staff":
                hosp_str = str(user.hospital_id)
                events = [
                    e
                    for e in events
                    if e.get("hospital_id") is None
                    or str(e.get("hospital_id")) == hosp_str
                ]
            elif user.role == "car_owner":
                events = [e for e in events if e.get("hospital_id") is None]

            return {
                "incident_id": incident_id,
                "items": events,
                "total": len(events),
            }

    # ------------------------------------------------------------------
    # 3. Cancellation (Owner and Device) & Expiry Race Protection
    # ------------------------------------------------------------------
    def _execute_cancellation(
        self,
        *,
        incident_id: UUID,
        actor_id: UUID | None,
        actor_label: str,
        actor_role: str,
        reason: str | None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current_time = _ensure_utc(now) or _utc_now()
        clean_reason = (reason or "").strip() or (
            "Cancelled by vehicle owner"
            if actor_role == "car_owner"
            else "Cancelled from vehicle device"
        )

        with self._lock:
            inc = self._get_incident_raw(incident_id)
            status = inc["status"]
            deadline = _ensure_utc(inc.get("cancellation_deadline"))

            # Idempotent retry: repeated cancellation on an already-cancelled incident
            # returns 200 OK without duplicating timeline or audit events.
            if status == "cancelled":
                return self._enrich_incident_dict(inc, include_details=True)

            if status == "closed":
                raise HTTPException(
                    status_code=409,
                    detail="Incident is already closed and cannot be cancelled.",
                )

            # Check if window has expired or incident was already notified/escalated
            window_expired_by_clock = (
                status == "cancellation_window"
                and deadline is not None
                and current_time > deadline
            )

            if window_expired_by_clock or status != "cancellation_window":
                # If the clock passed the deadline while status was still cancellation_window,
                # expire the window first so expiry wins deterministically.
                if window_expired_by_clock:
                    self.expire_cancellation_window(incident_id, now=current_time)

                # Explicit permitted workflow for late cancellation:
                # Never erase already-notified history; record the late cancellation request
                # on the incident timeline and audit log for responder/admin visibility,
                # and return 409 Conflict.
                late_msg = (
                    f"Late cancellation requested after the 30-second window by {actor_label}: "
                    f"{clean_reason}. Existing hospital notifications remain active."
                )
                if self._use_memory_store:
                    self._append_event_memory(
                        incident_id=incident_id,
                        event_type="note",
                        message=late_msg,
                        created_at=current_time,
                        actor_id=actor_id,
                        actor_label=actor_label,
                        metadata={
                            "late_cancellation_requested": True,
                            "actor_role": actor_role,
                            "reason": clean_reason,
                        },
                    )
                    self._append_audit_memory(
                        actor_id=actor_id,
                        actor_label=actor_label,
                        actor_role=actor_role,
                        category="incident",
                        action="Rejected late cancellation after window expiry",
                        target_type="incident",
                        target_id=str(incident_id),
                        target_label=inc["code"],
                        detail=clean_reason,
                        created_at=current_time,
                        metadata={"late_cancellation_requested": True},
                    )
                else:
                    db = get_supabase_admin()
                    try:
                        db.table("incident_events").insert(
                            {
                                "incident_id": str(incident_id),
                                "event_type": "note",
                                "message": late_msg,
                                "actor_id": str(actor_id) if actor_id else None,
                                "actor_label": actor_label,
                                "metadata": {
                                    "late_cancellation_requested": True,
                                    "actor_role": actor_role,
                                    "reason": clean_reason,
                                },
                            }
                        ).execute()
                    except (APIError, HTTPError):
                        pass

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The 30-second cancellation window has already expired. "
                        "Hospital notification history is preserved and late cancellation "
                        "was logged for responder review."
                    ),
                )

            # Timely cancellation within the 30-second window!
            if self._use_memory_store:
                inc["status"] = "cancelled"
                inc["cancellation_outcome"] = "cancelled"
                inc["cancellation_resolved_at"] = current_time
                inc["cancelled_by"] = actor_id
                inc["cancelled_by_label"] = actor_label
                inc["cancel_reason"] = clean_reason
                inc["updated_at"] = current_time

                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="cancelled",
                    message=(
                        "Cancelled as a false alarm during the cancellation window. "
                        f"Reason: {clean_reason}"
                    ),
                    created_at=current_time,
                    actor_id=actor_id,
                    actor_label=actor_label,
                    metadata={"actor_role": actor_role},
                )
                self._append_audit_memory(
                    actor_id=actor_id,
                    actor_label=actor_label,
                    actor_role=actor_role,
                    category="incident",
                    action="Cancelled false alarm",
                    target_type="incident",
                    target_id=str(incident_id),
                    target_label=inc["code"],
                    detail=clean_reason,
                    created_at=current_time,
                )
                return self._enrich_incident_dict(inc, include_details=True)

            # Supabase mode: atomic conditional update where status = 'cancellation_window'
            db = get_supabase_admin()
            try:
                updated = (
                    db.table("incidents")
                    .update(
                        {
                            "status": "cancelled",
                            "cancellation_outcome": "cancelled",
                            "cancellation_resolved_at": current_time.isoformat(),
                            "cancelled_by": str(actor_id) if actor_id else None,
                            "cancelled_by_label": actor_label,
                            "cancel_reason": clean_reason,
                        }
                    )
                    .eq("id", str(incident_id))
                    .eq("status", "cancellation_window")
                    .execute()
                    .data
                )
            except APIError as exc:
                if exc.code in {"23514", "40001", "40P01"}:
                    raise HTTPException(
                        status_code=409,
                        detail="The cancellation window has expired or the incident state changed.",
                    ) from None
                raise HTTPException(
                    status_code=503,
                    detail="Unable to cancel incident.",
                ) from None
            except HTTPError:
                raise HTTPException(
                    status_code=503,
                    detail="Unable to cancel incident.",
                ) from None

            if not updated:
                latest = self._get_incident_raw(incident_id)
                if latest["status"] == "cancelled":
                    return self._enrich_incident_dict(latest, include_details=True)
                raise HTTPException(
                    status_code=409,
                    detail="Cancellation lost the race against window expiry.",
                )

            return self._enrich_incident_dict(updated[0], include_details=True)

    def cancel_by_owner(
        self,
        incident_id: UUID,
        user: CurrentUser,
        payload: IncidentCancelRequest,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if user.role != "car_owner" or user.owner_id is None:
            raise HTTPException(
                status_code=403,
                detail="Only the registered car owner may cancel an incident through this endpoint.",
            )

        with self._lock:
            inc = self._get_incident_raw(incident_id)
            if not self._owner_owns_vehicle(user.owner_id, inc.get("vehicle_id")):
                raise HTTPException(
                    status_code=403,
                    detail="You may only cancel incidents for your own registered vehicles.",
                )

            actor_label = user.full_name.strip() or (user.email or "Car Owner")
            return self._execute_cancellation(
                incident_id=incident_id,
                actor_id=user.id,
                actor_label=actor_label,
                actor_role="car_owner",
                reason=payload.reason,
                now=now,
            )

    def cancel_by_device(
        self,
        device_id: UUID,
        incident_id: UUID,
        device: AuthenticatedDevice,
        payload: IncidentCancelRequest,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if device.id != device_id:
            raise HTTPException(
                status_code=403,
                detail="Authenticated device does not match path device_id.",
            )

        with self._lock:
            inc = self._get_incident_raw(incident_id)
            if str(inc.get("device_id")) != str(device.id):
                raise HTTPException(
                    status_code=403,
                    detail="Device may only cancel its own incident.",
                )

            device_code = str(device.id)
            if self._use_memory_store and device.id in self._devices:
                device_code = self._devices[device.id].get("device_code", str(device.id))

            return self._execute_cancellation(
                incident_id=incident_id,
                actor_id=None,
                actor_label=f"Device {device_code}",
                actor_role="device",
                reason=payload.reason,
                now=now,
            )

    # ------------------------------------------------------------------
    # 4. Cancellation Window Expiry & Hospital Routing Handoff
    # ------------------------------------------------------------------
    def _select_nearest_active_hospital_memory(
        self,
        latitude: float | None,
        longitude: float | None,
        exclude_ids: set[UUID] | None = None,
    ) -> tuple[dict[str, Any] | None, float | None]:
        excluded = exclude_ids or set()
        candidates = [
            h
            for h in self._hospitals.values()
            if h.get("is_active", True) and h["id"] not in excluded
        ]
        if not candidates or latitude is None or longitude is None:
            return None, None

        ranked = sorted(
            candidates,
            key=lambda h: (
                _haversine_km(latitude, longitude, h["latitude"], h["longitude"]),
                h["name"],
            ),
        )
        best = ranked[0]
        dist = _haversine_km(latitude, longitude, best["latitude"], best["longitude"])
        return best, dist

    def expire_cancellation_window(
        self,
        incident_id: UUID,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Atomically expire a due 30s cancellation window and trigger hospital routing."""

        current_time = _ensure_utc(now) or _utc_now()
        with self._lock:
            inc = self._get_incident_raw(incident_id)
            status = inc["status"]
            if status == "cancelled":
                raise HTTPException(
                    status_code=409,
                    detail="Incident was already cancelled; cancellation window cannot expire.",
                )
            if status != "cancellation_window":
                return self._enrich_incident_dict(inc, include_details=True)

            deadline = _ensure_utc(inc.get("cancellation_deadline"))
            if deadline is not None and current_time < deadline:
                raise HTTPException(
                    status_code=409,
                    detail="Cancellation window has not yet reached its deadline.",
                )

            if self._use_memory_store:
                inc["cancellation_outcome"] = "expired"
                inc["cancellation_resolved_at"] = current_time
                inc["updated_at"] = current_time

                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="window_expired",
                    message="Cancellation window expired without cancellation.",
                    created_at=current_time,
                    actor_label="System",
                )

                if self._alert_router_callback is not None:
                    self._alert_router_callback(copy.deepcopy(inc))

                # Route to nearest active hospital if location is available
                hosp, dist_km = self._select_nearest_active_hospital_memory(
                    inc.get("latitude"),
                    inc.get("longitude"),
                )
                if hosp is not None:
                    ack_timeout = self._settings.get("hospital_ack_timeout_seconds", 180)
                    notif_id = uuid4()
                    notif = {
                        "id": notif_id,
                        "incident_id": incident_id,
                        "hospital_id": hosp["id"],
                        "hospital_name": hosp["name"],
                        "escalation_level": 1,
                        "routing_reason": "nearest",
                        "routed_by": None,
                        "distance_km": dist_km,
                        "status": "notified",
                        "notified_at": current_time,
                        "response_deadline": current_time + timedelta(seconds=ack_timeout),
                        "acknowledged_at": None,
                        "acknowledged_by": None,
                        "responded_at": None,
                        "responded_by": None,
                        "decline_reason": None,
                        "created_at": current_time,
                        "updated_at": current_time,
                    }
                    self._notifications[notif_id] = notif
                    inc["status"] = "notified"
                    self._append_event_memory(
                        incident_id=incident_id,
                        event_type="notified",
                        message=f"{hosp['name']} notified (nearest active hospital).",
                        created_at=current_time,
                        hospital_id=hosp["id"],
                        actor_label="System",
                        metadata={
                            "escalation_level": 1,
                            "routing_reason": "nearest",
                            "distance_km": dist_km,
                        },
                    )
                else:
                    inc["status"] = "escalated"
                    reason_tag = (
                        "location_unavailable"
                        if inc.get("latitude") is None or inc.get("longitude") is None
                        else "routing_exhausted"
                    )
                    self._append_event_memory(
                        incident_id=incident_id,
                        event_type="escalated",
                        message=(
                            "No eligible hospital could be routed automatically "
                            f"({reason_tag}). Superuser action required."
                        ),
                        created_at=current_time,
                        actor_label="System",
                        metadata={"reason": reason_tag, "escalation_level": 0},
                    )

                return self._enrich_incident_dict(inc, include_details=True)

            # Supabase mode: invoke `process_incident_deadlines` RPC
            db = get_supabase_admin()
            try:
                db.rpc("process_incident_deadlines", {}).execute()
                refreshed = self._get_incident_raw(incident_id)
                return self._enrich_incident_dict(refreshed, include_details=True)
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to process expired cancellation window.",
                ) from None

    def process_due_cancellation_windows(
        self, *, now: datetime | None = None
    ) -> dict[str, Any]:
        """Durable worker entry point: expire all due 30s windows atomically."""

        current_time = _ensure_utc(now) or _utc_now()
        with self._lock:
            if self._use_memory_store:
                due_ids = [
                    inc["id"]
                    for inc in self._incidents.values()
                    if inc["status"] == "cancellation_window"
                    and _ensure_utc(inc.get("cancellation_deadline")) is not None
                    and _ensure_utc(inc.get("cancellation_deadline")) <= current_time
                ]
                expired_count = 0
                notified_count = 0
                needs_superuser_count = 0
                for inc_id in due_ids:
                    result = self.expire_cancellation_window(inc_id, now=current_time)
                    expired_count += 1
                    if result["status"] == "notified":
                        notified_count += 1
                    elif result["status"] == "escalated":
                        needs_superuser_count += 1
                return {
                    "windows_expired": expired_count,
                    "incidents_notified": notified_count,
                    "needs_superuser": needs_superuser_count,
                    "processed_at": current_time.isoformat(),
                }

            db = get_supabase_admin()
            try:
                res = db.rpc("process_incident_deadlines", {}).execute()
                return res.data if isinstance(res.data, dict) else {"processed": True}
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to process incident deadlines.",
                ) from None

    # ------------------------------------------------------------------
    # 5. Shared Service Entry: Apply Hospital Response
    # ------------------------------------------------------------------
    def apply_hospital_response(
        self,
        update: HospitalResponseUpdate | dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Update incident state and timeline when a hospital notification changes."""

        data = (
            update
            if isinstance(update, HospitalResponseUpdate)
            else HospitalResponseUpdate.model_validate(update)
        )
        current_time = _ensure_utc(now) or _utc_now()

        with self._lock:
            inc = self._get_incident_raw(data.incident_id)
            if inc["status"] in {"cancelled", "closed"}:
                raise HTTPException(
                    status_code=409,
                    detail=f"Incident is already {inc['status']} and cannot accept hospital updates.",
                )

            if self._use_memory_store:
                hosp = self._hospitals.get(data.hospital_id, {})
                hosp_name = hosp.get("name", f"Hospital {data.hospital_id}")
                actor_label = data.actor_label or hosp_name

                # Find or create notification record in memory
                notif = None
                for existing in self._notifications.values():
                    if (
                        existing["incident_id"] == data.incident_id
                        and existing["hospital_id"] == data.hospital_id
                    ):
                        notif = existing
                        break

                if notif is None:
                    notif_id = data.notification_id or uuid4()
                    ack_timeout = self._settings.get("hospital_ack_timeout_seconds", 180)
                    notif = {
                        "id": notif_id,
                        "incident_id": data.incident_id,
                        "hospital_id": data.hospital_id,
                        "hospital_name": hosp_name,
                        "escalation_level": data.escalation_level,
                        "routing_reason": data.routing_reason,
                        "routed_by": data.actor_id if data.routing_reason == "manual" else None,
                        "distance_km": data.distance_km,
                        "status": "notified",
                        "notified_at": current_time,
                        "response_deadline": data.response_deadline
                        or (current_time + timedelta(seconds=ack_timeout)),
                        "acknowledged_at": None,
                        "acknowledged_by": None,
                        "responded_at": None,
                        "responded_by": None,
                        "decline_reason": None,
                        "created_at": current_time,
                        "updated_at": current_time,
                    }
                    self._notifications[notif_id] = notif

                if data.status in {"notified", "escalated"}:
                    if inc["status"] == "cancellation_window":
                        inc["cancellation_outcome"] = "expired"
                        inc["cancellation_resolved_at"] = current_time
                        self._append_event_memory(
                            incident_id=data.incident_id,
                            event_type="window_expired",
                            message="Cancellation window expired without cancellation.",
                            created_at=current_time,
                            actor_label="System",
                        )
                    inc["status"] = (
                        "escalated"
                        if data.escalation_level > 1 or data.status == "escalated"
                        else "notified"
                    )
                    inc["updated_at"] = current_time
                    evt_type = "escalated" if inc["status"] == "escalated" else "notified"
                    msg = (
                        f"Escalated to {hosp_name} (level {data.escalation_level}, reason: {data.routing_reason})."
                        if evt_type == "escalated"
                        else f"{hosp_name} notified."
                    )
                    self._append_event_memory(
                        incident_id=data.incident_id,
                        event_type=evt_type,
                        message=msg,
                        created_at=current_time,
                        hospital_id=data.hospital_id,
                        actor_id=data.actor_id,
                        actor_label=actor_label if data.actor_id else "System",
                        metadata={
                            "escalation_level": data.escalation_level,
                            "routing_reason": data.routing_reason,
                            "distance_km": data.distance_km,
                        },
                    )
                elif data.status == "acknowledged":
                    notif["status"] = "acknowledged"
                    notif["acknowledged_at"] = current_time
                    notif["acknowledged_by"] = data.actor_id
                    notif["updated_at"] = current_time
                    if inc["status"] in {"notified", "escalated", "cancellation_window"}:
                        inc["status"] = "acknowledged"
                        inc["updated_at"] = current_time
                    self._append_event_memory(
                        incident_id=data.incident_id,
                        event_type="acknowledged",
                        message=f"{hosp_name} acknowledged the alert.",
                        created_at=current_time,
                        hospital_id=data.hospital_id,
                        actor_id=data.actor_id,
                        actor_label=actor_label,
                    )
                    self._append_audit_memory(
                        actor_id=data.actor_id,
                        actor_label=actor_label,
                        actor_role=data.actor_role,
                        category="incident",
                        action="Acknowledged alert",
                        target_type="incident",
                        target_id=str(data.incident_id),
                        target_label=inc["code"],
                        detail=hosp_name,
                        created_at=current_time,
                    )
                elif data.status == "accepted":
                    for other in self._notifications.values():
                        if (
                            other["incident_id"] == data.incident_id
                            and other["id"] != notif["id"]
                            and other["status"] == "accepted"
                        ):
                            raise HTTPException(
                                status_code=409,
                                detail="Another hospital has already accepted this incident.",
                            )
                    notif["status"] = "accepted"
                    notif["acknowledged_at"] = notif["acknowledged_at"] or current_time
                    notif["responded_at"] = current_time
                    notif["responded_by"] = data.actor_id
                    notif["updated_at"] = current_time
                    for other in self._notifications.values():
                        if (
                            other["incident_id"] == data.incident_id
                            and other["id"] != notif["id"]
                            and other["status"] in {"notified", "acknowledged"}
                        ):
                            other["status"] = "withdrawn"
                            other["updated_at"] = current_time
                    inc["status"] = "accepted"
                    inc["updated_at"] = current_time
                    self._append_event_memory(
                        incident_id=data.incident_id,
                        event_type="accepted",
                        message=f"{hosp_name} accepted the response.",
                        created_at=current_time,
                        hospital_id=data.hospital_id,
                        actor_id=data.actor_id,
                        actor_label=actor_label,
                    )
                    self._append_audit_memory(
                        actor_id=data.actor_id,
                        actor_label=actor_label,
                        actor_role=data.actor_role,
                        category="incident",
                        action="Accepted response",
                        target_type="incident",
                        target_id=str(data.incident_id),
                        target_label=inc["code"],
                        detail=hosp_name,
                        created_at=current_time,
                    )
                elif data.status == "declined":
                    if not (data.decline_reason or "").strip():
                        raise HTTPException(
                            status_code=422,
                            detail="A decline reason is required.",
                        )
                    notif["status"] = "declined"
                    notif["acknowledged_at"] = notif["acknowledged_at"] or current_time
                    notif["responded_at"] = current_time
                    notif["responded_by"] = data.actor_id
                    notif["decline_reason"] = data.decline_reason.strip()
                    notif["updated_at"] = current_time
                    self._append_event_memory(
                        incident_id=data.incident_id,
                        event_type="declined",
                        message=f"{hosp_name} declined: {notif['decline_reason']}",
                        created_at=current_time,
                        hospital_id=data.hospital_id,
                        actor_id=data.actor_id,
                        actor_label=actor_label,
                    )
                    self._append_audit_memory(
                        actor_id=data.actor_id,
                        actor_label=actor_label,
                        actor_role=data.actor_role,
                        category="incident",
                        action="Declined response",
                        target_type="incident",
                        target_id=str(data.incident_id),
                        target_label=inc["code"],
                        detail=f"{hosp_name}: {notif['decline_reason']}",
                        created_at=current_time,
                    )
                elif data.status == "timed_out":
                    notif["status"] = "timed_out"
                    notif["updated_at"] = current_time
                    self._append_event_memory(
                        incident_id=data.incident_id,
                        event_type="timed_out",
                        message=f"No acknowledgment from {hosp_name} before the response deadline.",
                        created_at=current_time,
                        hospital_id=data.hospital_id,
                        actor_label="System",
                    )

                return self._enrich_incident_dict(inc, include_details=True)

            # Supabase mode: triggers on incident_notifications keep incidents & events in sync
            refreshed = self._get_incident_raw(data.incident_id)
            return self._enrich_incident_dict(refreshed, include_details=True)

    # ------------------------------------------------------------------
    # 6. Notes (`POST /api/incidents/{id}/notes`)
    # ------------------------------------------------------------------
    def add_note(
        self,
        incident_id: UUID,
        user: CurrentUser,
        payload: IncidentNoteCreate,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if user.role not in {"superuser", "hospital_staff"}:
            raise HTTPException(
                status_code=403,
                detail="Only authorized hospital staff or superusers may add incident notes.",
            )

        current_time = _ensure_utc(now) or _utc_now()
        with self._lock:
            inc = self._get_incident_raw(incident_id)
            hospital_id: UUID | None = None
            if user.role == "hospital_staff":
                if not self._hospital_assigned_to_incident(user.hospital_id, incident_id):
                    raise HTTPException(
                        status_code=403,
                        detail="This incident is not assigned to your hospital.",
                    )
                hospital_id = user.hospital_id

            author_label = user.full_name.strip() or (user.email or "Authorized User")

            if self._use_memory_store:
                note_record = {
                    "id": uuid4(),
                    "incident_id": incident_id,
                    "hospital_id": hospital_id,
                    "author_id": user.id,
                    "author_label": author_label,
                    "body": payload.body,
                    "created_at": current_time,
                }
                self._notes.append(note_record)
                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="note",
                    message=f"Note added: {payload.body[:280]}",
                    created_at=current_time,
                    hospital_id=hospital_id,
                    actor_id=user.id,
                    actor_label=author_label,
                )
                return copy.deepcopy(note_record)

            db = get_supabase_admin()
            try:
                created = (
                    db.table("incident_notes")
                    .insert(
                        {
                            "incident_id": str(incident_id),
                            "hospital_id": str(hospital_id) if hospital_id else None,
                            "author_id": str(user.id),
                            "author_label": author_label,
                            "body": payload.body,
                        }
                    )
                    .execute()
                    .data
                )
                if not created:
                    raise HTTPException(
                        status_code=503,
                        detail="Incident note could not be saved.",
                    )
                return created[0]
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to save incident note.",
                ) from None

    # ------------------------------------------------------------------
    # 7. Hospital False-Alarm Report (`POST /api/incidents/{id}/false-alarm-reports`)
    # ------------------------------------------------------------------
    def report_false_alarm(
        self,
        incident_id: UUID,
        user: CurrentUser,
        payload: FalseAlarmReportCreate,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Submit a hospital false-alarm review report without cancelling the incident."""

        if user.role != "hospital_staff" or user.hospital_id is None:
            raise HTTPException(
                status_code=403,
                detail="Only hospital staff assigned to the incident may submit a false-alarm report.",
            )

        current_time = _ensure_utc(now) or _utc_now()
        with self._lock:
            inc = self._get_incident_raw(incident_id)
            if not self._hospital_assigned_to_incident(user.hospital_id, incident_id):
                raise HTTPException(
                    status_code=403,
                    detail="This incident is not assigned to your hospital.",
                )

            actor_label = user.full_name.strip() or (user.email or "Hospital Staff")

            if self._use_memory_store:
                report_record = {
                    "id": uuid4(),
                    "incident_id": incident_id,
                    "hospital_id": user.hospital_id,
                    "reported_by": user.id,
                    "reason": payload.reason,
                    "review_status": "open",
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "review_note": None,
                    "created_at": current_time,
                    "updated_at": current_time,
                }
                self._false_alarm_reports.append(report_record)
                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="false_alarm_reported",
                    message=f"Possible false alarm reported: {payload.reason}",
                    created_at=current_time,
                    hospital_id=user.hospital_id,
                    actor_id=user.id,
                    actor_label=actor_label,
                )
                self._append_audit_memory(
                    actor_id=user.id,
                    actor_label=actor_label,
                    actor_role="hospital_staff",
                    category="incident",
                    action="Reported possible false alarm",
                    target_type="incident",
                    target_id=str(incident_id),
                    target_label=inc["code"],
                    detail=payload.reason,
                    created_at=current_time,
                )
                return copy.deepcopy(report_record)

            db = get_supabase_admin()
            try:
                created = (
                    db.table("false_alarm_reports")
                    .insert(
                        {
                            "incident_id": str(incident_id),
                            "hospital_id": str(user.hospital_id),
                            "reported_by": str(user.id),
                            "reason": payload.reason,
                        }
                    )
                    .execute()
                    .data
                )
                if not created:
                    raise HTTPException(
                        status_code=503,
                        detail="False-alarm report could not be saved.",
                    )
                return created[0]
            except (APIError, HTTPError):
                raise HTTPException(
                    status_code=503,
                    detail="Unable to submit false-alarm report.",
                ) from None

    # ------------------------------------------------------------------
    # 8. Incident Closure (`POST /api/incidents/{id}/close` & `/api/admin/incidents/{id}/close`)
    # ------------------------------------------------------------------
    def close_incident(
        self,
        incident_id: UUID,
        user: CurrentUser,
        payload: IncidentCloseRequest,
        *,
        is_admin_endpoint: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if is_admin_endpoint and user.role != "superuser":
            raise HTTPException(
                status_code=403,
                detail="Superuser access is required.",
            )

        if user.role not in {"superuser", "hospital_staff"}:
            raise HTTPException(
                status_code=403,
                detail="Only an authorized hospital responder or superuser may close an incident.",
            )

        current_time = _ensure_utc(now) or _utc_now()
        with self._lock:
            inc = self._get_incident_raw(incident_id)

            if user.role == "hospital_staff":
                notifs = self._hospital_assigned_to_incident(
                    user.hospital_id, incident_id
                )
                if not notifs:
                    raise HTTPException(
                        status_code=403,
                        detail="This incident is not assigned to your hospital.",
                    )
                if not any(
                    n.get("status") in {"acknowledged", "accepted", "notified"}
                    for n in notifs
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Your hospital does not hold an active responder assignment for this incident.",
                    )

            if inc["status"] in {"cancelled", "closed"}:
                raise HTTPException(
                    status_code=409,
                    detail=f"Incident is already {inc['status']} and cannot be closed.",
                )

            if inc["status"] == "cancellation_window":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Incident is still in its 30-second cancellation window. "
                        "Use cancellation for false alarms during the window."
                    ),
                )

            closing_note = payload.resolved_closing_note() or "Incident closed."
            actor_label = user.full_name.strip() or (user.email or "Authorized User")

            if self._use_memory_store:
                inc["status"] = "closed"
                inc["closed_at"] = current_time
                inc["closed_by"] = user.id
                inc["closing_note"] = closing_note
                inc["updated_at"] = current_time

                for notif in self._notifications.values():
                    if (
                        notif["incident_id"] == incident_id
                        and notif["status"] in {"notified", "acknowledged"}
                    ):
                        notif["status"] = "withdrawn"
                        notif["updated_at"] = current_time

                if user.role == "superuser" and payload.outcome in {
                    "confirmed_false_alarm",
                    "rejected_false_alarm",
                }:
                    new_review_status = (
                        "confirmed_false_alarm"
                        if payload.outcome == "confirmed_false_alarm"
                        else "rejected"
                    )
                    for rep in self._false_alarm_reports:
                        if (
                            rep["incident_id"] == incident_id
                            and rep["review_status"] == "open"
                        ):
                            rep["review_status"] = new_review_status
                            rep["reviewed_by"] = user.id
                            rep["reviewed_at"] = current_time
                            rep["review_note"] = closing_note
                            rep["updated_at"] = current_time

                self._append_event_memory(
                    incident_id=incident_id,
                    event_type="closed",
                    message=f"Incident closed. {closing_note}",
                    created_at=current_time,
                    hospital_id=user.hospital_id if user.role == "hospital_staff" else None,
                    actor_id=user.id,
                    actor_label=actor_label,
                    metadata={"outcome": payload.outcome} if payload.outcome else {},
                )
                self._append_audit_memory(
                    actor_id=user.id,
                    actor_label=actor_label,
                    actor_role=user.role,
                    category="incident",
                    action="Closed incident",
                    target_type="incident",
                    target_id=str(incident_id),
                    target_label=inc["code"],
                    detail=closing_note,
                    created_at=current_time,
                )
                return self._enrich_incident_dict(inc, include_details=True, caller=user)

            db = get_supabase_admin()
            try:
                updated = (
                    db.table("incidents")
                    .update(
                        {
                            "status": "closed",
                            "closed_at": current_time.isoformat(),
                            "closed_by": str(user.id),
                            "closing_note": closing_note,
                        }
                    )
                    .eq("id", str(incident_id))
                    .execute()
                    .data
                )
                if not updated:
                    raise HTTPException(
                        status_code=409,
                        detail="Incident could not be closed.",
                    )
                if user.role == "superuser" and payload.outcome in {
                    "confirmed_false_alarm",
                    "rejected_false_alarm",
                }:
                    new_review_status = (
                        "confirmed_false_alarm"
                        if payload.outcome == "confirmed_false_alarm"
                        else "rejected"
                    )
                    db.table("false_alarm_reports").update(
                        {
                            "review_status": new_review_status,
                            "reviewed_by": str(user.id),
                            "reviewed_at": current_time.isoformat(),
                            "review_note": closing_note,
                        }
                    ).eq("incident_id", str(incident_id)).eq(
                        "review_status", "open"
                    ).execute()

                return self._enrich_incident_dict(
                    updated[0], include_details=True, caller=user
                )
            except APIError as exc:
                if exc.code == "23514":
                    raise HTTPException(
                        status_code=409,
                        detail="Incident is already closed or cancelled.",
                    ) from None
                raise HTTPException(
                    status_code=503,
                    detail="Unable to close incident.",
                ) from None
            except HTTPError:
                raise HTTPException(
                    status_code=503,
                    detail="Unable to close incident.",
                ) from None


incident_service = IncidentService()

