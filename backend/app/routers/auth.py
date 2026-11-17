from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Header
from httpx import HTTPError
from postgrest.exceptions import APIError
from pydantic import BaseModel, EmailStr, SecretStr, Field
from app.core.config import get_settings

from app.core.database import get_supabase_admin
from app.core.security import get_current_user
from app.schemas.auth import CurrentUser


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class LocalLogin(BaseModel):
    email: EmailStr
    password: SecretStr = Field(max_length=128)


def local_only():
    if get_settings().database_backend != "mysql":
        raise HTTPException(404, "Local authentication is not enabled.")


@router.get("/config")
def auth_configuration(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"provider": "local" if get_settings().database_backend == "mysql" else "supabase"}


@router.post("/login")
def local_login(payload: LocalLogin, response: Response):
    local_only()
    from app.localdb.auth import sign_in
    response.headers["Cache-Control"] = "no-store"
    return {"session": sign_in(str(payload.email), payload.password.get_secret_value())}


@router.post("/logout")
def local_logout(authorization: str = Header(default="")):
    local_only()
    from app.localdb.auth import logout
    logout(authorization.removeprefix("Bearer "))
    return {"signed_out": True}


class PasswordChange(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=12, max_length=128)


@router.post("/password")
def local_password_change(payload: PasswordChange, authorization: str = Header(default="")):
    local_only()
    from app.localdb.auth import change_password
    change_password(authorization.removeprefix("Bearer "),payload.current_password.get_secret_value(),payload.new_password.get_secret_value())
    return {"changed": True}


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
