from fastapi import APIRouter, Depends, Response

from app.core.security import get_current_user
from app.schemas.auth import CurrentUser


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/me", response_model=CurrentUser)
def read_current_user(
    response: Response,
    user: CurrentUser = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return user