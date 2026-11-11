"""Single-process prototype lease broker. No command-table polling."""
import asyncio
import time
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import HTTPException

LEASE_SECONDS = 30
COMMAND_LIFETIME_MS = 350


@dataclass
class Link:
    channel: str = field(default_factory=lambda: str(uuid4()))
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=4))
    last_seen: float = field(default_factory=time.monotonic)
    last_ack: dict | None = None
    drive_ready: bool = False


@dataclass
class Lease:
    id: str
    actor: str
    vehicle: str
    device: str
    channel: str
    expires: float
    sequence: int = 0


class ControlRuntime:
    """All mutations run on the single ASGI event loop, without intervening await."""
    def __init__(self):
        self.links = {}
        self.leases = {}

    def online(self, device):
        link = self.links.get(device)
        if link is None or not link.drive_ready or time.monotonic() - link.last_seen > 3:
            raise HTTPException(409, "Device live-control connection is unavailable.")
        return link

    def acquire(self, actor, vehicle, device):
        link = self.online(device)
        now = time.monotonic()
        self.prune()
        if any(s.vehicle == vehicle and s.expires > now for s in self.leases.values()):
            raise HTTPException(409, "This vehicle already has a controller lease.")
        lease = Lease(str(uuid4()), actor, vehicle, device, link.channel, now + LEASE_SECONDS)
        link.last_ack = None
        self.leases[lease.id] = lease
        return lease

    def get(self, session, actor):
        lease = self.leases.get(session)
        if not lease or lease.actor != actor:
            raise HTTPException(404, "Controller session not found.")
        if lease.expires <= time.monotonic():
            self.end(lease)
            raise HTTPException(409, "Controller lease expired; acquire a new lease.")
        link = self.online(lease.device)
        if link.channel != lease.channel:
            self.end(lease)
            raise HTTPException(409, "Device reconnected; acquire a new lease.")
        return lease

    def enqueue(self, lease, sequence, direction, speed, sent_at):
        link = self.online(lease.device)
        if link.channel != lease.channel or lease.expires <= time.monotonic():
            raise HTTPException(409, "Controller lease is no longer valid.")
        if sequence <= lease.sequence:
            raise HTTPException(409, "Replayed or out-of-order command.")
        age = time.time() - sent_at
        if age > 1.0 or age < -0.5:
            raise HTTPException(422, "Command is stale or the phone clock is incorrect.")
        now_ms = int(time.time() * 1000)
        message = {
            "type": "command", "channel": link.channel, "lease_id": lease.id,
            "seq": sequence, "direction": direction, "speed": speed,
            "issued_ms": now_ms,
            "expires_ms": now_ms + min(COMMAND_LIFETIME_MS,
                max(0, int((lease.expires - time.monotonic()) * 1000))),
        }
        if link.queue.full():
            self.end(lease)
            raise HTTPException(409, "Live transport congested; controller stopped.")
        lease.sequence = sequence
        link.queue.put_nowait(message)
        return message

    def end(self, lease):
        self.leases.pop(lease.id, None)
        link = self.links.get(lease.device)
        if link:
            while not link.queue.empty():
                link.queue.get_nowait()
            link.queue.put_nowait({"type": "stop", "channel": link.channel})

    def stop_device(self, device):
        link = self.links.get(device)
        if link:
            while not link.queue.empty():
                link.queue.get_nowait()
            link.queue.put_nowait({"type": "stop", "channel": link.channel})

    def stop_vehicle(self, vehicle):
        for lease in list(self.leases.values()):
            if lease.vehicle == vehicle:
                self.end(lease)

    def prune(self):
        for lease in list(self.leases.values()):
            if lease.expires <= time.monotonic():
                self.end(lease)


runtime = ControlRuntime()
