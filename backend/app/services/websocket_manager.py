"""Scoped WebSocket connection manager for `/api/ws` (Section 7).

Requirements from the Backend Development Guide:
- Authenticate before transmitting data.
- Derive staff hospital and owner subscriptions from verified assignments,
  and authorize admin monitoring separately.
- Do not broadcast every incident to every connected user.
- One hospital user's acknowledgment updates the shared notification and all
  that hospital's screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.core.auth import AuthenticatedUser


@dataclass
class _ClientConnection:
    websocket: WebSocket
    user: AuthenticatedUser


class LiveConnectionManager:
    """Manages authenticated WebSocket clients and scoped fan-out."""

    def __init__(self) -> None:
        self._connections: list[_ClientConnection] = []

    @property
    def active_connections(self) -> list[_ClientConnection]:
        return list(self._connections)

    async def connect(self, websocket: WebSocket, user: AuthenticatedUser) -> None:
        """Accept an authenticated WebSocket and send its initial subscription scope."""
        await websocket.accept()
        self._connections.append(_ClientConnection(websocket=websocket, user=user))
        await websocket.send_json(
            {
                "event": "session.ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scope": {
                    "user_id": str(user.id),
                    "role": user.role,
                    "hospital_id": str(user.hospital_id) if user.hospital_id else None,
                    "owner_id": str(user.owner_id) if user.owner_id else None,
                },
            }
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a closed WebSocket connection."""
        self._connections = [
            conn for conn in self._connections if conn.websocket is not websocket
        ]

    async def broadcast_hospital_and_admins(
        self,
        *,
        hospital_id: UUID | None,
        event: str,
        payload: dict[str, Any],
        owner_id: UUID | None = None,
    ) -> int:
        """Send an event only to staff of `hospital_id`, superuser monitors, and optionally `owner_id`.

        Never broadcasts to unrelated hospitals or unrelated car owners.
        Returns the number of sockets that received the message.
        """
        message = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hospital_id": str(hospital_id) if hospital_id else None,
            **payload,
        }
        delivered = 0
        stale: list[WebSocket] = []

        for conn in list(self._connections):
            user = conn.user
            should_receive = False

            if user.role == "superuser" and user.hospital_id is None:
                should_receive = True
            elif (
                user.role == "hospital_staff"
                and hospital_id is not None
                and user.hospital_id == hospital_id
            ):
                should_receive = True
            elif (
                user.role == "car_owner"
                and owner_id is not None
                and user.owner_id == owner_id
            ):
                should_receive = True

            if not should_receive:
                continue

            try:
                await conn.websocket.send_json(message)
                delivered += 1
            except Exception:
                stale.append(conn.websocket)

        for ws in stale:
            self.disconnect(ws)

        return delivered


live_manager = LiveConnectionManager()

