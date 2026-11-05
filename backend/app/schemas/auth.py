from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    role: Literal["hospital_staff", "superuser", "car_owner"]
    status: Literal["active"]
    hospital_id: UUID | None
    owner_id: UUID | None
    