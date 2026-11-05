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


def require_hospital_staff(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Allow access only to verified hospital staff assigned to a hospital."""

    if user.role != "hospital_staff" or user.hospital_id is None:
        raise HTTPException(
            status_code=403,
            detail="Hospital-staff access is required.",
        )

    return user


def require_staff_or_superuser(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Allow access only to verified hospital staff or a superuser."""

    if user.role == "superuser":
        return user

    if user.role == "hospital_staff" and user.hospital_id is not None:
        return user

    raise HTTPException(
        status_code=403,
        detail="Hospital staff or superuser access is required.",
    )
