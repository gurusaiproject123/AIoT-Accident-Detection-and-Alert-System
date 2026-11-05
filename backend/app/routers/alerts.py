"""HTTP routes and authenticated WebSocket channel for Section 7: Hospital Alerts & Live Updates.

Endpoints implemented (Victor - `backend-hospital-alerts`):
- GET  /api/hospital/alerts              List notifications assigned to this hospital
- GET  /api/alerts/{id}                  One authorized notification
- POST /api/alerts/{id}/acknowledge      Confirm receipt
- POST /api/alerts/{id}/accept           Record willingness to respond
- POST /api/alerts/{id}/decline          Decline with a required reason
- POST /api/admin/incidents/{id}/notify  Superuser manually routes an incident
- WS   /api/ws                           Authenticated scoped live update channel
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.core.auth import (
    AuthenticatedUser,
    require_hospital_staff,
    require_hospital_staff_or_superuser,
    require_superuser,
    verify_access_token,
)
from app.schemas.alerts import (
    AlertActionResponse,
    AlertDeclineRequest,
    HospitalAlertResponse,
    ManualNotifyRequest,
    NotificationStatus,
    RoutingOutcomeResponse,
)
from app.services.alert_service import HospitalAlertService, alert_service
from app.services.websocket_manager import live_manager

router = APIRouter(tags=["Hospital Alerts"])


def get_alert_service() -> HospitalAlertService:
    """Dependency returning the shared HospitalAlertService instance."""
    return alert_service


@router.get(
    "/api/hospital/alerts",
    response_model=list[HospitalAlertResponse],
    summary="List notifications assigned to the caller's verified hospital",
)
async def list_hospital_alerts(
    caller: Annotated[AuthenticatedUser, Depends(require_hospital_staff)],
    service: Annotated[HospitalAlertService, Depends(get_alert_service)],
    status_filter: Annotated[
        NotificationStatus | None,
        Query(alias="status", description="Optional notification status filter."),
    ] = None,
) -> list[HospitalAlertResponse]:
    """Return all hospital notifications assigned to the signed-in staff member's hospital.

    The caller's verified `hospital_id` determines the scope; any hospital ID supplied
    by the browser is never trusted as authorization.
    """
    return service.list_hospital_alerts(caller, status_filter=status_filter)


@router.get(
    "/api/alerts/{id}",
    response_model=HospitalAlertResponse,
    summary="Retrieve one authorized hospital notification",
)
async def get_alert(
    id: UUID,
    caller: Annotated[AuthenticatedUser, Depends(require_hospital_staff_or_superuser)],
    service: Annotated[HospitalAlertService, Depends(get_alert_service)],
) -> HospitalAlertResponse:
    """Return one `incident_notifications` record if the caller is assigned to that hospital or is a superuser."""
    return service.get_authorized_alert(id, caller)


@router.post(
    "/api/alerts/{id}/acknowledge",
    response_model=AlertActionResponse,
    summary="Confirm receipt of an assigned hospital alert",
)
async def acknowledge_alert(
    id: UUID,
    caller: Annotated[AuthenticatedUser, Depends(require_hospital_staff)],
    service: Annotated[HospitalAlertService, Depends(get_alert_service)],
) -> AlertActionResponse:
    """Record that hospital staff have seen the alert without automatically accepting the response."""
    return await service.acknowledge_alert(id, caller)


@router.post(
    "/api/alerts/{id}/accept",
    response_model=AlertActionResponse,
    summary="Record willingness to respond to an acknowledged alert",
)
async def accept_alert(
    id: UUID,
    caller: Annotated[AuthenticatedUser, Depends(require_hospital_staff)],
    service: Annotated[HospitalAlertService, Depends(get_alert_service)],
) -> AlertActionResponse:
    """Record that the assigned hospital agrees to respond (requires prior acknowledgment)."""
    return await service.accept_alert(id, caller)


@router.post(
    "/api/alerts/{id}/decline",
    response_model=AlertActionResponse,
    summary="Decline an assigned alert with a mandatory reason and escalate",
)
async def decline_alert(
    id: UUID,
    payload: AlertDeclineRequest,
    caller: Annotated[AuthenticatedUser, Depends(require_hospital_staff)],
    service: Annotated[HospitalAlertService, Depends(get_alert_service)],
) -> AlertActionResponse:
    """Decline the response with a required reason and escalate to the next eligible hospital."""
    return await service.decline_alert(id, payload.reason, caller)


@router.post(
    "/api/admin/incidents/{id}/notify",
    response_model=RoutingOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Superuser manually routes an incident to an active hospital",
)
async def admin_manual_notify(
    id: UUID,
    payload: ManualNotifyRequest,
    caller: Annotated[AuthenticatedUser, Depends(require_superuser)],
    service: Annotated[HospitalAlertService, Depends(get_alert_service)],
) -> RoutingOutcomeResponse:
    """Manually route an incident to a specified active hospital and notify its staff."""
    return await service.manual_notify_hospital(id, payload.hospital_id, caller)


@router.websocket("/api/ws")
async def websocket_live_updates(websocket: WebSocket) -> None:
    """Authenticated WebSocket channel for real-time hospital alerts and admin monitoring.

    Authenticates before accepting or transmitting any data. Token can be supplied
    via `Authorization: Bearer <token>` header or `?token=<token>` query parameter.
    Subscriptions are strictly derived from the caller's verified role and assignment.
    """
    token = websocket.headers.get("Authorization") or websocket.query_params.get("token")
    try:
        user = verify_access_token(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if user.role == "unassigned":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if user.role == "hospital_staff" and user.hospital_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if user.role == "car_owner" and user.owner_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await live_manager.connect(websocket, user)
    try:
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        live_manager.disconnect(websocket)
    except Exception:
        live_manager.disconnect(websocket)
