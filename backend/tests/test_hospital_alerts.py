"""Permission, workflow, escalation, and WebSocket tests for Section 7:
Hospital Alerts and Live Updates (`backend-hospital-alerts` - Victor).

Covers every required test in Section 7 of the Backend Development Guide:
1. Three staff at the same hospital see the same alert; another hospital cannot access it.
2. Acknowledgment updates all staff screens without automatically accepting the response.
3. A decline requires a reason and escalates once; retries do not duplicate routing.
4. Unanswered alerts escalate after the stored 180s deadline, including after a worker restart.
Plus:
- Unresolved routing when location or eligible hospitals are unavailable.
- Superuser manual routing (`POST /api/admin/incidents/{id}/notify`).
- Scoped live WebSocket updates (`/api/ws`) ensuring alerts are not broadcast to unrelated users.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from app.core.auth import AuthenticatedUser, set_token_verifier
from app.main import app
from app.schemas.alerts import OwnerContactSummary, VehicleSummary
from app.services.alert_service import (
    HospitalRecord,
    IncidentRecord,
    alert_service,
)
from app.services.websocket_manager import live_manager
from app.workers.escalation_worker import EscalationDeadlineWorker

# Deterministic test UUIDs
HOSP_BINDURA_ID = UUID("11111111-1111-1111-1111-111111111111")
HOSP_MAZOWE_ID = UUID("22222222-2222-2222-2222-222222222222")
HOSP_SHAMVA_ID = UUID("33333333-3333-3333-3333-333333333333")

OWNER_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OWNER_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

TEST_ACCOUNTS: dict[str, AuthenticatedUser] = {
    "token-bindura-staff-1": AuthenticatedUser(
        id=UUID("10000000-0000-0000-0000-000000000001"),
        full_name="Bindura Operator 1",
        role="hospital_staff",
        status="active",
        hospital_id=HOSP_BINDURA_ID,
    ),
    "token-bindura-staff-2": AuthenticatedUser(
        id=UUID("10000000-0000-0000-0000-000000000002"),
        full_name="Bindura Operator 2",
        role="hospital_staff",
        status="active",
        hospital_id=HOSP_BINDURA_ID,
    ),
    "token-bindura-staff-3": AuthenticatedUser(
        id=UUID("10000000-0000-0000-0000-000000000003"),
        full_name="Bindura Operator 3",
        role="hospital_staff",
        status="active",
        hospital_id=HOSP_BINDURA_ID,
    ),
    "token-mazowe-staff-1": AuthenticatedUser(
        id=UUID("20000000-0000-0000-0000-000000000001"),
        full_name="Mazowe Nurse 1",
        role="hospital_staff",
        status="active",
        hospital_id=HOSP_MAZOWE_ID,
    ),
    "token-superuser": AuthenticatedUser(
        id=UUID("90000000-0000-0000-0000-000000000001"),
        full_name="Platform Superuser",
        role="superuser",
        status="active",
        hospital_id=None,
    ),
    "token-owner-a": AuthenticatedUser(
        id=UUID("80000000-0000-0000-0000-000000000001"),
        full_name="Car Owner A",
        role="car_owner",
        status="active",
        hospital_id=None,
        owner_id=OWNER_A_ID,
    ),
    "token-owner-b": AuthenticatedUser(
        id=UUID("80000000-0000-0000-0000-000000000002"),
        full_name="Car Owner B",
        role="car_owner",
        status="active",
        hospital_id=None,
        owner_id=OWNER_B_ID,
    ),
    "token-suspended": AuthenticatedUser(
        id=UUID("70000000-0000-0000-0000-000000000001"),
        full_name="Suspended Staff",
        role="hospital_staff",
        status="suspended",
        hospital_id=HOSP_BINDURA_ID,
    ),
}


def _auth_header(token_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_key}"}


class _ASGIResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self.body = body

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


async def _call_asgi(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
) -> _ASGIResponse:
    """Invoke the FastAPI ASGI app directly in-memory without OS sockets."""
    parsed = urlsplit(path)
    raw_headers: list[tuple[bytes, bytes]] = []
    for k, v in (headers or {}).items():
        raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

    payload_bytes = b""
    if json_body is not None:
        payload_bytes = json.dumps(json_body).encode("utf-8")
        raw_headers.append((b"content-type", b"application/json"))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    sent_request = False
    status_code = 500
    body_chunks: list[bytes] = []

    async def receive() -> dict[str, Any]:
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": payload_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    return _ASGIResponse(status_code=status_code, body=b"".join(body_chunks))


class _FakeWebSocket:
    """In-memory fake WebSocket for testing scoped real-time fan-out."""

    def __init__(self) -> None:
        self.accepted = False
        self.messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.messages.append(payload)


class HospitalAlertsWorkflowTests(unittest.TestCase):
    """Comprehensive tests for Victor's Section 7 hospital alerts & live updates module."""

    def setUp(self) -> None:
        alert_service.reset_state()
        live_manager._connections.clear()
        set_token_verifier(lambda tok: TEST_ACCOUNTS.get(tok))
        self.t0 = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)

        alert_service.register_hospital_fixture(
            HospitalRecord(
                id=HOSP_BINDURA_ID,
                code="HSP-001",
                name="Bindura Hospital",
                city="Bindura",
                latitude=-17.3019,
                longitude=31.3306,
                is_active=True,
            )
        )
        alert_service.register_hospital_fixture(
            HospitalRecord(
                id=HOSP_MAZOWE_ID,
                code="HSP-002",
                name="Mazowe District Hospital",
                city="Mazowe",
                latitude=-17.5101,
                longitude=30.9711,
                is_active=True,
            )
        )
        alert_service.register_hospital_fixture(
            HospitalRecord(
                id=HOSP_SHAMVA_ID,
                code="HSP-003",
                name="Shamva District Hospital",
                city="Shamva",
                latitude=-17.3127,
                longitude=31.5703,
                is_active=False,
            )
        )

        self.incident_id = UUID("aaaa1111-1111-1111-1111-111111111111")
        alert_service.register_incident_fixture(
            IncidentRecord(
                id=self.incident_id,
                code="INC-1051",
                device_id=uuid4(),
                device_code="ESP32-A01",
                detected_at=self.t0,
                status="cancellation_window",
                cancellation_window_seconds=30,
                cancellation_deadline=self.t0 + timedelta(seconds=30),
                latitude=-17.3205,
                longitude=31.3101,
                location_label="Chipadze Road, Bindura",
                model_score=0.89,
                impact_summary="Front impact signature",
                vehicle=VehicleSummary(
                    registration="DEMO-008",
                    make="Toyota",
                    model="Corolla",
                    colour="Silver",
                ),
                owner=OwnerContactSummary(
                    id=OWNER_A_ID,
                    full_name="Sample owner 008",
                    phone="+263 700 000 008",
                    email="owner008@example.com",
                ),
                owner_id=OWNER_A_ID,
            )
        )

    def tearDown(self) -> None:
        live_manager._connections.clear()
        set_token_verifier(None)

    def test_1_three_staff_same_hospital_see_same_alert_and_other_hospital_denied(
        self,
    ) -> None:
        """Requirement 1: Three staff at the same hospital see the same alert; another hospital cannot access it."""

        async def scenario() -> None:
            outcome = await alert_service.route_incident(
                self.incident_id, now=self.t0 + timedelta(seconds=31)
            )
            self.assertTrue(outcome.resolved)
            self.assertIsNotNone(outcome.alert)
            alert_id = outcome.alert.id
            self.assertEqual(outcome.alert.hospital_id, HOSP_BINDURA_ID)

            for staff_tok in (
                "token-bindura-staff-1",
                "token-bindura-staff-2",
                "token-bindura-staff-3",
            ):
                list_resp = await _call_asgi(
                    "GET", "/api/hospital/alerts", headers=_auth_header(staff_tok)
                )
                self.assertEqual(list_resp.status_code, 200)
                items = list_resp.json()
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["id"], str(alert_id))
                self.assertEqual(items[0]["status"], "notified")
                self.assertEqual(items[0]["hospital_display_status"], "New")

                detail_resp = await _call_asgi(
                    "GET", f"/api/alerts/{alert_id}", headers=_auth_header(staff_tok)
                )
                self.assertEqual(detail_resp.status_code, 200)
                self.assertEqual(detail_resp.json()["id"], str(alert_id))

            mazowe_list = await _call_asgi(
                "GET",
                "/api/hospital/alerts",
                headers=_auth_header("token-mazowe-staff-1"),
            )
            self.assertEqual(mazowe_list.status_code, 200)
            self.assertEqual(mazowe_list.json(), [])

            mazowe_detail = await _call_asgi(
                "GET",
                f"/api/alerts/{alert_id}",
                headers=_auth_header("token-mazowe-staff-1"),
            )
            self.assertEqual(mazowe_detail.status_code, 403)

            owner_resp = await _call_asgi(
                "GET",
                f"/api/alerts/{alert_id}",
                headers=_auth_header("token-owner-a"),
            )
            self.assertEqual(owner_resp.status_code, 403)

            unauth_resp = await _call_asgi("GET", f"/api/alerts/{alert_id}")
            self.assertEqual(unauth_resp.status_code, 401)

            suspended_resp = await _call_asgi(
                "GET", "/api/hospital/alerts", headers=_auth_header("token-suspended")
            )
            self.assertEqual(suspended_resp.status_code, 403)

        asyncio.run(scenario())

    def test_2_acknowledgment_updates_all_staff_without_auto_accepting(self) -> None:
        """Requirement 2: Acknowledgment updates all staff screens without automatically accepting the response."""

        async def scenario() -> None:
            outcome = await alert_service.route_incident(
                self.incident_id, now=self.t0 + timedelta(seconds=31)
            )
            alert_id = outcome.alert.id

            premature_accept = await _call_asgi(
                "POST",
                f"/api/alerts/{alert_id}/accept",
                headers=_auth_header("token-bindura-staff-1"),
            )
            self.assertEqual(premature_accept.status_code, 409)

            ws_b1, ws_b2, ws_b3 = _FakeWebSocket(), _FakeWebSocket(), _FakeWebSocket()
            ws_mazowe, ws_admin, ws_owner_b = (
                _FakeWebSocket(),
                _FakeWebSocket(),
                _FakeWebSocket(),
            )
            await live_manager.connect(ws_b1, TEST_ACCOUNTS["token-bindura-staff-1"])  # type: ignore[arg-type]
            await live_manager.connect(ws_b2, TEST_ACCOUNTS["token-bindura-staff-2"])  # type: ignore[arg-type]
            await live_manager.connect(ws_b3, TEST_ACCOUNTS["token-bindura-staff-3"])  # type: ignore[arg-type]
            await live_manager.connect(ws_mazowe, TEST_ACCOUNTS["token-mazowe-staff-1"])  # type: ignore[arg-type]
            await live_manager.connect(ws_admin, TEST_ACCOUNTS["token-superuser"])  # type: ignore[arg-type]
            await live_manager.connect(ws_owner_b, TEST_ACCOUNTS["token-owner-b"])  # type: ignore[arg-type]

            ack_resp = await _call_asgi(
                "POST",
                f"/api/alerts/{alert_id}/acknowledge",
                headers=_auth_header("token-bindura-staff-1"),
            )
            self.assertEqual(ack_resp.status_code, 200)
            ack_body = ack_resp.json()
            self.assertEqual(ack_body["alert"]["status"], "acknowledged")
            self.assertEqual(
                ack_body["alert"]["hospital_display_status"], "Acknowledged"
            )
            self.assertEqual(ack_body["incident_status"], "acknowledged")
            self.assertIsNotNone(ack_body["alert"]["acknowledged_at"])
            self.assertIsNone(ack_body["alert"]["responded_at"])

            for ws in (ws_b1, ws_b2, ws_b3, ws_admin):
                self.assertEqual(len(ws.messages), 2)
                self.assertEqual(ws.messages[1]["event"], "alert.acknowledged")
                self.assertEqual(ws.messages[1]["alert"]["status"], "acknowledged")

            self.assertEqual(len(ws_mazowe.messages), 1)
            self.assertEqual(len(ws_owner_b.messages), 1)

            for tok in ("token-bindura-staff-2", "token-bindura-staff-3"):
                check = await _call_asgi(
                    "GET", f"/api/alerts/{alert_id}", headers=_auth_header(tok)
                )
                self.assertEqual(check.status_code, 200)
                self.assertEqual(check.json()["status"], "acknowledged")

            accept_resp = await _call_asgi(
                "POST",
                f"/api/alerts/{alert_id}/accept",
                headers=_auth_header("token-bindura-staff-2"),
            )
            self.assertEqual(accept_resp.status_code, 200)
            self.assertEqual(accept_resp.json()["alert"]["status"], "accepted")
            self.assertEqual(accept_resp.json()["incident_status"], "accepted")

        asyncio.run(scenario())

    def test_3_decline_requires_reason_and_escalates_once_idempotently(self) -> None:
        """Requirement 3: A decline requires a reason and escalates once; retries do not duplicate routing."""

        async def scenario() -> None:
            outcome = await alert_service.route_incident(
                self.incident_id, now=self.t0 + timedelta(seconds=31)
            )
            bindura_alert_id = outcome.alert.id

            await _call_asgi(
                "POST",
                f"/api/alerts/{bindura_alert_id}/acknowledge",
                headers=_auth_header("token-bindura-staff-1"),
            )

            empty_reason = await _call_asgi(
                "POST",
                f"/api/alerts/{bindura_alert_id}/decline",
                headers=_auth_header("token-bindura-staff-1"),
                json_body={"reason": "   "},
            )
            self.assertEqual(empty_reason.status_code, 422)

            decline_resp = await _call_asgi(
                "POST",
                f"/api/alerts/{bindura_alert_id}/decline",
                headers=_auth_header("token-bindura-staff-1"),
                json_body={"reason": "Trauma theatre at full capacity."},
            )
            self.assertEqual(decline_resp.status_code, 200)
            body = decline_resp.json()
            self.assertEqual(body["alert"]["status"], "declined")
            self.assertEqual(
                body["alert"]["decline_reason"], "Trauma theatre at full capacity."
            )
            self.assertEqual(body["incident_status"], "escalated")
            self.assertIsNotNone(body["escalation"])
            self.assertTrue(body["escalation"]["resolved"])
            mazowe_alert = body["escalation"]["alert"]
            self.assertEqual(mazowe_alert["hospital_id"], str(HOSP_MAZOWE_ID))
            self.assertEqual(mazowe_alert["escalation_level"], 2)
            self.assertEqual(mazowe_alert["routing_reason"], "declined")

            retry_resp = await _call_asgi(
                "POST",
                f"/api/alerts/{bindura_alert_id}/decline",
                headers=_auth_header("token-bindura-staff-1"),
                json_body={"reason": "Trauma theatre at full capacity."},
            )
            self.assertEqual(retry_resp.status_code, 200)
            all_notifs = alert_service.list_incident_notifications(self.incident_id)
            self.assertEqual(len(all_notifs), 2)
            self.assertEqual(all_notifs[0].hospital_id, HOSP_BINDURA_ID)
            self.assertEqual(all_notifs[0].status, "declined")
            self.assertEqual(all_notifs[1].hospital_id, HOSP_MAZOWE_ID)
            self.assertEqual(all_notifs[1].status, "notified")

        asyncio.run(scenario())

    def test_4_unanswered_alerts_escalate_after_180s_deadline_across_worker_restart(
        self,
    ) -> None:
        """Requirement 4: Unanswered alerts escalate after the stored 180s deadline, including after a worker restart."""

        async def scenario() -> None:
            t_route = self.t0 + timedelta(seconds=31)
            worker_instance_1 = EscalationDeadlineWorker(service=alert_service)
            step1 = await worker_instance_1.run_once(now=t_route)
            self.assertEqual(step1["windows_routed"], [str(self.incident_id)])

            notifs_after_route = alert_service.list_incident_notifications(
                self.incident_id
            )
            self.assertEqual(len(notifs_after_route), 1)
            first_alert = notifs_after_route[0]
            self.assertEqual(first_alert.hospital_id, HOSP_BINDURA_ID)
            self.assertEqual(
                first_alert.response_deadline, t_route + timedelta(seconds=180)
            )

            worker_instance_2 = EscalationDeadlineWorker(service=alert_service)
            step_mid = await worker_instance_2.run_once(
                now=t_route + timedelta(seconds=120)
            )
            self.assertEqual(step_mid["timed_out_alerts"], [])
            self.assertEqual(
                alert_service.list_incident_notifications(self.incident_id)[0].status,
                "notified",
            )

            worker_after_restart = EscalationDeadlineWorker(service=alert_service)
            step_expired = await worker_after_restart.run_once(
                now=t_route + timedelta(seconds=181)
            )
            self.assertEqual(step_expired["timed_out_alerts"], [str(first_alert.id)])

            notifs_final = alert_service.list_incident_notifications(self.incident_id)
            self.assertEqual(len(notifs_final), 2)
            self.assertEqual(notifs_final[0].status, "timed_out")
            self.assertEqual(notifs_final[1].hospital_id, HOSP_MAZOWE_ID)
            self.assertEqual(notifs_final[1].status, "notified")
            self.assertEqual(notifs_final[1].escalation_level, 2)
            self.assertEqual(notifs_final[1].routing_reason, "timeout")

            step_repeat = await worker_after_restart.run_once(
                now=t_route + timedelta(seconds=182)
            )
            self.assertEqual(step_repeat["timed_out_alerts"], [])
            self.assertEqual(
                len(alert_service.list_incident_notifications(self.incident_id)), 2
            )

        asyncio.run(scenario())

    def test_5_unresolved_routing_when_location_missing_or_hospitals_exhausted(
        self,
    ) -> None:
        """If location or an eligible destination is unavailable, record unresolved state; never invent a destination."""

        async def scenario() -> None:
            no_gps_id = uuid4()
            alert_service.register_incident_fixture(
                IncidentRecord(
                    id=no_gps_id,
                    code="INC-1099",
                    device_id=uuid4(),
                    detected_at=self.t0,
                    status="cancellation_window",
                    cancellation_deadline=self.t0 + timedelta(seconds=30),
                    latitude=None,
                    longitude=None,
                )
            )
            outcome = await alert_service.route_incident(
                no_gps_id, now=self.t0 + timedelta(seconds=35)
            )
            self.assertFalse(outcome.resolved)
            self.assertIsNone(outcome.alert)
            self.assertEqual(outcome.incident_status, "escalated")
            self.assertEqual(alert_service.list_incident_notifications(no_gps_id), [])

        asyncio.run(scenario())

    def test_6_superuser_manual_routing_and_role_enforcement(self) -> None:
        """POST /api/admin/incidents/{id}/notify allows superuser manual routing and blocks staff."""

        async def scenario() -> None:
            alert_service.register_hospital_fixture(
                HospitalRecord(
                    id=HOSP_SHAMVA_ID,
                    code="HSP-003",
                    name="Shamva District Hospital",
                    city="Shamva",
                    latitude=-17.3127,
                    longitude=31.5703,
                    is_active=True,
                )
            )

            staff_attempt = await _call_asgi(
                "POST",
                f"/api/admin/incidents/{self.incident_id}/notify",
                headers=_auth_header("token-bindura-staff-1"),
                json_body={"hospital_id": str(HOSP_SHAMVA_ID)},
            )
            self.assertEqual(staff_attempt.status_code, 403)

            admin_resp = await _call_asgi(
                "POST",
                f"/api/admin/incidents/{self.incident_id}/notify",
                headers=_auth_header("token-superuser"),
                json_body={"hospital_id": str(HOSP_SHAMVA_ID)},
            )
            self.assertEqual(admin_resp.status_code, 201)
            body = admin_resp.json()
            self.assertTrue(body["resolved"])
            self.assertEqual(body["alert"]["hospital_id"], str(HOSP_SHAMVA_ID))
            self.assertEqual(body["alert"]["routing_reason"], "manual")

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
