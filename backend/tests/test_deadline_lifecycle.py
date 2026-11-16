import asyncio
import threading

from app.main import app
from app.workers import incident_deadline_worker as worker


def test_app_lifespan_runs_deadlines_off_event_loop_and_stops(monkeypatch):
    thread_ids = []

    def tick():
        thread_ids.append(threading.get_ident())
        return {}

    monkeypatch.setattr(worker, "run_cancellation_deadline_tick", tick)

    async def scenario():
        async with app.router.lifespan_context(app):
            async with asyncio.timeout(2):
                while not thread_ids:
                    await asyncio.sleep(0.01)
            assert thread_ids[0] != threading.get_ident()
        count = len(thread_ids)
        await asyncio.sleep(0.05)
        assert len(thread_ids) == count

    asyncio.run(scenario())


def test_worker_retries_after_database_failure(monkeypatch):
    calls = []

    def tick():
        calls.append(True)
        if len(calls) == 1:
            raise RuntimeError("Database temporarily unavailable")
        return {}

    monkeypatch.setattr(worker, "run_cancellation_deadline_tick", tick)

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(worker.cancellation_deadline_worker_loop(0.01, stop))
        try:
            async with asyncio.timeout(2):
                while len(calls) < 2:
                    await asyncio.sleep(0.01)
        finally:
            stop.set()
            await task

    asyncio.run(scenario())
