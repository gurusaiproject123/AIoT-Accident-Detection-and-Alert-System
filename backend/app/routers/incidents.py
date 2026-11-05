from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Response, status

from app.core.device_security import AuthenticatedDevice, require_device
from app.core.permissions import (
    require_car_owner,
    require_hospital_staff,
    require_staff_or_superuser,
)
from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.incident import (
    FalseAlarmReportCreate,
    FalseAlarmReportResponse,
    IncidentCancelRequest,
    IncidentCloseRequest,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentNoteCreate,
    IncidentNoteResponse,
    IncidentStatus,
    IncidentTimelineResponse,
)
from app.services.incident_service import incident_service


router = APIRouter(tags=["Incidents"])


@router.get(
    "/api/incidents",
    response_model=IncidentListResponse,
)
def list_permitted_incidents(
    response: Response,
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
):
    """List incidents permitted for the signed-in caller."""
    result = incident_service.list_incidents(
        user,
        status=incident_status,
        limit=limit,
        offset=offset,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/api/incidents/{incident_id}",
    response_model=IncidentDetailResponse,
)
def get_permitted_incident(
    incident_id: UUID,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    """Retrieve permitted incident details for the signed-in caller."""
    result = incident_service.get_incident(incident_id, user)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/api/incidents/{incident_id}/timeline",
    response_model=IncidentTimelineResponse,
)
def get_incident_timeline(
    incident_id: UUID,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    """Retrieve permitted event history for an incident."""
    result = incident_service.get_timeline(incident_id, user)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/api/incidents/{incident_id}/cancel",
    response_model=IncidentDetailResponse,
)
def cancel_incident_by_owner(
    incident_id: UUID,
    response: Response,
    payload: IncidentCancelRequest | None = Body(default=None),
    user: CurrentUser = Depends(require_car_owner),
):
    """Owner requests cancellation of their incident during the 30-second window."""
    req = payload or IncidentCancelRequest()
    result = incident_service.cancel_by_owner(incident_id, user, req)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/api/devices/{device_id}/incidents/{incident_id}/cancel",
    response_model=IncidentDetailResponse,
)
def cancel_incident_by_device(
    device_id: UUID,
    incident_id: UUID,
    response: Response,
    payload: IncidentCancelRequest | None = Body(default=None),
    device: AuthenticatedDevice = Depends(require_device),
):
    """Device cancellation for its own incident during the 30-second window."""
    req = payload or IncidentCancelRequest()
    result = incident_service.cancel_by_device(
        device_id, incident_id, device, req
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/api/incidents/{incident_id}/notes",
    response_model=IncidentNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_incident_note(
    incident_id: UUID,
    payload: IncidentNoteCreate,
    response: Response,
    user: CurrentUser = Depends(require_staff_or_superuser),
):
    """Authorized hospital staff or superuser adds a note to an incident."""
    result = incident_service.add_note(incident_id, user, payload)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/api/incidents/{incident_id}/false-alarm-reports",
    response_model=FalseAlarmReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_false_alarm_report(
    incident_id: UUID,
    payload: FalseAlarmReportCreate,
    response: Response,
    user: CurrentUser = Depends(require_hospital_staff),
):
    """Assigned hospital submits a false-alarm review report (does not cancel incident)."""
    result = incident_service.report_false_alarm(incident_id, user, payload)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/api/incidents/{incident_id}/close",
    response_model=IncidentDetailResponse,
)
def close_incident(
    incident_id: UUID,
    response: Response,
    payload: IncidentCloseRequest | None = Body(default=None),
    user: CurrentUser = Depends(require_staff_or_superuser),
):
    """Authorized responder or superuser records incident closure."""
    req = payload or IncidentCloseRequest()
    result = incident_service.close_incident(
        incident_id, user, req, is_admin_endpoint=False
    )
    response.headers["Cache-Control"] = "no-store"
    return result

