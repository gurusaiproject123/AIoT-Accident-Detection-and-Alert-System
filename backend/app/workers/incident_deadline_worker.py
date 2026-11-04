import asyncio
import logging
from datetime import datetime
from typing import Any

from app.services.incident_service import incident_service


logger = logging.getLogger(__name__)


def run_cancellation_deadline_tick(now: datetime | None = None) -> dict[str, Any]:
    """Process all incidents whose stored 30-second cancellation deadline has elapsed."""
    return incident_service.process_due_cancellation_windows(now=now)


async def cancellation_deadline_worker_loop(
    interval_seconds: float = 1.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background worker loop that periodically sweeps stored cancellation deadlines."""
    while stop_event is None or not stop_event.is_set():
        try:
            run_cancellation_deadline_tick()
        except Exception as exc:  # pragma: no cover - defensive worker guard
            logger.warning("Cancellation deadline tick failed: %s", exc)
        await asyncio.sleep(interval_seconds)

