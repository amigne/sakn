import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.database import get_session
from app.models import User
from app.security.csrf import validate_csrf, SAFE_METHODS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None


def _csrf_required(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    if not validate_csrf(request):
        raise AppError(403, "CSRF_MISMATCH", "errors.csrf_mismatch", "CSRF validation failed.")


@router.put("/profile")
async def update_profile(
    body: ProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    _csrf_required(request)

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise AppError(401, "SESSION_EXPIRED", "errors.session_expired", "Session required.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(404, "NOT_FOUND", "errors.not_found", "User not found.")

    if body.first_name is not None:
        stripped = body.first_name.strip()
        if not stripped:
            raise AppError(422, "VALIDATION_ERROR", "errors.validation", "First name cannot be empty.")
        user.first_name = stripped
    if body.last_name is not None:
        stripped = body.last_name.strip()
        if not stripped:
            raise AppError(422, "VALIDATION_ERROR", "errors.validation", "Last name cannot be empty.")
        user.last_name = stripped

    await db.flush()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "email_verified": user.email_verified_at is not None,
            "created_at": user.created_at.isoformat(),
        }
    }
