from fastapi import Depends, HTTPException

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser


def require_superuser(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if user.role != "superuser":
        raise HTTPException(
            status_code=403,
            detail="Superuser access is required.",
        )

    return user