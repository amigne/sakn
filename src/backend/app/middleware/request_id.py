"""Request ID middleware — propagates a unique ID per request for log correlation."""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logs.logger import request_id_var
from app.models.base import new_uuid7


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique request ID to each request for log correlation.

    Must be the outermost middleware so the ID is available to all
    downstream handlers, including session middleware and error handlers.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(new_uuid7()))
        request.state.request_id = request_id
        request_id_var.set(request_id)

        response: Response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        return response
