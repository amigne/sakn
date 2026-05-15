import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.services.preference_service import get_preferences, set_preferences
from app.security.csrf import validate_csrf, SAFE_METHODS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesUpdate(BaseModel):
    language: str | None = None
    locale: str | None = None
    theme: str | None = None
    display_mode: str | None = None
    tool: str | None = None


def _csrf_required(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    if not validate_csrf(request):
        from app.api.errors import AppError

        raise AppError(403, "CSRF_MISMATCH", "errors.csrf_mismatch", "CSRF validation failed.")


@router.get("")
async def get_prefs(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    user_id = getattr(request.state, "user_id", None)
    session_id = getattr(request.state, "session_id", None)
    tool = request.query_params.get("tool")

    prefs = await get_preferences(db, user_id=user_id, session_id=session_id)

    if tool and "display_mode" in prefs:
        # For per-tool display mode, we could scope it. For now return as-is.
        pass

    return {"preferences": prefs}


@router.put("")
async def put_prefs(
    body: PreferencesUpdate,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    _csrf_required(request)

    user_id = getattr(request.state, "user_id", None)
    session_id = getattr(request.state, "session_id", None)

    updates = {}
    if body.language is not None:
        updates["language"] = body.language
    if body.locale is not None:
        updates["locale"] = body.locale
    if body.theme is not None:
        updates["theme"] = body.theme
    if body.display_mode is not None:
        updates["display_mode"] = body.display_mode

    prefs = await set_preferences(db, user_id=user_id, session_id=session_id, updates=updates)
    return {"preferences": prefs}
