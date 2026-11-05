from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from httpx import HTTPError
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.core.database import get_supabase_admin
from app.core.security import get_current_user
from app.schemas.auth import CurrentUser


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class AssignedHospital(BaseModel):
    id: UUID
    code: str
    name: str


@router.get("/me", response_model=CurrentUser)
def read_current_user(
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.get("/me/hospital", response_model=AssignedHospital)
def read_assigned_hospital(
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    if user.role != "hospital_staff" or user.hospital_id is None:
        raise HTTPException(
            status_code=403,
            detail="Hospital staff access is required.",
        )

    try:
        result = (
            get_supabase_admin()
            .table("hospitals")
            .select("id,code,name")
            .eq("id", str(user.hospital_id))
            .limit(1)
            .execute()
        )
    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Could not load the assigned hospital.",
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="The assigned hospital was not found.",
        )

    response.headers["Cache-Control"] = "no-store"
    return result.data[0]