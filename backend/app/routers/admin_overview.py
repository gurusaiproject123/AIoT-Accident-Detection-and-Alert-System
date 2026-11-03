from fastapi import APIRouter, Depends, HTTPException, Response
from httpx import HTTPError
from postgrest.exceptions import APIError

from app.core.database import get_supabase_admin
from app.core.permissions import require_superuser
from app.schemas.auth import CurrentUser


router = APIRouter(
    prefix="/api/admin/overview",
    tags=["Admin - Overview"],
    dependencies=[Depends(require_superuser)],
)


@router.get("")
def get_overview(
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Return platform-wide summary counts to a superuser."""

    db = get_supabase_admin()

    try:
        result = db.rpc(
            "admin_get_overview",
            {
                "p_actor_id": str(user.id),
            },
        ).execute()

    except APIError as exc:
        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="System overview access is not permitted.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve the system overview.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve the system overview.",
        ) from None

    if not isinstance(result.data, dict):
        raise HTTPException(
            status_code=503,
            detail="The system overview returned an unexpected result.",
        )

    response.headers["Cache-Control"] = "no-store"

    return result.data