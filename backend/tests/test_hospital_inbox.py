from types import SimpleNamespace
from uuid import uuid4
import asyncio

import pytest
from fastapi import HTTPException
from app.core.auth import AuthenticatedUser
from app.services import hospital_inbox as module


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}
    def select(self, *_): return self
    def eq(self, key, value):
        self.filters[key] = value
        return self
    def order(self, *args, **kwargs): return self
    def range(self, start, end): return self
    def execute(self):
        return SimpleNamespace(data=[row for row in self.rows if all(str(row.get(k)) == str(v) for k, v in self.filters.items())])


def test_persisted_inbox_scopes_hospital_and_includes_timed_out_history(monkeypatch):
    hospital, other = uuid4(), uuid4()
    rows = [
        {"id": str(uuid4()), "hospital_id": str(hospital), "status": "timed_out"},
        {"id": str(uuid4()), "hospital_id": str(other), "status": "notified"},
    ]
    monkeypatch.setattr(module, "get_supabase_admin", lambda: SimpleNamespace(table=lambda _: Query(rows)))
    monkeypatch.setattr(module, "serialize_alert", lambda row: row)
    staff = AuthenticatedUser(id=uuid4(), full_name="Staff", role="hospital_staff", status="active", hospital_id=hospital)
    inbox = module.HospitalInbox()
    assert inbox.list_hospital_alerts(staff) == [rows[0]]
    assert inbox.list_hospital_alerts(staff, status_filter="notified") == []
    assert inbox.get_authorized_alert(rows[0]["id"], staff) == rows[0]
    with pytest.raises(HTTPException) as error:
        inbox.get_authorized_alert(rows[1]["id"], staff)
    assert error.value.status_code == 404


def test_unassigned_user_cannot_query_database(monkeypatch):
    def forbidden():
        pytest.fail("Unauthorised request reached database")
    monkeypatch.setattr(module, "get_supabase_admin", forbidden)
    user = AuthenticatedUser(id=uuid4(), full_name="Unassigned", role="hospital_staff", status="active")
    with pytest.raises(HTTPException) as error:
        module.HospitalInbox().list_hospital_alerts(user)
    assert error.value.status_code == 403


def test_acknowledgment_uses_database_actor_and_returns_saved_state(monkeypatch):
    staff = AuthenticatedUser(id=uuid4(), full_name="Staff", role="hospital_staff", status="active", hospital_id=uuid4())
    alert_id = uuid4()
    calls = []
    saved = SimpleNamespace(status="notified", incident=SimpleNamespace(status="notified"))
    inbox = module.HospitalInbox()
    monkeypatch.setattr(inbox, "get_authorized_alert", lambda *args: saved)
    def rpc(name, params):
        calls.append((name, params))
        def execute():
            saved.status = "acknowledged"
            saved.incident.status = "acknowledged"
        return SimpleNamespace(execute=execute)
    monkeypatch.setattr(module, "get_supabase_admin", lambda: SimpleNamespace(rpc=rpc))
    monkeypatch.setattr(module, "AlertActionResponse", lambda **kw: SimpleNamespace(**kw))
    result = asyncio.run(inbox.acknowledge_alert(alert_id, staff))
    assert calls == [("hospital_acknowledge_notification", {"p_actor_id": str(staff.id), "p_notification_id": str(alert_id)})]
    assert result.alert.status == result.incident_status == "acknowledged"


def test_wrong_hospital_cannot_acknowledge(monkeypatch):
    staff = AuthenticatedUser(id=uuid4(), full_name="Staff", role="hospital_staff", status="active", hospital_id=uuid4())
    inbox = module.HospitalInbox()
    monkeypatch.setattr(module, "get_supabase_admin", lambda: SimpleNamespace(table=lambda _: Query([])))
    with pytest.raises(HTTPException) as error:
        asyncio.run(inbox.acknowledge_alert(uuid4(), staff))
    assert error.value.status_code == 404


def test_expired_acknowledgment_returns_conflict(monkeypatch):
    staff = AuthenticatedUser(id=uuid4(), full_name="Staff", role="hospital_staff", status="active", hospital_id=uuid4())
    inbox = module.HospitalInbox()
    monkeypatch.setattr(inbox, "get_authorized_alert", lambda *args: None)
    def execute():
        raise module.APIError({"code": "23514", "message": "Expired", "details": None, "hint": None})
    monkeypatch.setattr(module, "get_supabase_admin", lambda: SimpleNamespace(rpc=lambda *args: SimpleNamespace(execute=execute)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(inbox.acknowledge_alert(uuid4(), staff))
    assert error.value.status_code == 409
