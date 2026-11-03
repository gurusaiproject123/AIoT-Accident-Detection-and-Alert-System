import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin
from app.core.device_security import (
    AuthenticatedDevice,
    require_device,
)
from app.schemas.heartbeat import DeviceHeartbeat, HeartbeatResult
from app.schemas.telemetry import TelemetryPacket, TelemetryResult


router = APIRouter(
    prefix="/api/devices",
    tags=["Device - Reporting"],
)


@router.post(
    "/{device_id}/heartbeat",
    response_model=HeartbeatResult,
)
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
        if exc.code == "28000":
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid device credentials.",
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Device is inactive.",
            ) from None

        if exc.code == "23514":
            raise HTTPException(
                status_code=409,
                detail="Device vehicle binding does not match.",
            ) from None

        if exc.code in {"22023", "22P02", "23502"}:
            raise HTTPException(
                status_code=422,
                detail="Invalid heartbeat data.",
            ) from None

        if exc.code in {"40001", "40P01"}:
            raise HTTPException(
                status_code=409,
                detail="Device configuration changed. Retry the heartbeat.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Heartbeat could not be recorded.",
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


@router.post(
    "/{device_id}/telemetry",
    response_model=TelemetryResult,
)
def receive_telemetry(
    device_id: UUID,
    payload: TelemetryPacket,
    response: Response,
    device: AuthenticatedDevice = Depends(require_device),
):
    """Save a validated sensor packet without running accident detection."""

    normalized_payload = payload.model_dump(mode="json")

    # Normalize serialization so identical validated content hashes equally.
    # Device credentials are never included in the packet hash.
    canonical_json = json.dumps(
        normalized_payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    payload_hash = hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()

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
        if exc.code == "28000":
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid device credentials.",
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Device is inactive.",
            ) from None

        if exc.code == "23514":
            raise HTTPException(
                status_code=409,
                detail="Device vehicle binding does not match.",
            ) from None

        if exc.code == "23505":
            raise HTTPException(
                status_code=409,
                detail=(
                    "This boot ID and sequence number were already "
                    "used with different packet content."
                ),
            ) from None

        if exc.code in {
            "22023",
            "22P02",
            "22003",
            "23502",
            "23503",
        }:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid packet metadata, readings or timestamps. "
                    "Check device clock synchronization."
                ),
            ) from None

        if exc.code in {"40001", "40P01"}:
            raise HTTPException(
                status_code=409,
                detail="A concurrent change occurred. Retry the same packet.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Telemetry could not be saved.",
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

    if not isinstance(result.data, dict):
        raise HTTPException(
            status_code=503,
            detail="Telemetry returned an unexpected result.",
        )

    response.headers["Cache-Control"] = "no-store"

    return {
        **result.data,
        "detection_performed": False,
    }