"""Authentication and role checks for hospital alerts and WebSockets."""

from __future__ import annotations

from typing import Annotated, Callable, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import create_client

from app.core.config import get_settings


RoleType = Literal["hospital_staff", "superuser", "car_owner", "unassigned"]
AccountStatusType = Literal["active", "suspended"]


class AuthenticatedUser(BaseModel):
    id: UUID
    full_name: str
    email: str | None = None
    role: RoleType
    status: AccountStatusType
    hospital_id: UUID | None = None
    owner_id: UUID | None = None


_bearer_scheme = HTTPBearer(auto_error=False)

TokenVerifier = Callable[[str], AuthenticatedUser | None]
_custom_token_verifier: TokenVerifier | None = None


def set_token_verifier(verifier: TokenVerifier | None) -> None:
    """Register or clear an alternate verifier, such as one used in tests."""
    global _custom_token_verifier
    _custom_token_verifier = verifier


def _verify_via_supabase(token: str) -> AuthenticatedUser:
    """Verify the token and read the account's role and assignments."""
    settings = get_settings()
    key = settings.supabase_service_role_key.get_secret_value()

    if not settings.supabase_url or not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend authentication is not configured.",
        )

    try:
        client = create_client(settings.supabase_url, key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backend authentication is unavailable.",
        ) from None

    try:
        user_response = client.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify the bearer token.",
        ) from None

    auth_user = getattr(user_response, "user", None)
    if auth_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
        )

    try:
        user_id = UUID(str(auth_user.id))
        profile_response = (
            client.table("profiles")
            .select("id, full_name, email, role, status, hospital_id")
            .eq("id", str(user_id))
            .maybe_single()
            .execute()
        )
        profile = getattr(profile_response, "data", None)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No application profile exists for this account.",
            )

        owner_id = None
        if profile["role"] == "car_owner":
            owner_response = (
                client.table("vehicle_owners")
                .select("id")
                .eq("user_id", str(user_id))
                .maybe_single()
                .execute()
            )
            owner = getattr(owner_response, "data", None)
            if owner and owner.get("id"):
                owner_id = UUID(str(owner["id"]))

        return AuthenticatedUser(
            id=user_id,
            full_name=profile.get("full_name") or "",
            email=profile.get("email"),
            role=profile["role"],
            status=profile["status"],
            hospital_id=profile.get("hospital_id"),
            owner_id=owner_id,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not load the application profile.",
        ) from None


def verify_access_token(token: str | None) -> AuthenticatedUser:
    """Verify a token and reject inactive accounts."""
    cleaned = (token or "").strip()
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()

    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    if _custom_token_verifier is not None:
        user = _custom_token_verifier(cleaned)
    else:
        user = _verify_via_supabase(cleaned)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended.",
        )

    return user


async def get_current_user(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> AuthenticatedUser:
    """Return the verified user for an HTTP request."""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return verify_access_token(credentials.credentials)

    return verify_access_token(request.headers.get("Authorization"))


async def require_hospital_staff(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.role != "hospital_staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hospital staff access is required.",
        )

    if user.hospital_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hospital staff account has no assigned hospital.",
        )

    return user


async def require_superuser(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.role != "superuser" or user.hospital_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access is required.",
        )

    return user


async def require_hospital_staff_or_superuser(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.role == "superuser" and user.hospital_id is None:
        return user

    if user.role == "hospital_staff" and user.hospital_id is not None:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authorized hospital staff or superuser access is required.",
    )