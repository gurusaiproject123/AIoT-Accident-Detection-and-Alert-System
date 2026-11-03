from uuid import UUID

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
from app.schemas.user import StaffUserCreate, UserStatusUpdate


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
    """List application profiles. Superusers only."""

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

    # Prepare the role and hospital assignment.
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

    # Create the Auth login.
    # The existing database trigger creates the assigned profile.
    try:
        created = db.auth.admin.create_user(
            {
                "email": email,
                "password": payload.password.get_secret_value(),
                # For controlled development accounts only.
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

    # Retrieve the profile without exposing passwords or tokens.
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


@router.patch("/{user_id}/status")
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Suspend or reactivate an account using the audited function."""

    db = get_supabase_admin()

    try:
        result = db.rpc(
            "admin_set_user_status",
            {
                "p_actor_id": str(user.id),
                "p_user_id": str(user_id),
                "p_status": payload.status,
            },
        ).execute()

    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(
                status_code=404,
                detail="User not found.",
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Account status management is not permitted.",
            ) from None

        if exc.code == "23514":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The status change conflicts with a database rule. "
                    "At least one active superuser must remain."
                ),
            ) from None

        if exc.code in {"22023", "22P02", "23502"}:
            raise HTTPException(
                status_code=422,
                detail="A valid account status is required.",
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Account status could not be updated.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm the status change. "
                "Check the user list before retrying."
            ),
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="No account status result was returned.",
        )

    profile = result.data[0]

    response.headers["Cache-Control"] = "no-store"

    return {
        "id": profile["id"],
        "full_name": profile["full_name"],
        "email": profile["email"],
        "role": profile["role"],
        "status": profile["status"],
        "hospital_id": profile["hospital_id"],
    }