from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class VehicleCreate(BaseModel):
    """Register a car under an existing owner."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    registration: str = Field(min_length=2, max_length=30)
    owner_id: UUID

    make: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    model: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    colour: str | None = Field(
        default=None, min_length=1, max_length=50
    )

    @field_validator("registration")
    @classmethod
    def normalize_registration(cls, value: str) -> str:
        return value.upper()


class VehicleUpdate(BaseModel):
    """Edit only the vehicle fields supplied in the request."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    registration: str | None = Field(
        default=None, min_length=2, max_length=30
    )
    owner_id: UUID | None = None

    make: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    model: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    colour: str | None = Field(
        default=None, min_length=1, max_length=50
    )

    @field_validator("registration")
    @classmethod
    def normalize_registration(cls, value: str | None):
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")

        for field in ("registration", "owner_id"):
            if (
                field in self.model_fields_set
                and getattr(self, field) is None
            ):
                raise ValueError(f"{field} cannot be null.")

        return self