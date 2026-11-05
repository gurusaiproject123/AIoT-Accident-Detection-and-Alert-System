from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeviceHeartbeat(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # Required field. Use null only for an unassigned device.
    vehicle_id: UUID | None

    firmware_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )


class HeartbeatResult(BaseModel):
    device_id: UUID
    device_code: str
    vehicle_id: UUID | None
    status: Literal["online"]
    last_seen_at: datetime
    firmware_version: str | None