from pydantic import BaseModel, ConfigDict, EmailStr, Field


class HospitalCreate(BaseModel):
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