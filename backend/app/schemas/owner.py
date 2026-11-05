from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class OwnerCreate(BaseModel):
    """Register owner contact details without creating a login."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    full_name: str = Field(min_length=2, max_length=200)

    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
    )

    email: EmailStr | None = None


class OwnerUpdate(BaseModel):
    """Update only the supplied owner contact fields."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
    )

    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
    )

    email: EmailStr | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")

        if (
            "full_name" in self.model_fields_set
            and self.full_name is None
        ):
            raise ValueError("Owner name cannot be null.")

        return self