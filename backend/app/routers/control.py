"""Owner-authorized live prototype driving. Run ONE Uvicorn worker."""
import asyncio
import contextlib
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool
from httpx import HTTPError
from postgrest.exceptions import APIError
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.database import get_supabase_admin
from app.core.device_security import require_device
from app.core.security import get_current_user
from app.schemas.auth import CurrentUser
from app.services.control_runtime import Link, LEASE_SECONDS, runtime

router = APIRouter(tags=["Owner - Live Control"])


class Movement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence_number: int = Field(strict=True, ge=1, le=2_000_000_000)
    direction: Literal["forward", "reverse", "left", "right", "stop"]
    speed: int = Field(strict=True, ge=0, le=120)
    sent_at: AwareDatetime


from app.services.owner_registry import drive_assignment as owner_assignment, owned_vehicle, active_device


async def checked_lease(session_id, user):
    lease = runtime.get(str(session_id), str(user.id))
    device = await run_in_threadpool(owner_assignment, lease.vehicle, user)
    # Recheck after database I/O; another request may have ended the lease.
    lease = runtime.get(str(session_id), str(user.id))
    if device != lease.device:
        runtime.end(lease)
        raise HTTPException(409, "Device binding changed; controller stopped.")
    return lease


def lease_result(lease):
    import time
    link = runtime.links.get(lease.device)
    return {"id": lease.id, "vehicle_id": lease.vehicle,
            "expires_in_seconds": max(0, lease.expires - time.monotonic()),
            "last_sequence": lease.sequence,
            "device_ack": link.last_ack if link else None}


@router.post("/api/vehicles/{vehicle_id}/control-sessions", status_code=201)
async def acquire(vehicle_id: UUID, response: Response, user: CurrentUser = Depends(get_current_user)):
    device = await run_in_threadpool(owner_assignment, str(vehicle_id), user)
    lease = runtime.acquire(str(user.id), str(vehicle_id), device)
    response.headers["Cache-Control"] = "no-store"
    return lease_result(lease)


@router.post("/api/control-sessions/{session_id}/commands", status_code=202)
async def command(session_id: UUID, payload: Movement, response: Response,
                  user: CurrentUser = Depends(get_current_user)):
    lease = await checked_lease(session_id, user)
    message = runtime.enqueue(lease, payload.sequence_number, payload.direction,
                              payload.speed, payload.sent_at.timestamp())
    response.headers["Cache-Control"] = "no-store"
    return {"queued": True, "sequence_number": message["seq"],
            "device_applied": False, "message": "Queued; inspect device acknowledgment."}


@router.post("/api/control-sessions/{session_id}/renew")
async def renew(session_id: UUID, response: Response, user: CurrentUser = Depends(get_current_user)):
    import time
    lease = await checked_lease(session_id, user)
    lease.expires = time.monotonic() + LEASE_SECONDS
    response.headers["Cache-Control"] = "no-store"
    return lease_result(lease)


@router.get("/api/control-sessions/{session_id}")
async def status(session_id: UUID, response: Response, user: CurrentUser = Depends(get_current_user)):
    lease = await checked_lease(session_id, user)
    response.headers["Cache-Control"] = "no-store"
    return lease_result(lease)


@router.post("/api/control-sessions/{session_id}/end")
async def end(session_id: UUID, user: CurrentUser = Depends(get_current_user)):
    # End remains idempotent and does not require an online device.
    lease = runtime.leases.get(str(session_id))
    if lease and lease.actor != str(user.id):
        raise HTTPException(404, "Controller session not found.")
    if user.role != "car_owner" or user.status != "active":
        raise HTTPException(403, "Active car-owner access is required.")
    if lease:
        runtime.end(lease)
    return {"ended": True, "stop_requested": True, "device_applied": False}


@router.post("/api/vehicles/{vehicle_id}/stop")
async def stop(vehicle_id: UUID, user: CurrentUser = Depends(get_current_user)):
    def stop_assignment():
        db = get_supabase_admin()
        owned_vehicle(db, vehicle_id, user)
        return active_device(db, vehicle_id)
    try:
        device = await run_in_threadpool(stop_assignment)
    except (APIError, HTTPError):
        raise HTTPException(503, "Unable to verify owned vehicle.") from None
    runtime.stop_vehicle(str(vehicle_id))
    if device:
        runtime.stop_device(str(device["id"]))
    return {"stop_requested": True, "device_applied": False}


@router.websocket("/api/devices/{device_id}/control-stream")
async def control_stream(websocket: WebSocket, device_id: UUID):
    # Explicitly reuse the existing device credential verifier.
    try:
        await run_in_threadpool(require_device, device_id, websocket.headers.get("x-device-secret"))
    except HTTPException:
        await websocket.close(code=1008)
        return
    key = str(device_id)
    if key in runtime.links:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    link = Link()
    runtime.links[key] = link
    sender = None
    async def send_messages():
        import time
        while True:
            message = await link.queue.get()
            if message["type"] == "command" and message["expires_ms"] <= int(time.time()*1000):
                message = {"type": "stop", "channel": link.channel}
            await websocket.send_json(message)
    try:
        await websocket.send_json({"type": "ready", "channel": link.channel})
        sender = asyncio.create_task(send_messages())
        import time
        checked_at = time.monotonic()
        while True:
            # Device watchdog acts even if this socket task stops making progress.
            message = await asyncio.wait_for(websocket.receive_json(), timeout=4)
            if time.monotonic() - checked_at >= 1:
                await run_in_threadpool(require_device, device_id, websocket.headers.get("x-device-secret"))
                checked_at = time.monotonic()
            link.last_seen = time.monotonic()
            if isinstance(message, dict) and message.get("type") == "alive":
                link.drive_ready = message.get("drive_ready") is True
            if isinstance(message, dict) and message.get("type") == "ack":
                sid = str(message.get("lease_id", ""))
                lease = runtime.leases.get(sid)
                if lease and lease.device == key and lease.channel == link.channel:
                    sequence = message.get("seq")
                    if isinstance(sequence, int) and sequence == lease.sequence:
                        link.last_ack = {
                            "lease_id": sid, "seq": sequence,
                            "applied": message.get("applied") is True,
                            "reason": str(message.get("reason", ""))[:80],
                            "received_ms": int(time.time()*1000),
                        }
    except (WebSocketDisconnect, asyncio.TimeoutError, HTTPException, ValueError):
        pass
    finally:
        if sender:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await sender
        if runtime.links.get(key) is link:
            runtime.links.pop(key, None)
            for lease in list(runtime.leases.values()):
                if lease.device == key:
                    runtime.end(lease)
        with contextlib.suppress(Exception):
            await websocket.close()


@router.get("/control-test", response_class=HTMLResponse, include_in_schema=False)
def control_test():
    return HTMLResponse(Path(__file__).with_name("control_test.html").read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})
