import hashlib
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin
from app.core.device_security import AuthenticatedDevice, require_device
from app.schemas.heartbeat import DeviceHeartbeat, HeartbeatResult
from app.schemas.telemetry import (
    TelemetryPacket,
    TelemetryPrediction,
    TelemetryResult,
)
from app.services.telemetry_processing import process_packet


logger = logging.getLogger(__name__)

MODEL_NAME = "random_forest"
MODEL_VERSION = "vzcrash-full-data-v1"

router = APIRouter(
    prefix="/api/devices",
    tags=["Device - Reporting"],
)

DEVICE_ERRORS = {
    "28000": (401, "Missing or invalid device credentials."),
    "42501": (403, "Device is inactive."),
}

HEARTBEAT_ERRORS = {
    **DEVICE_ERRORS,
    "23514": (409, "Device vehicle binding does not match."),
    "22023": (422, "Invalid heartbeat data."),
    "22P02": (422, "Invalid heartbeat data."),
    "23502": (422, "Invalid heartbeat data."),
    "40001": (409, "Device configuration changed. Retry the heartbeat."),
    "40P01": (409, "Device configuration changed. Retry the heartbeat."),
}

INVALID_TELEMETRY = (
    422,
    "Invalid packet metadata, readings or timestamps. "
    "Check device clock synchronization.",
)
RETRY_TELEMETRY = (
    409,
    "A concurrent change occurred. Retry the same packet.",
)

TELEMETRY_ERRORS = {
    **DEVICE_ERRORS,
    "23514": (409, "Device vehicle binding does not match."),
    "23505": (
        409,
        "This boot ID and sequence number were already "
        "used with different packet content.",
    ),
    "22023": INVALID_TELEMETRY,
    "22P02": INVALID_TELEMETRY,
    "22003": INVALID_TELEMETRY,
    "23502": INVALID_TELEMETRY,
    "23503": INVALID_TELEMETRY,
    "40001": RETRY_TELEMETRY,
    "40P01": RETRY_TELEMETRY,
}

CANCELLATION_ERRORS = {
    **DEVICE_ERRORS,
    "P0002": (404, "Incident not found for this device."),
    "23514": (409, "The cancellation window is closed."),
    "40001": (409, "A concurrent change occurred. Retry cancellation."),
    "40P01": (409, "A concurrent change occurred. Retry cancellation."),
}


def rpc_error(
    exc: APIError,
    errors: dict[str, tuple[int, str]],
    fallback: str,
) -> HTTPException:
    status, detail = errors.get(exc.code, (503, fallback))
    return HTTPException(status_code=status, detail=detail)


@router.post("/{device_id}/heartbeat", response_model=HeartbeatResult)
def record_heartbeat(
    device_id: UUID,
    payload: DeviceHeartbeat,
    response: Response,
    device: AuthenticatedDevice = Depends(require_device),
):
    """Record an authenticated device heartbeat."""
    db = get_supabase_admin()

    try:
        result = db.rpc(
            "device_record_heartbeat",
            {
                "p_device_id": str(device.id),
                "p_secret_hash": device.credential_hash,
                "p_vehicle_id": (
                    str(payload.vehicle_id)
                    if payload.vehicle_id is not None
                    else None
                ),
                "p_firmware_version": payload.firmware_version,
            },
        ).execute()
    except APIError as exc:
        raise rpc_error(
            exc, HEARTBEAT_ERRORS, "Heartbeat could not be recorded."
        ) from None
    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Could not confirm heartbeat receipt.",
        ) from None

    if not isinstance(result.data, dict):
        raise HTTPException(
            status_code=503,
            detail="Heartbeat returned an unexpected result.",
        )

    response.headers["Cache-Control"] = "no-store"
    return result.data


@router.post("/{device_id}/telemetry", response_model=TelemetryResult)
def receive_telemetry(
    device_id: UUID,
    payload: TelemetryPacket,
    response: Response,
    device: AuthenticatedDevice = Depends(require_device),
):
    """Save telemetry, score new full windows, and open suspected incidents."""
    normalized_payload = payload.model_dump(mode="json")

    # Hash the validated packet without including the device credential.
    canonical_json = json.dumps(
        normalized_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    payload_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    db = get_supabase_admin()

    try:
        result = db.rpc(
            "device_ingest_telemetry",
            {
                "p_device_id": str(device.id),
                "p_secret_hash": device.credential_hash,
                "p_payload": normalized_payload,
                "p_payload_sha256": payload_hash,
            },
        ).execute()
    except APIError as exc:
        raise rpc_error(
            exc, TELEMETRY_ERRORS, "Telemetry could not be saved."
        ) from None
    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm telemetry receipt. "
                "Retry the identical packet with the same boot ID "
                "and sequence number."
            ),
        ) from None

    if (
        not isinstance(result.data, dict)
        or not isinstance(result.data.get("duplicate"), bool)
        or not result.data.get("packet_id")
    ):
        raise HTTPException(
            status_code=503,
            detail="Telemetry returned an unexpected result.",
        )

    response.headers["Cache-Control"] = "no-store"
    packet_id = str(result.data["packet_id"])
    try:
        processed = process_packet(db, packet_id, device.id, normalized_payload)
    except Exception:
        logger.exception("Packet stored but inference/incident processing is incomplete: %s", packet_id)
        raise HTTPException(
            status_code=503,
            detail=("Telemetry was stored but processing is incomplete. Retry the IDENTICAL "
                    "packet with the same boot ID and sequence number."),
        ) from None

    return {**result.data, **processed}



@router.post("/{device_id}/incidents/{incident_id}/cancel")
def cancel_device_incident(
    device_id: UUID,
    incident_id: UUID,
    response: Response,
    device: AuthenticatedDevice = Depends(require_device),
):
    """Cancel an incident reported by this device before its deadline."""
    db = get_supabase_admin()

    try:
        result = db.rpc(
            "device_cancel_incident",
            {
                "p_device_id": str(device.id),
                "p_secret_hash": device.credential_hash,
                "p_incident_id": str(incident_id),
            },
        ).execute()
    except APIError as exc:
        raise rpc_error(
            exc, CANCELLATION_ERRORS, "Could not confirm cancellation."
        ) from None
    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Could not confirm cancellation. Retry the same request.",
        ) from None

    if not isinstance(result.data, dict):
        raise HTTPException(
            status_code=503,
            detail="Cancellation returned an unexpected result.",
        )

    response.headers["Cache-Control"] = "no-store"
    return result.data