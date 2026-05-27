import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.config import settings
from app.database import get_session
from app.security.cookies import get_session_token, session_cookie_name
from app.security.csrf import (
    SAFE_METHODS,
    generate_csrf_token,
    set_csrf_cookie,
    validate_csrf,
)
from app.security.tokens import hash_token
from app.services import auth_service
from app.services.rate_limit_service import auth_check as rl_check
from app.services.rate_limit_service import auth_record as rl_record

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Request schemas ---

class RegisterRequest(BaseModel):
    email: str
    password: str
    password_confirm: str
    first_name: str
    last_name: str
    locale: str = "en-US"


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str
    password_confirm: str


# --- Helpers ---

def _get_source_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _csrf_required(request: Request) -> None:
    """Raises 403 if CSRF validation fails on state-changing methods."""
    if request.method in SAFE_METHODS:
        return
    if not validate_csrf(request):
        raise AppError(403, "CSRF_MISMATCH", "errors.csrf_mismatch", "CSRF validation failed.")


def _enforce_rate_limit(key: str, limit_name: str) -> None:
    """Raise 429 if rate limit exceeded, otherwise record the request."""
    if not rl_check(key, limit_name):
        raise AppError(429, "RATE_LIMIT_EXCEEDED", "errors.rate_limit_exceeded", "Too many requests. Try again later.")
    rl_record(key, limit_name)


# --- Endpoints ---

from fastapi.responses import JSONResponse


@router.post("/register")
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    _enforce_rate_limit(f"ip:{_get_source_ip(request)}", "register")
    msg_key, msg = await auth_service.register_user(
        db,
        email=body.email,
        password=body.password,
        password_confirm=body.password_confirm,
        first_name=body.first_name,
        last_name=body.last_name,
        locale=body.locale,
        source_ip=_get_source_ip(request),
    )
    status = 201 if msg_key == "auth.registration_success" else 200
    return JSONResponse(status_code=status, content={"message_key": msg_key, "message": msg})


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    _enforce_rate_limit(f"ip:{_get_source_ip(request)}", "login")
    result = await auth_service.login(
        db,
        email=body.email,
        password=body.password,
        source_ip=_get_source_ip(request),
        user_agent=_get_user_agent(request),
    )
    if not result["success"]:
        if result.get("message_key") == "errors.rate_limited":
            retry_after = str(settings.BRUTEFORCE_IP_WINDOW_SECONDS)
            raise AppError(429, "RATE_LIMIT_EXCEEDED", "errors.rate_limited", result["message"],
                           headers={"Retry-After": retry_after})
        raise AppError(401, "INVALID_CREDENTIALS", result["message_key"], result["message"])

    # Set session cookie
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key=session_cookie_name(is_secure),
        value=result["session_token"],
        httponly=True,
        samesite="lax",
        secure=is_secure,
        path="/",
        max_age=86400,
    )

    # Set CSRF cookie
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token, secure=is_secure)

    return {"user": result["user"]}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    _csrf_required(request)

    is_secure = request.url.scheme == "https"
    session_token = get_session_token(request)
    if session_token:
        token_hash = hash_token(session_token)
        await auth_service.logout(db, session_token_hash=token_hash)

    response.delete_cookie(session_cookie_name(is_secure), path="/")
    return {"message_key": "auth.logout_success", "message": "Logged out."}


@router.post("/verify-email")
async def verify_email_endpoint(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_session),
):
    success, msg_key, msg = await auth_service.verify_email(db, token=body.token)
    if not success:
        raise AppError(410, "TOKEN_EXPIRED" if "expired" in msg_key else "TOKEN_USED", msg_key, msg)
    return {"message_key": msg_key, "message": msg}


@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    _csrf_required(request)

    user_id = getattr(request.state, "user_id", None)
    if user_id:
        _enforce_rate_limit(f"user:{user_id}", "resend")
    if user_id is None:
        raise AppError(401, "SESSION_EXPIRED", "errors.session_expired", "Session required.")

    msg_key, msg = await auth_service.resend_verification(
        db, user_id=user_id, source_ip=_get_source_ip(request),
    )
    return {"message_key": msg_key, "message": msg}


@router.post("/request-password-reset")
async def request_password_reset(
    body: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    _enforce_rate_limit(f"email:{body.email.strip().lower()}", "reset")
    msg_key, msg = await auth_service.request_password_reset(
        db, email=body.email, source_ip=_get_source_ip(request),
    )
    return {"message_key": msg_key, "message": msg}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    success, msg_key, msg = await auth_service.reset_password(
        db,
        token=body.token,
        password=body.password,
        password_confirm=body.password_confirm,
        source_ip=_get_source_ip(request),
    )
    if not success:
        raise AppError(410 if "expired" in msg_key or "used" in msg_key else 422, "INVALID_REQUEST", msg_key, msg)
    return {"message_key": msg_key, "message": msg}


@router.get("/me")
async def me(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Return the current authenticated user."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise AppError(401, "SESSION_EXPIRED", "errors.session_expired", "Session required.")

    from sqlalchemy import select

    from app.models import User, UserPreference

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(404, "NOT_FOUND", "errors.not_found", "User not found.")

    # Load locale from preferences
    locale_result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.key == "locale",
        )
    )
    locale_pref = locale_result.scalar_one_or_none()
    user_locale = locale_pref.value if locale_pref else "en-US"

    return {
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
        }
    }


@router.get("/csrf")
async def get_csrf(
    request: Request,
    response: Response,
):
    """Set or refresh the CSRF cookie. Called by frontend after CSRF mismatch or first visit."""
    csrf_token = generate_csrf_token()
    is_secure = request.url.scheme == "https"
    set_csrf_cookie(response, csrf_token, secure=is_secure)
    return {"message_key": "auth.csrf_ready", "message": "CSRF token set."}
