from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Response

from app.core.permissions import require_superuser
from app.schemas.auth import CurrentUser
from app.schemas.incident import (
    IncidentCloseRequest,
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentStatus,
)
from app.services.incident_service import incident_service


router = APIRouter(
    prefix="/api/admin/incidents",
    tags=["Admin - Incidents"],
    dependencies=[Depends(require_superuser)],
)


@router.get(
    "",
    response_model=IncidentListResponse,
)
def admin_list_incidents(
    response: Response,
    incident_status: IncidentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_superuser),
):
    """Superuser lists all incidents across the platform."""
    result = incident_service.list_incidents(
        user,
        status=incident_status,
        limit=limit,
        offset=offset,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
)
def admin_get_incident(
    incident_id: UUID,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Superuser retrieves full incident details, timeline state, and review reports."""
    result = incident_service.get_incident(incident_id, user)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(
    "/{incident_id}/close",
    response_model=IncidentDetailResponse,
)
def admin_close_incident(
    incident_id: UUID,
    response: Response,
    payload: IncidentCloseRequest | None = Body(default=None),
    user: CurrentUser = Depends(require_superuser),
):
    """Superuser closes an incident with an outcome or closing note."""
    req = payload or IncidentCloseRequest()
    result = incident_service.close_incident(
        incident_id, user, req, is_admin_endpoint=True
    )
    response.headers["Cache-Control"] = "no-store"
    return result

