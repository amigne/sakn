import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.database import get_session
from app.models import Session, User
from app.models.log import AuditLog, SecurityEventLog, ToolExecutionLog
from app.models.preferences import EmailVerification, PasswordReset, UserPreference
from app.security.csrf import SAFE_METHODS, validate_csrf
from app.security.password import verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None


class DeleteAccountRequest(BaseModel):
    password: str


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


@router.delete("")
async def delete_account(
    body: DeleteAccountRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Delete the authenticated user's account. Requires password confirmation.

    - Verifies the provided password
    - Deletes preferences, verification tokens, password resets, sessions
    - Anonymizes log references (user_id set to NULL)
    - Deletes the user record
    """
    _csrf_required(request)

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise AppError(401, "SESSION_EXPIRED", "errors.session_expired", "Session required.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(404, "NOT_FOUND", "errors.not_found", "User not found.")

    # Verify password
    if not verify_password(body.password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "errors.invalid_credentials", "Invalid password.")

    # Delete related data
    related_tables = [UserPreference, EmailVerification, PasswordReset, Session]
    for model in related_tables:
        await db.execute(
            delete(model).where(model.user_id == user_id)  # type: ignore[arg-type]
        )

    # Anonymize logs (set user_id to NULL, keep the log entries)
    log_models = [ToolExecutionLog, SecurityEventLog, AuditLog]
    for model in log_models:
        await db.execute(
            update(model).where(model.user_id == user_id).values(user_id=None)  # type: ignore[arg-type]
        )

    # Delete the user
    await db.delete(user)
    await db.commit()

    logger.info("Account deleted", extra={"user_id": user_id})
    return {"message": "Account deleted.", "message_key": "auth.account_deleted"}
