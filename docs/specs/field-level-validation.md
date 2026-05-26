# Field-Level Validation Errors

> **Version:** 1.0 — New document
> **Status:** Draft
> **Date:** 2026-05-26
> **Issue:** #2

## 1. Motivation

Currently, Pydantic `ValidationError` on POST/PUT endpoints is handled by FastAPI's default exception handler, which returns a flat list of errors. The frontend cannot map errors to specific form fields.

The API contract (`spec-api-contract.md` §2) already defines the `details.fields` format but it is not implemented.

## 2. Response Format

### 2.1 Error with field-level details

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message_key": "errors.validation",
    "message": "Validation failed.",
    "details": {
      "fields": {
        "email": {"message_key": "errors.invalid_email", "message": "Invalid email address."},
        "password": {"message_key": "errors.password_too_short", "message": "Min 8 characters."}
      }
    }
  }
}
```

### 2.2 Field error object

Each field key maps to an object with:
- `message_key` (string): i18n key resolvable by the frontend
- `message` (string): English fallback message

### 2.3 Field error message keys

Mapping from Pydantic error types to i18n keys:

| Pydantic error | message_key | message fallback |
|---|---|---|
| `missing` | `errors.field_required` | "This field is required." |
| `string_type`, `int_type`, etc. | `errors.invalid_type` | "Invalid type." |
| `value_error.email` | `errors.invalid_email` | "Invalid email address." |
| `string_too_short` (min_length) | `errors.too_short` | "Too short." |
| `string_too_long` (max_length) | `errors.too_long` | "Too long." |
| `value_error` (generic) | `errors.invalid_value` | "Invalid value." |
| `extra` (forbidden field) | `errors.forbidden_field` | "Unknown field." |

If a field has multiple errors, only the **first** error per field is returned (the most relevant one that Pydantic reports).

## 3. Backward Compatibility

- `details` was previously always `null` in `AppError` responses. Adding `details.fields` on validation errors does not break existing clients.
- The existing `AppError` handler is preserved. A new handler for FastAPI's `RequestValidationError` is added alongside it.
- Endpoints that already use `AppError` with custom `details` (none currently) are unaffected.
- The `message_key` at the error level remains `errors.validation` — existing clients that display only the top-level message continue to work unchanged.

## 4. Scope — Endpoints

### Initial scope (this PR)

| Endpoint | Method | Body model |
|---|---|---|
| `/api/v1/auth/register` | POST | `RegisterRequest` |
| `/api/v1/auth/reset-password` | POST | `ResetPasswordRequest` |
| `/api/v1/auth/login` | POST | `LoginRequest` |

Rationale: These are the highest-impact endpoints for end users. Adding field-level errors to login and register forms immediately improves UX.

### Follow-up scope (separate PR/issue)

All other POST/PUT endpoints with Pydantic body models:
- `/api/v1/account/profile` (PUT `ProfileUpdate`)
- `/api/v1/account` (DELETE `DeleteAccountRequest`)
- `/api/v1/auth/verify-email` (POST `VerifyEmailRequest`)
- `/api/v1/auth/request-password-reset` (POST `PasswordResetRequest`)
- `/api/v1/tools/{name}/execute` (POST — raw dict, no Pydantic model)

## 5. Implementation Plan

### 5.1 Backend

1. Add `pydantic_validation_handler` in `app/api/errors.py` that:
   - Catches `fastapi.exceptions.RequestValidationError`
   - Extracts field-level errors from `exc.errors()` (Pydantic error list)
   - Maps Pydantic error types to message keys (see table above)
   - Builds `details.fields` object
   - Returns `AppError`-compatible JSON response (422)

2. Register the new handler in `register_error_handlers()`.

3. Add unit tests in `tests/integration/test_auth_api.py`:
   - POST `/api/v1/auth/register` with invalid email → `details.fields.email` present
   - POST `/api/v1/auth/register` with empty body → `details.fields` has all required fields
   - POST `/api/v1/auth/reset-password` with missing fields → `details.fields` present
   - Existing endpoints still return correct error format (no regression)

### 5.2 Frontend

1. Extend `ApiError` class to expose `fields: Record<string, {message_key: string, message: string}> | null`

2. Update `LoginForm` to display per-field errors via `TextInput error={...}` instead of (or in addition to) the top-level `Alert`

3. Update `RegisterForm` similarly.

4. Add E2E test: submit login with invalid email format → error message visible under email field.

## 6. Acceptance Criteria

- [ ] POST `/api/v1/auth/register` with `email: "notanemail"` returns 422 with `details.fields.email.message_key = "errors.invalid_email"`
- [ ] POST `/api/v1/auth/register` with empty body returns 422 with `details.fields.email`, `.password`, `.password_confirm`, `.first_name`, `.last_name`
- [ ] POST `/api/v1/auth/login` with missing fields returns 422 with `details.fields`
- [ ] Existing 422 responses from non-body endpoints are unaffected
- [ ] LoginForm shows per-field error under email/password inputs when API returns field errors
- [ ] Backward compatible: clients ignoring `details.fields` see no behavior change
