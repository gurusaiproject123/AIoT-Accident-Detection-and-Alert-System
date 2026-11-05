"""Authentication and role-authorization dependencies for hospital alerts & WS.

This module implements the verified caller contract defined in the Backend
Development Guide (Section 3 & Section 7):
  {
    "id": "verified-user-uuid",
    "full_name": "Account name",
    "role": "hospital_staff" | "superuser" | "car_owner" | "unassigned",
    "status": "active" | "suspended",
    "hospital_id": "hospital-uuid" | null,
    "owner_id": "owner-uuid" | null
  }

In production, the token is verified through Supabase Auth (`get_user(jwt)`)
and the authoritative profile/assignment is fetched from `public.profiles`
(and `public.vehicle_owners` when applicable). During tests or before
`backend-auth-admin` is merged, callers can register a custom token verifier
or override `get_current_user` via FastAPI `dependency_overrides`.
"""

from __future__ import annotations

from typing import Annotated, Callable, Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings

RoleType = Literal["hospital_staff", "superuser", "car_owner", "unassigned"]
AccountStatusType = Literal["active", "suspended"]


class AuthenticatedUser(BaseModel):
    """Verified application user context derived from the bearer token."""

    id: UUID
    full_name: str
    email: str | None = None
    role: RoleType
    status: AccountStatusType = "active"
    hospital_id: UUID | None = None
    owner_id: UUID | None = None


_bearer_scheme = HTTPBearer(auto_error=False)

# Pluggable token verifier hook used by HTTP and WebSocket authentication.
TokenVerifier = Callable[[str], AuthenticatedUser | None]
_custom_token_verifier: TokenVerifier | None = None


def set_token_verifier(verifier: TokenVerifier | None) -> None:
    """Register or clear a custom token verifier (used by tests or auth integration)."""
    global _custom_token_verifier
    _custom_token_verifier = verifier


def _verify_via_supabase(token: str) -> AuthenticatedUser:
    """Verify a Supabase JWT and load the protected profile record."""
    settings = get_settings()
    if not settings.supabase_url or not (
        settings.supabase_service_role_key or settings.supabase_publishable_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token could not be verified.",
        )

    try:
        from supabase import create_client  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - when supabase pkg is not installed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase client is not available to verify token.",
        ) from exc

    key = settings.supabase_service_role_key or settings.supabase_publishable_key
    client = create_client(settings.supabase_url, key)
    try:
        user_resp = client.auth.get_user(token)
        auth_user = getattr(user_resp, "user", None)
        if auth_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token.",
            )
        user_id = UUID(str(auth_user.id))
        profile_resp = (
            client.table("profiles")
            .select("id, full_name, email, role, status, hospital_id")
            .eq("id", str(user_id))
            .maybe_single()
            .execute()
        )
        data = getattr(profile_resp, "data", None)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No application profile exists for this account.",
            )
        owner_id: UUID | None = None
        if data.get("role") == "car_owner":
            owner_resp = (
                client.table("vehicle_owners")
                .select("id")
                .eq("user_id", str(user_id))
                .maybe_single()
                .execute()
            )
            owner_data = getattr(owner_resp, "data", None)
            if owner_data and owner_data.get("id"):
                owner_id = UUID(str(owner_data["id"]))

        return AuthenticatedUser(
            id=user_id,
            full_name=data.get("full_name") or "",
            email=data.get("email"),
            role=data["role"],
            status=data.get("status", "active"),
            hospital_id=UUID(str(data["hospital_id"])) if data.get("hospital_id") else None,
            owner_id=owner_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token.",
        ) from exc


def verify_access_token(token: str | None) -> AuthenticatedUser:
    """Validate a raw bearer token and enforce active account rules."""
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    cleaned = token.strip()
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()

    user: AuthenticatedUser | None = None
    if _custom_token_verifier is not None:
        user = _custom_token_verifier(cleaned)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired bearer token.",
            )
    else:
        user = _verify_via_supabase(cleaned)

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended.",
        )
    return user


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthenticatedUser:
    """FastAPI dependency returning the verified caller."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        # Allow a raw Authorization header fallback if needed
        raw_auth = request.headers.get("Authorization")
        if not raw_auth:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token.",
            )
        return verify_access_token(raw_auth)
    return verify_access_token(credentials.credentials)


async def require_hospital_staff(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Ensure the caller is active hospital staff with a verified hospital assignment."""
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
    """Ensure the caller is an active superuser with no hospital assignment."""
    if user.role != "superuser" or user.hospital_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access is required.",
        )
    return user


async def require_hospital_staff_or_superuser(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """Ensure the caller is either assigned hospital staff or a superuser."""
    if user.role == "superuser" and user.hospital_id is None:
        return user
    if user.role == "hospital_staff" and user.hospital_id is not None:
        return user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authorized hospital staff or superuser access is required.",
    )
