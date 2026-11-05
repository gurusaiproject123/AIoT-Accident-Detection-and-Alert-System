import asyncio
import hashlib
import json
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

try:
    import email_validator  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - fallback when venv lacks pydantic[email]
    _ev = types.ModuleType("email_validator")

    class EmailNotValidError(ValueError):
        pass

    class _ValidatedEmail:
        def __init__(self, email: str) -> None:
            local, _, domain = email.partition("@")
            self.local_part = local
            self.domain = domain
            self.normalized = email.strip()
            self. email = self.normalized

    def validate_email(email: str, **_kwargs: Any) -> _ValidatedEmail:
        if "@" not in email or "." not in email.split("@")[-1]:
            raise EmailNotValidError("Invalid email address")
        return _ValidatedEmail(email)

    _ev.EmailNotValidError = EmailNotValidError  # type: ignore[attr-defined]
    _ev.validate_email = validate_email  # type: ignore[attr-defined]
    _ev.__version__ = "2.2.0"  # type: ignore[attr-defined]
    sys.modules["email_validator"] = _ev

    import pydantic.networks

    pydantic.networks.email_validator = _ev  # type: ignore[attr-defined]
    pydantic.networks.import_email_validator = lambda: None  # type: ignore[assignment]

from app.core.device_security import AuthenticatedDevice, require_device
from app.core.security import get_current_user
from app.main import app
from app.schemas.auth import CurrentUser
from app.services.incident_service import incident_service
from app.workers.incident_deadline_worker import run_cancellation_deadline_tick


# ---------------------------------------------------------------------------
# Direct ASGI Test Harness (avoids Windows loopback socket hangs in sandbox)
# ---------------------------------------------------------------------------
def asgi_request(
    method: str,
    path: str,
    *,
    user: CurrentUser | None = None,
    device: AuthenticatedDevice | None = None,
    json_body: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    else:
        app.dependency_overrides.pop(get_current_user, None)

    if device is not None:
        app.dependency_overrides[require_device] = lambda: device
    else:
        app.dependency_overrides.pop(require_device, None)

    raw_body = (
        json.dumps(json_body).encode("utf-8") if json_body is not None else b""
    )
    req_headers: list[tuple[bytes, bytes]] = [
        (b"host", b"testserver"),
    ]
    if json_body is not None:
        req_headers.append((b"content-type", b"application/json"))
    req_headers.append((b"content-length", str(len(raw_body)).encode("ascii")))
    if headers:
        for k, v in headers.items():
            req_headers.append((k.lower().encode("ascii"), v.encode("utf-8")))

    query_bytes = urlencode(query, doseq=True).encode("ascii") if query else b""

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_bytes,
        "headers": req_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    sent = False
    response_status = 500
    response_chunks: list[bytes] = []

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": raw_body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        nonlocal response_status
        if message["type"] == "http.response.start":
            response_status = message["status"]
        elif message["type"] == "http.response.body":
            response_chunks.append(message.get("body", b""))

    try:
        asyncio.run(app(scope, receive, send))
    finally:
        app.dependency_overrides.clear()

    full_body = b"".join(response_chunks).decode("utf-8")
    parsed = json.loads(full_body) if full_body else {}
    return response_status, parsed


# ---------------------------------------------------------------------------
# Test Fixtures: Users, Hospitals, Owners, Vehicles, Devices
# ---------------------------------------------------------------------------
HOSPITAL_A_ID = UUID("11111111-1111-4111-8111-111111111111")
HOSPITAL_B_ID = UUID("22222222-2222-4222-8222-222222222222")

OWNER_A_ID = UUID("aaaaaaaa-1111-4111-8111-111111111111")
OWNER_B_ID = UUID("bbbbbbbb-2222-4222-8222-222222222222")

VEHICLE_A_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
VEHICLE_B_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

DEVICE_A_ID = UUID("dddddddd-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DEVICE_B_ID = UUID("dddddddd-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

SUPERUSER = CurrentUser(
    id=UUID("90000000-0000-4000-8000-000000000001"),
    full_name="System Superuser",
    email="admin@aiot.example",
    role="superuser",
    status="active",
    hospital_id=None,
    owner_id=None,
)

STAFF_A1 = CurrentUser(
    id=UUID("90000000-0000-4000-8000-000000000011"),
    full_name="Nurse Chipo (Hospital A)",
    email="chipo@hosp-a.example",
    role="hospital_staff",
    status="active",
    hospital_id=HOSPITAL_A_ID,
    owner_id=None,
)

STAFF_A2 = CurrentUser(
    id=UUID("90000000-0000-4000-8000-000000000012"),
    full_name="Dr Tendai (Hospital A)",
    email="tendai@hosp-a.example",
    role="hospital_staff",
    status="active",
    hospital_id=HOSPITAL_A_ID,
    owner_id=None,
)

STAFF_B1 = CurrentUser(
    id=UUID("90000000-0000-4000-8000-000000000021"),
    full_name="Dr Moyo (Hospital B)",
    email="moyo@hosp-b.example",
    role="hospital_staff",
    status="active",
    hospital_id=HOSPITAL_B_ID,
    owner_id=None,
)

OWNER_A_USER = CurrentUser(
    id=UUID("90000000-0000-4000-8000-000000000031"),
    full_name="Farai Owner A",
    email="farai@owners.example",
    role="car_owner",
    status="active",
    hospital_id=None,
    owner_id=OWNER_A_ID,
)

OWNER_B_USER = CurrentUser(
    id=UUID("90000000-0000-4000-8000-000000000032"),
    full_name="Rudo Owner B",
    email="rudo@owners.example",
    role="car_owner",
    status="active",
    hospital_id=None,
    owner_id=OWNER_B_ID,
)

AUTH_DEVICE_A = AuthenticatedDevice(
    id=DEVICE_A_ID,
    credential_hash=hashlib.sha256(b"device-a-secret").hexdigest(),
)

AUTH_DEVICE_B = AuthenticatedDevice(
    id=DEVICE_B_ID,
    credential_hash=hashlib.sha256(b"device-b-secret").hexdigest(),
)


@pytest.fixture(autouse=True)
def setup_incident_store():
    incident_service.enable_memory_store(True)
    incident_service.reset_memory_store()

    incident_service.register_hospital_fixture(
        hospital_id=HOSPITAL_A_ID,
        name="Parirenyatwa General Hospital",
        latitude=-17.8052,
        longitude=31.0447,
        code="HSP-001",
        is_active=True,
    )
    incident_service.register_hospital_fixture(
        hospital_id=HOSPITAL_B_ID,
        name="Harare Central Hospital",
        latitude=-17.8686,
        longitude=31.0189,
        code="HSP-002",
        is_active=True,
    )
    incident_service.register_owner_vehicle_device_fixture(
        owner_id=OWNER_A_ID,
        owner_user_id=OWNER_A_USER.id,
        owner_name=OWNER_A_USER.full_name,
        vehicle_id=VEHICLE_A_ID,
        registration="AEJ-4821",
        device_id=DEVICE_A_ID,
        device_code="ESP32-A01",
        secret_hash=AUTH_DEVICE_A.credential_hash,
    )
    incident_service.register_owner_vehicle_device_fixture(
        owner_id=OWNER_B_ID,
        owner_user_id=OWNER_B_USER.id,
        owner_name=OWNER_B_USER.full_name,
        vehicle_id=VEHICLE_B_ID,
        registration="BGT-9910",
        device_id=DEVICE_B_ID,
        device_code="ESP32-B02",
        secret_hash=AUTH_DEVICE_B.credential_hash,
    )
    yield
    incident_service.reset_memory_store()


# ---------------------------------------------------------------------------
# Required Test 1: Retried detection creates one incident and preserves history
# ---------------------------------------------------------------------------
def test_retried_detection_creates_single_incident_and_preserves_history():
    t0 = datetime(2026, 10, 29, 10, 0, 0, tzinfo=timezone.utc)
    payload = {
        "device_id": str(DEVICE_A_ID),
        "prediction_id": 501,
        "idempotency_key": "boot1-seq42",
        "detected_at": t0.isoformat(),
        "latitude": -17.8060,
        "longitude": 31.0450,
        "location_recorded_at": (t0 - timedelta(seconds=5)).isoformat(),
        "model_score": 0.87,
        "impact_summary": "High longitudinal deceleration and roll spike.",
    }

    first = incident_service.create_from_detection(payload, now=t0)
    second_same_pred = incident_service.create_from_detection(payload, now=t0 + timedelta(seconds=2))
    third_overlapping = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 502,
            "detected_at": (t0 + timedelta(seconds=8)).isoformat(),
            "latitude": -17.8060,
            "longitude": 31.0450,
            "location_recorded_at": (t0 + timedelta(seconds=7)).isoformat(),
            "model_score": 0.91,
        },
        now=t0 + timedelta(seconds=8),
    )

    assert first["id"] == second_same_pred["id"] == third_overlapping["id"]
    assert first["status"] == "cancellation_window"
    assert first["cancellation_outcome"] == "pending"
    assert first["cancellation_window_seconds"] == 30
    assert first["notifications"] == []  # No hospital notified before 30s expiry

    status_code, timeline = asgi_request(
        "GET",
        f"/api/incidents/{first['id']}/timeline",
        user=OWNER_A_USER,
    )
    assert status_code == 200
    event_types = [e["event_type"] for e in timeline["items"]]
    assert event_types == ["detected", "window_started"]


# ---------------------------------------------------------------------------
# Required Test 2: Timely cancellation prevents notification; another owner cannot cancel
# ---------------------------------------------------------------------------
def test_timely_cancellation_prevents_notification_and_blocks_other_owners():
    t0 = datetime.now(timezone.utc)
    created = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 601,
            "detected_at": t0.isoformat(),
            "latitude": -17.8060,
            "longitude": 31.0450,
            "location_recorded_at": t0.isoformat(),
            "model_score": 0.82,
        },
        now=t0,
    )
    inc_id = created["id"]

    # Unauthenticated caller -> 401
    code_unauth, _ = asgi_request("POST", f"/api/incidents/{inc_id}/cancel")
    assert code_unauth == 401

    # Owner B (different car) -> 403
    code_owner_b, body_owner_b = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/cancel",
        user=OWNER_B_USER,
        json_body={"reason": "Trying to cancel someone else's car"},
    )
    assert code_owner_b == 403
    assert "own registered vehicles" in body_owner_b["detail"]

    # Hospital staff or superuser -> 403 on owner cancel endpoint
    code_staff, _ = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/cancel",
        user=STAFF_A1,
        json_body={"reason": "Staff cannot use owner cancel"},
    )
    assert code_staff == 403

    code_admin, _ = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/cancel",
        user=SUPERUSER,
        json_body={"reason": "Admin cannot use owner cancel"},
    )
    assert code_admin == 403

    # Device B -> 403 on Device A's incident
    code_dev_b, _ = asgi_request(
        "POST",
        f"/api/devices/{DEVICE_B_ID}/incidents/{inc_id}/cancel",
        device=AUTH_DEVICE_B,
        json_body={"reason": "Wrong device"},
    )
    assert code_dev_b == 403

    # Owner A cancels within 30s window -> 200 OK
    code_owner_a, cancelled = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/cancel",
        user=OWNER_A_USER,
        json_body={"reason": "Hard pothole impact, no accident"},
    )
    assert code_owner_a == 200
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_outcome"] == "cancelled"
    assert cancelled["cancel_reason"] == "Hard pothole impact, no accident"
    assert cancelled["notifications"] == []

    # Deadline worker runs after 35s -> no hospital notification is created
    sweep = run_cancellation_deadline_tick(now=t0 + timedelta(seconds=35))
    assert sweep["windows_expired"] == 0

    code_detail, detail = asgi_request(
        "GET",
        f"/api/admin/incidents/{inc_id}",
        user=SUPERUSER,
    )
    assert code_detail == 200
    assert detail["status"] == "cancelled"
    assert detail["notifications"] == []


# ---------------------------------------------------------------------------
# Required Test 3: Repeated cancellation does not duplicate events
# ---------------------------------------------------------------------------
def test_repeated_owner_and_device_cancellation_is_idempotent():
    t0 = datetime.now(timezone.utc)
    created = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 701,
            "detected_at": t0.isoformat(),
            "latitude": -17.8060,
            "longitude": 31.0450,
            "location_recorded_at": t0.isoformat(),
            "model_score": 0.76,
        },
        now=t0,
    )
    inc_id = created["id"]

    # First cancellation via device endpoint
    c1, res1 = asgi_request(
        "POST",
        f"/api/devices/{DEVICE_A_ID}/incidents/{inc_id}/cancel",
        device=AUTH_DEVICE_A,
        json_body={"reason": "Driver pressed physical cancel button"},
    )
    assert c1 == 200
    assert res1["status"] == "cancelled"

    # Second cancellation via device endpoint (retry)
    c2, res2 = asgi_request(
        "POST",
        f"/api/devices/{DEVICE_A_ID}/incidents/{inc_id}/cancel",
        device=AUTH_DEVICE_A,
        json_body={"reason": "Driver pressed physical cancel button"},
    )
    assert c2 == 200
    assert res2["status"] == "cancelled"

    # Third cancellation via owner endpoint
    c3, res3 = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/cancel",
        user=OWNER_A_USER,
        json_body={"reason": "Owner also tapped cancel"},
    )
    assert c3 == 200
    assert res3["status"] == "cancelled"

    # Check timeline & audit logs: 'cancelled' appears only ONCE
    _, timeline = asgi_request(
        "GET",
        f"/api/incidents/{inc_id}/timeline",
        user=SUPERUSER,
    )
    cancelled_events = [
        e for e in timeline["items"] if e["event_type"] == "cancelled"
    ]
    assert len(cancelled_events) == 1

    audits = incident_service.get_audit_logs(UUID(str(inc_id)))
    cancel_audits = [a for a in audits if a["action"] == "Cancelled false alarm"]
    assert len(cancel_audits) == 1


# ---------------------------------------------------------------------------
# Required Test 4: Late cancellation follows explicit workflow without erasing history
# ---------------------------------------------------------------------------
def test_late_cancellation_preserves_notified_history_and_logs_review_event():
    t0 = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
    created = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 801,
            "detected_at": t0.isoformat(),
            "latitude": -17.8060,
            "longitude": 31.0450,
            "location_recorded_at": t0.isoformat(),
            "model_score": 0.93,
        },
        now=t0,
    )
    inc_id = UUID(str(created["id"]))

    # 31 seconds pass -> window expires and Hospital A is notified
    expired = incident_service.expire_cancellation_window(
        inc_id, now=t0 + timedelta(seconds=31)
    )
    assert expired["status"] == "notified"
    assert expired["cancellation_outcome"] == "expired"
    assert len(expired["notifications"]) == 1
    assert str(expired["notifications"][0]["hospital_id"]) == str(HOSPITAL_A_ID)

    # Owner A attempts late cancellation at t0 + 40s
    with pytest.raises(HTTPException) as exc_info:
        incident_service.cancel_by_owner(
            inc_id,
            OWNER_A_USER,
            incident_service_cancel_req("Sorry, I was outside the car"),
            now=t0 + timedelta(seconds=40),
        )
    assert exc_info.value.status_code == 409

    # Verify HTTP endpoint also returns 409 Conflict
    code_late, body_late = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/cancel",
        user=OWNER_A_USER,
        json_body={"reason": "Late cancel via HTTP"},
    )
    assert code_late == 409
    assert "already expired" in body_late["detail"]

    # Verify Hospital A notification and history were NOT erased
    _, detail = asgi_request("GET", f"/api/admin/incidents/{inc_id}", user=SUPERUSER)
    assert detail["status"] == "notified"
    assert detail["cancellation_outcome"] == "expired"
    assert len(detail["notifications"]) == 1
    assert detail["notifications"][0]["status"] == "notified"

    # Verify late cancellation request is preserved on the timeline
    _, timeline = asgi_request(
        "GET", f"/api/incidents/{inc_id}/timeline", user=SUPERUSER
    )
    event_types = [e["event_type"] for e in timeline["items"]]
    assert "detected" in event_types
    assert "window_started" in event_types
    assert "window_expired" in event_types
    assert "notified" in event_types
    late_notes = [
        e
        for e in timeline["items"]
        if e["metadata"].get("late_cancellation_requested") is True
    ]
    assert len(late_notes) >= 1


def incident_service_cancel_req(reason: str):
    from app.schemas.incident import IncidentCancelRequest

    return IncidentCancelRequest(reason=reason)


# ---------------------------------------------------------------------------
# Required Test 5: Expiry and cancellation cannot both win; invalid transitions return 409
# ---------------------------------------------------------------------------
def test_expiry_and_cancellation_race_exclusivity_and_invalid_transitions():
    t0 = datetime(2026, 10, 29, 13, 0, 0, tzinfo=timezone.utc)
    created = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 901,
            "detected_at": t0.isoformat(),
            "latitude": -17.8060,
            "longitude": 31.0450,
            "location_recorded_at": t0.isoformat(),
            "model_score": 0.89,
        },
        now=t0,
    )
    inc_id = UUID(str(created["id"]))

    # Cannot expire before the 30s deadline
    with pytest.raises(HTTPException) as early_exp:
        incident_service.expire_cancellation_window(
            inc_id, now=t0 + timedelta(seconds=15)
        )
    assert early_exp.value.status_code == 409

    # Cannot close an incident while still in cancellation_window
    close_early_code, _ = asgi_request(
        "POST",
        f"/api/admin/incidents/{inc_id}/close",
        user=SUPERUSER,
        json_body={"closing_note": "Trying to close during 30s window"},
    )
    assert close_early_code == 409

    # Race two threads at the boundary: one cancelling at t0+29s, one expiring at t0+30s
    outcomes: list[str] = []
    errors: list[int] = []
    barrier = threading.Barrier(2)

    def worker_cancel():
        barrier.wait()
        try:
            res = incident_service.cancel_by_owner(
                inc_id,
                OWNER_A_USER,
                incident_service_cancel_req("Race cancel"),
                now=t0 + timedelta(seconds=29),
            )
            outcomes.append(res["status"])
        except HTTPException as exc:
            errors.append(exc.status_code)

    def worker_expire():
        barrier.wait()
        try:
            res = incident_service.expire_cancellation_window(
                inc_id,
                now=t0 + timedelta(seconds=30),
            )
            outcomes.append(res["status"])
        except HTTPException as exc:
            errors.append(exc.status_code)

    th1 = threading.Thread(target=worker_cancel)
    th2 = threading.Thread(target=worker_expire)
    th1.start()
    th2.start()
    th1.join()
    th2.join()

    # Exactly one succeeded and one failed with 409 Conflict!
    assert len(outcomes) == 1
    assert errors == [409]

    final_inc = incident_service.get_incident(inc_id, SUPERUSER)
    if final_inc["status"] == "cancelled":
        assert final_inc["cancellation_outcome"] == "cancelled"
        assert final_inc["notifications"] == []
    else:
        assert final_inc["status"] == "notified"
        assert final_inc["cancellation_outcome"] == "expired"
        assert len(final_inc["notifications"]) == 1


# ---------------------------------------------------------------------------
# Required Test 6: Stored deadlines survive restart; missing or stale location labelled honestly
# ---------------------------------------------------------------------------
def test_stored_deadlines_survive_worker_restart_and_honest_location_labels():
    t0 = datetime(2026, 10, 29, 14, 0, 0, tzinfo=timezone.utc)

    # Case A: Missing GPS coordinates
    inc_no_gps = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 1001,
            "detected_at": t0.isoformat(),
            "latitude": None,
            "longitude": None,
            "model_score": 0.85,
        },
        now=t0,
    )
    assert inc_no_gps["gps_status"] == "none"
    assert inc_no_gps["location_available"] is False
    assert inc_no_gps["location_stale"] is False
    assert "unavailable" in inc_no_gps["location_status_label"].lower()

    # Case B: Stale GPS coordinates (recorded 300s before detection > 120s threshold)
    inc_stale_gps = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_B_ID),
            "prediction_id": 1002,
            "detected_at": t0.isoformat(),
            "latitude": -17.8680,
            "longitude": 31.0190,
            "location_recorded_at": (t0 - timedelta(seconds=300)).isoformat(),
            "model_score": 0.81,
        },
        now=t0,
    )
    assert inc_stale_gps["gps_status"] == "stale"
    assert inc_stale_gps["location_available"] is True
    assert inc_stale_gps["location_stale"] is True
    assert "stale" in inc_stale_gps["location_status_label"].lower()

    # Simulate backend process/worker restart by exporting durable DB snapshot,
    # wiping memory, and restoring from durable storage
    durable_snapshot = incident_service.export_durable_state()
    incident_service.reset_memory_store()
    assert incident_service.list_incidents(SUPERUSER)["total"] == 0

    incident_service.restore_durable_state(durable_snapshot)
    assert incident_service.list_incidents(SUPERUSER)["total"] == 2

    # Run deadline tick after 31s
    tick_result = run_cancellation_deadline_tick(now=t0 + timedelta(seconds=31))
    assert tick_result["windows_expired"] == 2
    assert tick_result["incidents_notified"] == 1
    assert tick_result["needs_superuser"] == 1

    # Incident without GPS could not invent a destination -> status is 'escalated'
    no_gps_after = incident_service.get_incident(UUID(str(inc_no_gps["id"])), SUPERUSER)
    assert no_gps_after["status"] == "escalated"
    assert no_gps_after["notifications"] == []

    # Incident with coordinates routed to nearest hospital (Hospital B)
    stale_gps_after = incident_service.get_incident(
        UUID(str(inc_stale_gps["id"])), SUPERUSER
    )
    assert stale_gps_after["status"] == "notified"
    assert len(stale_gps_after["notifications"]) == 1
    assert str(stale_gps_after["notifications"][0]["hospital_id"]) == str(HOSPITAL_B_ID)


# ---------------------------------------------------------------------------
# Required Test 7: Full Role Permission Matrix, Notes, False-Alarm Reports & Closure
# ---------------------------------------------------------------------------
def test_permissions_notes_false_alarm_reports_and_closure_workflow():
    t0 = datetime(2026, 10, 29, 15, 0, 0, tzinfo=timezone.utc)
    created = incident_service.create_from_detection(
        {
            "device_id": str(DEVICE_A_ID),
            "prediction_id": 1101,
            "detected_at": t0.isoformat(),
            "latitude": -17.8055,
            "longitude": 31.0445,
            "location_recorded_at": t0.isoformat(),
            "model_score": 0.94,
        },
        now=t0,
    )
    inc_id = created["id"]

    # Expire 30s window so Hospital A is notified
    run_cancellation_deadline_tick(now=t0 + timedelta(seconds=31))

    # 1. List & Detail Permissions across all 6 actor contexts
    # - No token -> 401
    c_no_tok, _ = asgi_request("GET", "/api/incidents")
    assert c_no_tok == 401

    # - Both staff at Hospital A see the incident
    c_a1, list_a1 = asgi_request("GET", "/api/incidents", user=STAFF_A1)
    c_a2, list_a2 = asgi_request("GET", "/api/incidents", user=STAFF_A2)
    assert c_a1 == 200 and list_a1["total"] == 1
    assert c_a2 == 200 and list_a2["total"] == 1

    # - Staff at Hospital B cannot see Hospital A's incident
    c_b1_list, list_b1 = asgi_request("GET", "/api/incidents", user=STAFF_B1)
    assert c_b1_list == 200 and list_b1["total"] == 0
    c_b1_det, _ = asgi_request("GET", f"/api/incidents/{inc_id}", user=STAFF_B1)
    assert c_b1_det == 403

    # - Owner A sees their own car's incident; Owner B cannot
    c_oa, list_oa = asgi_request("GET", "/api/incidents", user=OWNER_A_USER)
    c_ob, list_ob = asgi_request("GET", "/api/incidents", user=OWNER_B_USER)
    assert c_oa == 200 and list_oa["total"] == 1
    assert c_ob == 200 and list_ob["total"] == 0
    c_ob_det, _ = asgi_request("GET", f"/api/incidents/{inc_id}", user=OWNER_B_USER)
    assert c_ob_det == 403

    # - Non-superusers cannot access /api/admin/incidents
    for non_admin in (STAFF_A1, STAFF_B1, OWNER_A_USER):
        c_adm, _ = asgi_request("GET", "/api/admin/incidents", user=non_admin)
        assert c_adm == 403

    # 2. Hospital A acknowledges and accepts via shared service
    incident_service.apply_hospital_response(
        {
            "incident_id": str(inc_id),
            "hospital_id": str(HOSPITAL_A_ID),
            "status": "acknowledged",
            "actor_id": str(STAFF_A1.id),
            "actor_label": STAFF_A1.full_name,
        },
        now=t0 + timedelta(seconds=40),
    )
    incident_service.apply_hospital_response(
        {
            "incident_id": str(inc_id),
            "hospital_id": str(HOSPITAL_A_ID),
            "status": "accepted",
            "actor_id": str(STAFF_A2.id),
            "actor_label": STAFF_A2.full_name,
        },
        now=t0 + timedelta(seconds=50),
    )

    # 3. Notes: Staff A1 and Superuser can add notes; Staff B1 and Owner A cannot
    c_note_b1, _ = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/notes",
        user=STAFF_B1,
        json_body={"body": "Unassigned hospital note"},
    )
    assert c_note_b1 == 403

    c_note_oa, _ = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/notes",
        user=OWNER_A_USER,
        json_body={"body": "Owner note"},
    )
    assert c_note_oa == 403

    c_note_a1, note_a1 = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/notes",
        user=STAFF_A1,
        json_body={"body": "Dispatching triage team to Samora Machel Ave."},
    )
    assert c_note_a1 == 201
    assert note_a1["hospital_id"] == str(HOSPITAL_A_ID)

    # 4. Hospital False-Alarm Report is a review request, NOT a cancellation
    c_fa_b1, _ = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/false-alarm-reports",
        user=STAFF_B1,
        json_body={"reason": "Hospital B cannot report on Hospital A incident"},
    )
    assert c_fa_b1 == 403

    c_fa_a1, fa_report = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/false-alarm-reports",
        user=STAFF_A1,
        json_body={"reason": "Caller on scene states sensor unit fell off mount."},
    )
    assert c_fa_a1 == 201
    assert fa_report["review_status"] == "open"

    # Incident must still be 'accepted', NOT 'cancelled'!
    _, after_fa = asgi_request("GET", f"/api/incidents/{inc_id}", user=STAFF_A1)
    assert after_fa["status"] == "accepted"

    # Owner A timeline does not leak internal hospital notes/events (hospital_id != None)
    _, owner_tl = asgi_request(
        "GET", f"/api/incidents/{inc_id}/timeline", user=OWNER_A_USER
    )
    assert all(item["hospital_id"] is None for item in owner_tl["items"])

    # 5. Superuser closes the incident and resolves the false-alarm report
    c_close, closed_inc = asgi_request(
        "POST",
        f"/api/admin/incidents/{inc_id}/close",
        user=SUPERUSER,
        json_body={
            "outcome": "confirmed_false_alarm",
            "closing_note": "Confirmed sensor mount detachment with hospital team.",
        },
    )
    assert c_close == 200
    assert closed_inc["status"] == "closed"
    assert closed_inc["closed_by"] == str(SUPERUSER.id)
    assert (
        closed_inc["false_alarm_reports"][0]["review_status"]
        == "confirmed_false_alarm"
    )

    # Closing an already-closed incident returns 409 Conflict
    c_close_again, _ = asgi_request(
        "POST",
        f"/api/incidents/{inc_id}/close",
        user=STAFF_A1,
        json_body={"closing_note": "Duplicate close"},
    )
    assert c_close_again == 409

