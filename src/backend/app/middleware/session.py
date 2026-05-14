import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.base import new_uuid7

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    """Read session cookie and attach session_id to request state.

    For Slice 3: anonymous sessions only. Auth comes in Slice 4.
    """

    async def dispatch(self, request: Request, call_next):
        session_token = request.cookies.get("sakn_session")
        if session_token:
            request.state.session_id = session_token
        else:
            request.state.session_id = f"anon_{new_uuid7()}"

        request.state.user_id = None
        request.state.role = "visitor"

        response = await call_next(request)
        return response
