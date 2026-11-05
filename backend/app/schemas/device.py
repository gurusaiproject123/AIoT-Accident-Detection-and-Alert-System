from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


class DeviceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    device_code: str = Field(pattern=r"^[A-Z0-9-]{3,40}$")
    vehicle_id: UUID | None = None
    label: str | None = Field(default=None, max_length=200)
    firmware_version: str | None = Field(default=None, max_length=100)
    is_active: StrictBool = True

    @field_validator("device_code", mode="before")
    @classmethod
    def normalize_code(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    vehicle_id: UUID | None = None
    label: str | None = Field(default=None, max_length=200)
    firmware_version: str | None = Field(default=None, max_length=100)
    is_active: StrictBool | None = None
    rotate_secret: StrictBool = False

    @model_validator(mode="after")
    def validate_changes(self):
        configuration_fields = self.model_fields_set - {"rotate_secret"}

        if not configuration_fields and not self.rotate_secret:
            raise ValueError("Provide a device change.")

        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("is_active cannot be null.")

        return self


class DevicePublic(BaseModel):
    id: UUID
    device_code: str
    vehicle_id: UUID | None
    label: str | None
    status: str
    gps_status: str
    firmware_version: str | None
    last_seen_at: datetime | None
    last_latitude: float | None
    last_longitude: float | None
    last_location_at: datetime | None
    is_active: bool
    registered_by: UUID | None
    created_at: datetime
    updated_at: datetime


class DevicePage(BaseModel):
    items: list[DevicePublic]
    total: int
    limit: int
    offset: int


class DeviceWriteResult(BaseModel):
    device: DevicePublic
    device_secret: str | None = None