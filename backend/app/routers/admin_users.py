from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
)
from httpx import HTTPError
from postgrest.exceptions import APIError
from supabase_auth.errors import AuthApiError

from app.core.database import get_supabase_admin
from app.core.permissions import require_superuser
from app.schemas.auth import CurrentUser
from app.schemas.user import StaffUserCreate


router = APIRouter(
    prefix="/api/admin/users",
    tags=["Admin - Users"],
    dependencies=[Depends(require_superuser)],
)


@router.get("")
def list_users(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List system profiles. Only superusers may access this endpoint."""

    db = get_supabase_admin()

    try:
        result = (
            db.table("profiles")
            .select(
                "id,full_name,email,role,status,hospital_id",
                count="exact",
            )
            .order("full_name")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve users.",
        ) from None

    response.headers["Cache-Control"] = "no-store"

    return {
        "items": result.data,
        "total": result.count,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
def create_staff_user(
    payload: StaffUserCreate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Create a hospital-staff login with one hospital assignment."""

    db = get_supabase_admin()
    email = str(payload.email).lower()

    # Prepare the approved role and hospital for the Auth trigger.
    try:
        db.rpc(
            "admin_prepare_staff",
            {
                "p_actor_id": str(user.id),
                "p_email": email,
                "p_hospital_id": str(payload.hospital_id),
            },
        ).execute()

    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(
                status_code=404,
                detail="Hospital not found.",
            ) from None

        if exc.code == "23505":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The account already exists or account creation "
                    "is already pending for this email."
                ),
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Staff account creation is not permitted.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Unable to prepare the staff account.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Could not confirm account preparation.",
        ) from None

    # Create the login. The database trigger creates its profile.
    try:
        created = db.auth.admin.create_user(
            {
                "email": email,
                "password": payload.password.get_secret_value(),
                # Immediate confirmation for controlled development accounts.
                "email_confirm": True,
                "user_metadata": {
                    "full_name": payload.full_name,
                },
            }
        )

    except AuthApiError as exc:
        if getattr(exc, "code", None) in {
            "email_exists",
            "user_already_exists",
        }:
            raise HTTPException(
                status_code=409,
                detail="An Auth account already uses this email.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail=(
                "Auth account creation failed. Check Authentication "
                "users and Auth logs before retrying."
            ),
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm account creation. "
                "Check the user list before retrying."
            ),
        ) from None

    if created.user is None:
        raise HTTPException(
            status_code=503,
            detail="Account creation returned no user.",
        )

    # Retrieve the application profile without exposing credentials.
    try:
        profiles = (
            db.table("profiles")
            .select("id,full_name,email,role,status,hospital_id")
            .eq("id", str(created.user.id))
            .limit(1)
            .execute()
            .data
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail=(
                "The account was created, but its profile could not "
                "be retrieved. Check the user list."
            ),
        ) from None

    if not profiles:
        raise HTTPException(
            status_code=503,
            detail=(
                "The Auth account exists, but no system profile "
                "was found. Administrator review is required."
            ),
        )

    response.headers["Cache-Control"] = "no-store"

    return profiles[0]