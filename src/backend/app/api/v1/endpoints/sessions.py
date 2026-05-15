import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services import session_service
from app.security.tokens import hash_token
from app.security.csrf import validate_csrf, SAFE_METHODS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _csrf_required(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    if not validate_csrf(request):
        from app.api.errors import AppError

        raise AppError(403, "CSRF_MISMATCH", "errors.csrf_mismatch", "CSRF validation failed.")


@router.get("")
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        from app.api.errors import AppError

        raise AppError(401, "SESSION_EXPIRED", "errors.session_expired", "Session required.")

    session_token = request.cookies.get("sakn_session")
    current_token_hash = hash_token(session_token) if session_token else None

    sessions = await session_service.list_for_user(db, user_id, current_token_hash)
    return {"sessions": sessions}


@router.delete("/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    _csrf_required(request)

    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        from app.api.errors import AppError

        raise AppError(401, "SESSION_EXPIRED", "errors.session_expired", "Session required.")

    token_hash = await session_service.revoke(db, session_id)
    if token_hash is None:
        from app.api.errors import AppError

        raise AppError(404, "NOT_FOUND", "errors.not_found", "Session not found.")

    # If revoking current session, clear cookie
    current_token = request.cookies.get("sakn_session")
    if current_token and hash_token(current_token) == token_hash:
        response.delete_cookie("sakn_session", path="/")

    return {"message_key": "sessions.revoked", "message": "Session revoked."}
