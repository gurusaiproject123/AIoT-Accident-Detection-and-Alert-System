from fastapi import Depends, HTTPException

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser


def require_superuser(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Allow access only to a verified superuser."""

    if user.role != "superuser":
        raise HTTPException(
            status_code=403,
            detail="Superuser access is required.",
        )

    return user


def require_car_owner(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Allow access only to a verified, linked car-owner account."""

    if user.role != "car_owner" or user.owner_id is None:
        raise HTTPException(
            status_code=403,
            detail="Car-owner access is required.",
        )

    return user