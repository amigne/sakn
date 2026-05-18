import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User, UserPreference, EmailVerification, PasswordReset, SecurityEventLog, Session
from app.models.base import new_uuid7, utcnow
from app.security.password import hash_password, verify_password, validate_password_strength
from app.security.tokens import generate_token, hash_token, verify_token
from app.services.email_service import send_email
import app.services.session_service as session_service

logger = logging.getLogger(__name__)

VERIFICATION_TOKEN_TTL = timedelta(hours=24)
RESET_TOKEN_TTL = timedelta(hours=1)


def _now_naive() -> datetime:
    """Return timezone-naive UTC now, for comparison with DB-stored values (SQLite compat)."""
    return utcnow().replace(tzinfo=None)

# Brute force lockout tiers
BRUTE_FORCE_TIERS = [
    (5, timedelta(minutes=5)),
    (10, timedelta(minutes=15)),
    (15, timedelta(minutes=45)),
    (20, timedelta(minutes=90)),
]


def _brute_force_duration(failed_count: int) -> timedelta | None:
    for threshold, duration in BRUTE_FORCE_TIERS:
        if failed_count >= threshold:
            return duration
    return None


def _check_brute_force_lock(user: User) -> tuple[bool, str | None]:
    """Check if user is temporarily locked. Returns (is_locked, error_message_key)."""
    if user.status == "blocked":
        return True, "errors.user_blocked"
    if user.status == "locked":
        return True, "errors.user_locked"
    now = _now_naive()
    if user.locked_until and user.locked_until > now:
        return True, "errors.account_locked"
    return False, None


async def _log_security_event(
    db: AsyncSession,
    event_type: str,
    source_ip: str,
    user_id: str | None = None,
    details: dict | None = None,
) -> None:
    event = SecurityEventLog(
        id=new_uuid7(),
        event_type=event_type,
        source_ip=source_ip,
        user_id=user_id,
        details=json.dumps(details or {}),
    )
    db.add(event)
    await db.flush()


async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    password_confirm: str,
    first_name: str | None = None,
    last_name: str | None = None,
    locale: str = "en-US",
    source_ip: str,
) -> tuple[str, str]:
    """Register a new user. Returns (message_key, message). Enumeration-safe."""
    email = email.lower().strip()

    # Validate required names
    if not first_name or not first_name.strip():
        return "errors.validation", "First name is required."
    if not last_name or not last_name.strip():
        return "errors.validation", "Last name is required."

    if password != password_confirm:
        return "errors.password_mismatch", "Passwords do not match."

    valid, err_key = validate_password_strength(password)
    if not valid:
        return err_key, "Password is too weak."

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        # Enumeration-safe: return same success message
        await _log_security_event(db, "registration_duplicate", source_ip, details={"email": email})
        return "auth.registration_success", "Registration successful. Check your email to verify your account."

    # Create user
    user = User(
        id=new_uuid7(),
        email=email,
        password_hash=hash_password(password),
        role="authenticated",
        status="pending",
        first_name=first_name.strip() if first_name else None,
        last_name=last_name.strip() if last_name else None,
    )
    db.add(user)
    await db.flush()

    # Create verification token
    token = generate_token()
    verification = EmailVerification(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + VERIFICATION_TOKEN_TTL,
    )
    db.add(verification)
    await db.flush()

    await _log_security_event(db, "registration", source_ip, user_id=user.id)

    # Send verification email (non-blocking on failure)
    verification_url = f"{settings.CORS_ORIGINS.split(',')[0]}/verify-email?token={token}"
    await send_email(
        email,
        "Verify your SAKN account",
        _render_verification_email(verification_url),
    )

    return "auth.registration_success", "Registration successful. Check your email to verify your account."


async def verify_email(db: AsyncSession, *, token: str) -> tuple[bool, str, str]:
    """Verify an email address. Returns (success, message_key, message)."""
    token_hash = hash_token(token)

    result = await db.execute(
        select(EmailVerification).where(EmailVerification.token_hash == token_hash)
    )
    verification = result.scalar_one_or_none()

    if verification is None or verification.used:
        return False, "errors.token_used", "Invalid or expired verification token."

    if verification.expires_at < _now_naive():
        return False, "errors.token_expired", "Verification token has expired."

    # Mark verification as used
    verification.used = True

    # Mark user as verified
    result = await db.execute(select(User).where(User.id == verification.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return False, "errors.not_found", "User not found."

    user.status = "active"
    user.email_verified_at = utcnow()
    await db.flush()

    return True, "auth.email_verified", "Email verified. You can now log in."


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    source_ip: str,
    user_agent: str | None = None,
    locale: str = "en-US",
    csrf_token: str | None = None,
) -> dict:
    """
    Authenticate a user and create a session.
    Returns a result dict with either:
      {"success": False, "message_key": ..., "message": ...}
      {"success": True, "user": ..., "session_token": ..., "session": ...}
    """
    email = email.lower().strip()

    # Find user (constant-time-ish — don't early return vs nonexistent email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # Enumeration-safe: identical response
        await _log_security_event(db, "login_failed_no_user", source_ip, details={"email": email})
        # Commit before AppError rollback
        await db.commit()
        return {"success": False, "message_key": "errors.invalid_credentials", "message": "Invalid email or password."}

    # Check block/lock
    is_locked, lock_key = _check_brute_force_lock(user)
    if is_locked:
        await _log_security_event(db, "login_blocked", source_ip, user_id=user.id, details={"reason": lock_key})
        await db.commit()
        return {"success": False, "message_key": lock_key, "message": "Account is locked or blocked."}

    # Verify password
    if not verify_password(password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts += 1
        duration = _brute_force_duration(user.failed_login_attempts)
        if duration:
            user.locked_until = utcnow() + duration

        # Log BEFORE commit so the event survives the AppError rollback
        await _log_security_event(
            db, "login_failed", source_ip, user_id=user.id,
            details={"failed_attempts": user.failed_login_attempts},
        )
        # Persist immediately — don't let AppError roll back security state
        await db.commit()

        return {"success": False, "message_key": "errors.invalid_credentials", "message": "Invalid email or password."}

    # Success: reset failed counter
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()

    # Check email verification
    if settings.EMAIL_VERIFICATION_REQUIRED and user.email_verified_at is None:
        return {
            "success": False,
            "message_key": "errors.email_not_verified",
            "message": "Email not verified.",
        }

    # Create session
    session_token, session_obj = await session_service.create(
        db, user_id=user.id, ip_address=source_ip, user_agent=user_agent,
    )

    # Build user dict with actual locale from preferences
    user_locale = locale
    try:
        locale_row = await db.execute(
            select(UserPreference).where(
                UserPreference.user_id == user.id,
                UserPreference.key == "locale",
            )
        )
        locale_pref = locale_row.scalar_one_or_none()
        if locale_pref:
            user_locale = locale_pref.value
    except Exception:
        pass  # Fall back to parameter default

    await _log_security_event(db, "login_success", source_ip, user_id=user.id)

    return {
        "success": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "email_verified": user.email_verified_at is not None,
            "locale": user_locale,
            "created_at": user.created_at.isoformat(),
        },
        "session_token": session_token,
        "token_hash": hash_token(session_token),
        "session_id": session_obj.id,
    }


async def logout(db: AsyncSession, *, session_token_hash: str) -> None:
    """Delete a session identified by its token hash."""
    from app.redis.session_store import delete_session as redis_delete

    result = await db.execute(select(Session).where(Session.token_hash == session_token_hash))
    s = result.scalar_one_or_none()
    if s:
        await db.delete(s)
        await db.flush()
    await redis_delete(session_token_hash)


async def request_password_reset(
    db: AsyncSession,
    *,
    email: str,
    source_ip: str,
) -> tuple[str, str]:
    """Request a password reset. Always returns the same message (enumeration-safe)."""
    email = email.lower().strip()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        await _log_security_event(db, "password_reset_request_no_user", source_ip, details={"email": email})
        return "auth.reset_email_sent", "If this email is registered, a reset link has been sent."

    # Create reset token
    token = generate_token()
    reset = PasswordReset(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + RESET_TOKEN_TTL,
    )
    db.add(reset)
    await db.flush()

    await _log_security_event(db, "password_reset_request", source_ip, user_id=user.id)

    reset_url = f"{settings.CORS_ORIGINS.split(',')[0]}/reset-password?token={token}"
    await send_email(
        email,
        "Reset your SAKN password",
        _render_reset_email(reset_url),
    )

    return "auth.reset_email_sent", "If this email is registered, a reset link has been sent."


async def reset_password(
    db: AsyncSession,
    *,
    token: str,
    password: str,
    password_confirm: str,
    source_ip: str,
) -> tuple[bool, str, str]:
    """Reset a password using a reset token. Returns (success, message_key, message)."""
    if password != password_confirm:
        return False, "errors.password_mismatch", "Passwords do not match."

    valid, err_key = validate_password_strength(password)
    if not valid:
        return False, err_key, "Password is too weak."

    token_hash = hash_token(token)
    result = await db.execute(
        select(PasswordReset).where(PasswordReset.token_hash == token_hash)
    )
    reset = result.scalar_one_or_none()

    if reset is None or reset.used:
        return False, "errors.token_used", "Invalid or expired reset token."

    if reset.expires_at < _now_naive():
        return False, "errors.token_expired", "Reset token has expired."

    # Mark token as used
    reset.used = True

    # Update password
    result = await db.execute(select(User).where(User.id == reset.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return False, "errors.not_found", "User not found."

    user.password_hash = hash_password(password)
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.flush()

    # Terminate all other sessions
    await session_service.revoke_all_for_user(db, user.id)

    await _log_security_event(db, "password_reset", source_ip, user_id=user.id)

    return True, "auth.password_reset_success", "Password reset. You can now log in."


async def resend_verification(
    db: AsyncSession,
    *,
    user_id: str,
    source_ip: str,
) -> tuple[str, str]:
    """Resend verification email. Returns (message_key, message)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.email_verified_at is not None:
        # Already verified or user doesn't exist — don't reveal
        return "auth.verification_resent", "Verification email sent."

    # Create new verification token
    token = generate_token()
    verification = EmailVerification(
        id=new_uuid7(),
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=utcnow() + VERIFICATION_TOKEN_TTL,
    )
    db.add(verification)
    await db.flush()

    verification_url = f"{settings.CORS_ORIGINS.split(',')[0]}/verify-email?token={token}"
    await send_email(
        user.email,
        "Verify your SAKN account",
        _render_verification_email(verification_url),
    )

    await _log_security_event(db, "verification_resent", source_ip, user_id=user.id)

    return "auth.verification_resent", "Verification email sent."


def _render_verification_email(verification_url: str) -> str:
    return f"""<html>
<body style="font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
  <h1 style="color: #1a1a2e;">Verify your SAKN account</h1>
  <p>Click the link below to verify your email address:</p>
  <p><a href="{verification_url}" style="display: inline-block; padding: 10px 20px; background: #2563eb; color: white; text-decoration: none; border-radius: 6px;">Verify Email</a></p>
  <p style="color: #6b7280; font-size: 0.875rem;">This link expires in 24 hours.</p>
  <p style="color: #6b7280; font-size: 0.875rem;">If you did not create this account, you can ignore this email.</p>
</body>
</html>"""


def _render_reset_email(reset_url: str) -> str:
    return f"""<html>
<body style="font-family: system-ui, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
  <h1 style="color: #1a1a2e;">Reset your SAKN password</h1>
  <p>Click the link below to reset your password:</p>
  <p><a href="{reset_url}" style="display: inline-block; padding: 10px 20px; background: #2563eb; color: white; text-decoration: none; border-radius: 6px;">Reset Password</a></p>
  <p style="color: #6b7280; font-size: 0.875rem;">This link expires in 1 hour.</p>
  <p style="color: #6b7280; font-size: 0.875rem;">If you did not request this, you can ignore this email.</p>
</body>
</html>"""