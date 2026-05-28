import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Mapping from Pydantic error types to i18n message keys
_PYDANTIC_ERROR_MESSAGE_KEYS: dict[str, str] = {
    "missing": "errors.field_required",
    "string_type": "errors.invalid_type",
    "int_type": "errors.invalid_type",
    "float_type": "errors.invalid_type",
    "bool_type": "errors.invalid_type",
    "list_type": "errors.invalid_type",
    "dict_type": "errors.invalid_type",
    "string_too_short": "errors.too_short",
    "string_too_long": "errors.too_long",
    "value_error": "errors.invalid_value",
}

# Human-readable fallback messages for each Pydantic error type
_PYDANTIC_ERROR_MESSAGES: dict[str, str] = {
    "missing": "This field is required.",
    "string_type": "Invalid type.",
    "int_type": "Invalid type.",
    "float_type": "Invalid type.",
    "bool_type": "Invalid type.",
    "list_type": "Invalid type.",
    "dict_type": "Invalid type.",
    "string_too_short": "Too short.",
    "string_too_long": "Too long.",
    "value_error": "Invalid value.",
}


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message_key: str,
        message: str,
        details: dict | None = None,
        headers: dict | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message_key = message_key
        self.message = message
        self.details = details
        self.headers = headers


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


def _build_field_errors(errors: list[dict]) -> dict[str, dict[str, str]]:
    """Extract field-level errors from Pydantic error list.

    Returns a dict mapping field names to {message_key, message}.
    Only the first error per field is included.
    """
    fields: dict[str, dict[str, str]] = {}
    for err in errors:
        # loc is ("body", "field_name", ...) for body validation errors
        loc = err.get("loc", ())
        if len(loc) >= 2 and loc[0] == "body":
            field_name = str(loc[1]) if isinstance(loc[1], (str, int)) else "body"
        else:
            continue

        if field_name in fields:
            continue  # Only first error per field

        error_type = err.get("type", "value_error")
        ctx = err.get("ctx", {})
        # For int_type/float_type etc, the ctx may have the expected type
        if isinstance(ctx, dict) and "expected" in ctx:
            # Use generic type error for all type mismatches
            pass

        message_key = _PYDANTIC_ERROR_MESSAGE_KEYS.get(error_type, "errors.invalid_value")
        message = _PYDANTIC_ERROR_MESSAGES.get(error_type, err.get("msg", "Invalid value."))
        fields[field_name] = {"message_key": message_key, "message": message}

    return fields


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
        headers=exc.headers,
    )


async def pydantic_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = _build_field_errors(exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message_key": "errors.validation",
                "message": "Validation failed.",
                "details": {"fields": field_errors} if field_errors else None,
            }
        },
    )


def register_error_handlers(app):
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, pydantic_validation_handler)
