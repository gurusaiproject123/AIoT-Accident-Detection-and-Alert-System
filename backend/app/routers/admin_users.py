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
from app.schemas.user import (
    UserAccessUpdate,
    UserCreate,
    UserStatusUpdate,
)


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
def create_user(
    payload: UserCreate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Create a hospital-staff or registered car-owner login."""

    db = get_supabase_admin()
    email = str(payload.email).lower()

    if payload.role == "hospital_staff":
        preparation_function = "admin_prepare_staff"

        preparation_data = {
            "p_actor_id": str(user.id),
            "p_email": email,
            "p_hospital_id": str(payload.hospital_id),
        }

    else:
        preparation_function = "admin_prepare_owner"

        preparation_data = {
            "p_actor_id": str(user.id),
            "p_email": email,
            "p_owner_id": str(payload.owner_id),
        }

    # Prepare the approved role and assignment.
    try:
        db.rpc(
            preparation_function,
            preparation_data,
        ).execute()

    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(
                status_code=404,
                detail="The selected hospital or owner was not found.",
            ) from None

        if exc.code == "23505":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The account or owner login already exists, "
                    "or account creation is already pending."
                ),
            ) from None

        if exc.code == "42501":
            raise HTTPException(
                status_code=403,
                detail="Account creation is not permitted.",
            ) from None

        if exc.code in {
            "22023",
            "23514",
            "23503",
            "23502",
            "22P02",
        }:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid account assignment. "
                    "A car owner must have a registered car."
                ),
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Unable to prepare the account.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail="Could not confirm account preparation.",
        ) from None

    # Supabase Auth creates the login.
    # The existing database trigger creates the profile and owner link.
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
                "Check existing accounts before retrying."
            ),
        ) from None

    if created.user is None:
        raise HTTPException(
            status_code=503,
            detail="Account creation returned no user.",
        )

    # Retrieve the saved profile and actual owner assignment.
    try:
        profiles = (
            db.table("profiles")
            .select("id,full_name,email,role,status,hospital_id")
            .eq("id", str(created.user.id))
            .limit(1)
            .execute()
            .data
        )

        owners = (
            db.table("vehicle_owners")
            .select("id")
            .eq("user_id", str(created.user.id))
            .limit(1)
            .execute()
            .data
        )

    except (APIError, HTTPError):
        raise HTTPException(
            status_code=503,
            detail=(
                "The account was created, but its assignment could "
                "not be retrieved. Check existing accounts."
            ),
        ) from None

    if not profiles:
        raise HTTPException(
            status_code=503,
            detail=(
                "Account profile is missing. "
                "Administrator review is required."
            ),
        )

    profile = profiles[0]
    linked_owner_id = owners[0]["id"] if owners else None

    # Verify the assignments created by the database trigger.
    if payload.role == "hospital_staff":
        assignment_valid = (
            profile["role"] == "hospital_staff"
            and profile["hospital_id"] == str(payload.hospital_id)
            and linked_owner_id is None
        )

    else:
        assignment_valid = (
            profile["role"] == "car_owner"
            and profile["hospital_id"] is None
            and linked_owner_id == str(payload.owner_id)
        )

    if not assignment_valid:
        raise HTTPException(
            status_code=503,
            detail=(
                "Account assignment verification failed. "
                "Administrator review is required."
            ),
        )

    response.headers["Cache-Control"] = "no-store"

    return {
        **profile,
        "owner_id": linked_owner_id,
    }


@router.patch("/{user_id}/status")
def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Suspend or reactivate an account."""

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


@router.patch("/{user_id}")
def update_user_access(
    user_id: UUID,
    payload: UserAccessUpdate,
    response: Response,
    user: CurrentUser = Depends(require_superuser),
):
    """Update status or hospital assignment without changing role."""

    db = get_supabase_admin()

    changes = payload.model_dump(
        mode="json",
        exclude_unset=True,
    )

    try:
        result = db.rpc(
            "admin_update_user_access",
            {
                "p_actor_id": str(user.id),
                "p_user_id": str(user_id),
                "p_data": changes,
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
                detail="Account access management is not permitted.",
            ) from None

        if exc.code == "23514":
            raise HTTPException(
                status_code=409,
                detail=(
                    "The change conflicts with a database rule. "
                    "At least one active superuser must remain."
                ),
            ) from None

        if exc.code in {"22023", "22P02", "23502", "23503"}:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Invalid status or hospital assignment. "
                    "Staff require an existing hospital; "
                    "superusers and car owners cannot have one."
                ),
            ) from None

        raise HTTPException(
            status_code=503,
            detail="Account access could not be updated.",
        ) from None

    except HTTPError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not confirm the update. "
                "Check the user list before retrying."
            ),
        ) from None

    if not result.data:
        raise HTTPException(
            status_code=503,
            detail="No account update result was returned.",
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