from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class HospitalCreate(BaseModel):
    """Validate details for registering a hospital."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )

    name: str = Field(min_length=2, max_length=200)
    city: str = Field(min_length=2, max_length=100)

    address: str | None = Field(default=None, max_length=500)

    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    is_active: bool = True
    notes: str | None = Field(default=None, max_length=2000)


class HospitalUpdate(BaseModel):
    """Validate a partial hospital update."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
    )
    city: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    address: str | None = Field(default=None, max_length=500)

    phone: str | None = Field(
        default=None,
        min_length=7,
        max_length=30,
    )
    email: EmailStr | None = None

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")

        required_fields = {
            "name",
            "city",
            "phone",
            "email",
            "latitude",
            "longitude",
            "is_active",
        }

        for field in self.model_fields_set & required_fields:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")

        return self