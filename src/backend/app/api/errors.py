from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message_key: str, message: str, details: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message_key = message_key
        self.message = message
        self.details = details


class ValidationError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(422, "VALIDATION_ERROR", "errors.validation", message, details)


class TargetNotAllowedError(AppError):
    def __init__(self):
        super().__init__(422, "TARGET_NOT_ALLOWED", "errors.target_not_allowed", "Target not allowed")


class DnsResolutionError(AppError):
    def __init__(self):
        super().__init__(422, "DNS_RESOLUTION_FAILED", "errors.dns_resolution_failed", "DNS resolution failed")


class RateLimitExceededError(AppError):
    def __init__(self):
        super().__init__(429, "RATE_LIMIT_EXCEEDED", "errors.rate_limit_exceeded", "Too many requests")


class InternalError(AppError):
    def __init__(self):
        super().__init__(500, "INTERNAL_ERROR", "errors.internal_error", "Unexpected server error")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message_key": exc.message_key,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


def register_error_handlers(app):
    app.add_exception_handler(AppError, app_error_handler)
