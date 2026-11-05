"""Durable deadline worker for cancellation windows and 180s hospital acknowledgment timeouts.

Requirements from the Backend Development Guide (Section 7 & Section 9):
- Cancellation deadline worker calls `alert_service.route_incident(...)`.
- Unanswered hospital alerts escalate after the stored 180 second deadline,
  including after a worker restart.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.services.alert_service import HospitalAlertService, alert_service


class EscalationDeadlineWorker:
    """Evaluates stored cancellation and hospital acknowledgment deadlines."""

    def __init__(
        self,
        service: HospitalAlertService | None = None,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self._service = service or alert_service
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    async def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Run one pass over stored deadlines (safe across worker restarts)."""
        return await self._service.process_due_deadlines(now=now)

    async def _loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                pass
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.poll_interval_seconds
                )
            except asyncio.TimeoutError:
                continue

    async def start(self) -> None:
        """Start background polling loop."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Stop background polling loop cleanly."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            except Exception:
                pass
            self._task = None


escalation_worker = EscalationDeadlineWorker()

