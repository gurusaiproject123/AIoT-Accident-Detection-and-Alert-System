from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


class StaffUserCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: SecretStr

    role: Literal["hospital_staff"] = "hospital_staff"
    hospital_id: UUID
    owner_id: None = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Enter the staff member's full name.")

        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if not 12 <= len(value.get_secret_value()) <= 128:
            raise ValueError(
                "Password must contain between 12 and 128 characters."
            )

        return value