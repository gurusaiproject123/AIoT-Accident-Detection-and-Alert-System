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
    logger.info("Incident deadline worker started; checking stored deadlines every %ss", interval_seconds)
    while stop_event is None or not stop_event.is_set():
        try:
            # The database client is synchronous; keep it off the API event loop.
            await asyncio.to_thread(run_cancellation_deadline_tick)
        except Exception as exc:  # pragma: no cover - defensive worker guard
            logger.exception("Cancellation deadline tick failed: %s", exc)
        if stop_event is None:
            await asyncio.sleep(interval_seconds)
        else:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass

