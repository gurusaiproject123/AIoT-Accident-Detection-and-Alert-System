import hashlib
import secrets
from dataclasses import dataclass, field
from uuid import UUID

from fastapi import Header, HTTPException
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin


@dataclass(frozen=True)
class AuthenticatedDevice:
    id: UUID
    credential_hash: str = field(repr=False)


def invalid_device_credentials() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Missing or invalid device credentials.",
    )


def require_device(
    device_id: UUID,
    device_secret: str | None = Header(
        default=None,
        alias="X-Device-Secret",
    ),
) -> AuthenticatedDevice:
    if not device_secret:
        raise invalid_device_credentials()

    candidate_hash = hashlib.sha256(
        device_secret.encode("utf-8")
    ).hexdigest()

    db = get_supabase_admin()

    try:
        devices = (
            db.table("devices")
            .select("id,secret_hash,is_active")
            .eq("id", str(device_id))
            .limit(1)
            .execute()
            .data
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Device authentication is unavailable.",
        ) from None

    if not devices:
        raise invalid_device_credentials()

    device = devices[0]
    stored_hash = device["secret_hash"]

    if not isinstance(stored_hash, str):
        raise invalid_device_credentials()

    if not secrets.compare_digest(
        candidate_hash.encode("ascii"),
        stored_hash.encode("utf-8"),
    ):
        raise invalid_device_credentials()

    if not device["is_active"]:
        raise HTTPException(
            status_code=403,
            detail="Device is inactive.",
        )

    return AuthenticatedDevice(
        id=UUID(device["id"]),
        credential_hash=candidate_hash,
    )

