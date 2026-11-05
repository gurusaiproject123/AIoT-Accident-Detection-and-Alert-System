from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from httpx import HTTPError
from postgrest.exceptions import APIError
from supabase_auth.errors import AuthApiError

from app.core.database import get_supabase_admin
from app.schemas.auth import CurrentUser


bearer = HTTPBearer(auto_error=False)


def unauthorized():
    return HTTPException(
        status_code=401,
        detail="Missing, invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if credentials is None:
        raise unauthorized()

    db = get_supabase_admin()

    # Verify identity. Never trust a user ID or role sent by React.
    try:
        result = db.auth.get_user(credentials.credentials)
    except AuthApiError as exc:
        if str(exc.status) in {"400", "401", "403", "422"}:
            raise unauthorized() from None

        raise HTTPException(
            status_code=503,
            detail="Authentication service is unavailable.",
        ) from None
    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Authentication service is unavailable.",
        ) from None

    if result.user is None:
        raise unauthorized()

    user_id = str(result.user.id)

    # Read assignments from protected database records.
    try:
        profiles = (
            db.table("profiles")
            .select("id,full_name,email,role,status,hospital_id")
            .eq("id", user_id)
            .limit(1)
            .execute()
            .data
        )

        if not profiles:
            raise HTTPException(
                status_code=403,
                detail="Your account has no system profile.",
            )

        profile = profiles[0]

        if profile["status"] != "active":
            raise HTTPException(
                status_code=403,
                detail="Your account is not active.",
            )

        owners = (
            db.table("vehicle_owners")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
            .data
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to load account permissions.",
        ) from None

    role = profile["role"]
    hospital_id = profile["hospital_id"]
    owner_id = owners[0]["id"] if owners else None

    # Enforce the relationships agreed for this system.
    valid_assignment = (
        (
            role == "hospital_staff"
            and hospital_id is not None
            and owner_id is None
        )
        or (
            role == "superuser"
            and hospital_id is None
            and owner_id is None
        )
        or (
            role == "car_owner"
            and hospital_id is None
            and owner_id is not None
        )
    )

    if not valid_assignment:
        raise HTTPException(
            status_code=403,
            detail="Account assignments need administrator review.",
        )

    return CurrentUser(
        id=user_id,
        full_name=profile["full_name"],
        email=profile["email"],
        role=role,
        status="active",
        hospital_id=hospital_id,
        owner_id=owner_id,
    )