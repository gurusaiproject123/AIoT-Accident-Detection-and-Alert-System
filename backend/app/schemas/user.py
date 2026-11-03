from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class UserCreate(BaseModel):
    """Create a hospital-staff or car-owner account."""

    model_config = ConfigDict(
        extra="forbid",
    )

    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: SecretStr

    role: Literal["hospital_staff", "car_owner"] = "hospital_staff"

    hospital_id: UUID | None = None
    owner_id: UUID | None = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Enter the user's full name.")

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        if not 12 <= len(value.get_secret_value()) <= 128:
            raise ValueError(
                "Password must contain between 12 and 128 characters."
            )

        return value

    @model_validator(mode="after")
    def validate_assignment(self):
        if self.role == "hospital_staff":
            if self.hospital_id is None:
                raise ValueError("Hospital staff require a hospital_id.")

            if self.owner_id is not None:
                raise ValueError(
                    "Hospital staff cannot have an owner_id."
                )

        if self.role == "car_owner":
            if self.owner_id is None:
                raise ValueError("Car owners require an owner_id.")

            if self.hospital_id is not None:
                raise ValueError(
                    "Car owners cannot have a hospital_id."
                )

        return self


class UserStatusUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    status: Literal["active", "suspended"]


class UserAccessUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    status: Literal["active", "suspended"] | None = None
    hospital_id: UUID | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")

        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null.")

        return self