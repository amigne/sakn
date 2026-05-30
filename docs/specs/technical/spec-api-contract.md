# API Contract — SAKN MVP

> **Version:** 2.0 — Added MAC OUI, WHOIS, Secret Generator i18n keys and error codes
> **Status:** Draft
> **Date:** 2026-05-21

The definitive contract between frontend and backend. Both agents MUST implement this exactly. Load with any other spec document when working on features that cross the network boundary.

---

## 1. Common Conventions

### 1.1 Base URL

```
/api/v1
```

### 1.2 Content Type

All requests and responses use `Content-Type: application/json` unless otherwise noted.

### 1.3 Response Envelope

All responses follow one of two shapes:

**Success** (2xx):
```json
{
  "<entity>": { ... },
  "pagination": { ... }   // only for list endpoints
}
```

Top-level key depends on endpoint (e.g., `"user"`, `"session"`, `"tool"`). List endpoints return a plural key (e.g., `"users"`, `"sessions"`).

**Error** (4xx, 5xx):
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message_key": "errors.specific_key",
    "message": "Human-readable fallback (English).",
    "details": null
  }
}
```

`details` is an optional object for field-level validation errors (see Section 2).

### 1.4 Pagination

All list endpoints use **offset/limit** pagination:

**Request** (query params):
```
GET /api/v1/admin/users?offset=0&limit=20
```

**Response**:
```json
{
  "users": [ ... ],
  "pagination": {
    "offset": 0,
    "limit": 20,
    "total": 142
  }
}
```

Default limit: 20. Maximum limit: 100.

### 1.5 CSRF

- Cookie: `sakn_csrf` (NOT httpOnly, SameSite=Lax, Secure in prod).
- Header: `X-CSRF-Token` — frontend reads cookie value and sends it as header on every state-changing request (POST, PUT, DELETE, PATCH).
- Server validates header == cookie. Mismatch → 403.
- Frontend: on 403 with CSRF-related error, fetch a fresh CSRF cookie from `GET /api/v1/auth/csrf` and retry once.

---

## 2. Validation Errors

When a request fails field-level validation (422 Unprocessable Entity):

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

---

## 3. Authentication Endpoints

### 3.1 Register

```
POST /auth/register
```

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass1",
  "password_confirm": "SecurePass1",
  "first_name": "John",
  "last_name": "Doe",
  "locale": "fr-FR"
}
```

`locale` is optional, defaults to `en-US`. `first_name` and `last_name` are required.

**Response** (201):
```json
{
  "message_key": "auth.registration_success",
  "message": "Registration successful. Check your email to verify your account."
}
```

No user object returned (prevents enumeration). No session created until email verified.

**Enumeration protection**: duplicate email registration returns HTTP 200 with a generic success message (identical to a fresh registration). This prevents attackers from testing whether an email is already registered. Internally, error code `EMAIL_ALREADY_EXISTS` is logged but not exposed.

### 3.2 Login

```
POST /auth/login
```

**Request**:
```json
{
  "email": "user@example.com",
  "password": "SecurePass1"
}
```

**Response** (200):
```json
{
  "user": {
    "id": "0193c8d4-...",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "authenticated",
    "status": "active",
    "email_verified": true,
    "locale": "fr-FR",
    "created_at": "2026-05-14T10:00:00Z"
  }
}
```

Sets cookies: `sakn_session` (httpOnly), `sakn_csrf` (JS-readable).

**Rate limiting**: 10 per IP per 60s. Error response on failure always: `{"error": {"code": "INVALID_CREDENTIALS", "message_key": "errors.invalid_credentials", "message": "Invalid email or password."}}` — identical timing whether email exists or not.

### 3.3 Logout

```
POST /auth/logout
```

No request body. Requires session cookie + CSRF header.

**Response** (200):
```json
{
  "message_key": "auth.logout_success",
  "message": "Logged out."
}
```

Clears `sakn_session` cookie. `sakn_csrf` cookie persists for the next visitor session.

### 3.4 Verify Email

```
POST /auth/verify-email
```

**Request**:
```json
{
  "token": "abc123..."
}
```

**Response** (200):
```json
{
  "message_key": "auth.email_verified",
  "message": "Email verified. You can now log in."
}
```

### 3.5 Resend Verification

```
POST /auth/resend-verification
```

No request body. Requires session cookie.

**Response** (200):
```json
{
  "message_key": "auth.verification_resent",
  "message": "Verification email sent."
}
```

Rate limited: 5 per user per 86400s.

### 3.6 Request Password Reset

```
POST /auth/request-password-reset
```

**Request**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200): Always identical, whether email exists or not:
```json
{
  "message_key": "auth.reset_email_sent",
  "message": "If this email is registered, a reset link has been sent."
}
```

Rate limited: 3 per email per 86400s.

### 3.7 Reset Password

```
POST /auth/reset-password
```

**Request**:
```json
{
  "token": "abc123...",
  "password": "NewSecurePass1",
  "password_confirm": "NewSecurePass1"
}
```

**Response** (200):
```json
{
  "message_key": "auth.password_reset_success",
  "message": "Password reset. You can now log in."
}
```

### 3.8 Get CSRF Token

```
GET /auth/csrf
```

No auth required. Sets `sakn_csrf` cookie. Used by frontend after 403 CSRF mismatch or on first visit.

**Response** (200):
```json
{
  "message_key": "auth.csrf_ready",
  "message": "CSRF token set."
}
```

---

## 4. Preferences

### 4.1 Get Preferences

```
GET /preferences
```

Requires session (authenticated or visitor).

**Response** (200):
```json
{
  "preferences": {
    "language": "fr",
    "locale": "fr-FR",
    "theme": "system",
    "display_mode": "table"
  }
}
```

`display_mode` is per-tool; the response may be scoped to the current tool if `?tool=ping` is provided.

### 4.2 Update Preferences

```
PUT /preferences
```

**Request**:
```json
{
  "language": "fr",
  "locale": "fr-FR",
  "theme": "dark",
  "display_mode": "text",
  "tool": "ping"
}
```

All fields optional. `tool` scopes `display_mode` to a specific tool. Without `tool`, `display_mode` sets a global default.

**Response** (200): same shape as GET.

---

## 5. Sessions

### 5.1 List Sessions

```
GET /sessions
```

Requires authenticated session.

**Response** (200):
```json
{
  "sessions": [
    {
      "id": "0193c8d4-...",
      "ip_address": "203.0.113.1",
      "user_agent": "Mozilla/5.0 ...",
      "created_at": "2026-05-14T08:00:00Z",
      "last_activity_at": "2026-05-14T10:00:00Z",
      "current": true
    }
  ]
}
```

`current` is `true` for the session making the request.

### 5.2 Revoke Session

```
DELETE /sessions/{session_id}
```

No request body. Requires session cookie + CSRF header. Can only revoke own sessions (non-admin users).

**Response** (200):
```json
{
  "message_key": "sessions.revoked",
  "message": "Session revoked."
}
```

If revoking the current session, `sakn_session` cookie is cleared.

---

## 6. Tools

### 6.1 List Tools

```
GET /tools
```

**Response** (200):
```json
{
  "tools": [
    {
      "name": "ping",
      "display_name_key": "tools.ping.name",
      "description_key": "tools.ping.description",
      "category": "network",
      "version": "1.0.0",
      "parameters": [
        {
          "name": "target",
          "type": "string",
          "label_key": "tools.ping.param_target_label",
          "description_key": "tools.ping.param_target_desc",
          "required": true,
          "default": null,
          "constraints": {"max_length": 255}
        }
      ],
      "enabled": true,
      "backend": true
    }
  ]
}
```

Only returns tools with `enabled: true` (for non-admin users) and with the user's role permission allowing it.

`backend: true` means the tool executes via `POST /api/v1/tools/{tool_name}/execute`. `backend: false` means the tool is frontend-only (e.g., Secret Generator) and has no execution endpoint.

---

## 7. Administration

All admin endpoints require authenticated session with `role = administrator`.

### 7.1 List Users

```
GET /admin/users?offset=0&limit=20&status=active&search=example
```

Query params: `offset`, `limit`, `status` (filter), `search` (email substring).

**Response** (200):
```json
{
  "users": [
    {
      "id": "0193c8d4-...",
      "email": "user@example.com",
      "role": "authenticated",
      "status": "active",
      "email_verified": true,
      "failed_login_attempts": 0,
      "locked_until": null,
      "admin_notes": null,
      "created_at": "2026-05-14T10:00:00Z",
      "updated_at": "2026-05-14T10:00:00Z"
    }
  ],
  "pagination": { "offset": 0, "limit": 20, "total": 1 }
}
```

### 7.2 Get User

```
GET /admin/users/{user_id}
```

**Response** (200): single user object (same shape as list item), plus `sessions` array (active sessions).

### 7.3 Block / Unblock / Lock / Unlock User

```
PUT /admin/users/{user_id}/block
PUT /admin/users/{user_id}/unblock
PUT /admin/users/{user_id}/lock
PUT /admin/users/{user_id}/unlock
```

No request body.

**Response** (200):
```json
{
  "user": { ... },
  "message_key": "admin.user_blocked",
  "message": "User blocked."
}
```

### 7.4 Update Admin Notes

```
PUT /admin/users/{user_id}/notes
```

**Request**:
```json
{
  "notes": "Internal note text."
}
```

**Response** (200): updated user object.

### 7.5 Delete User

```
DELETE /admin/users/{user_id}
```

No request body.

**Response** (200):
```json
{
  "message_key": "admin.user_deleted",
  "message": "User deleted."
}
```

Last admin cannot be deleted (returns 422).

### 7.6 List / Update Tool Config

```
GET /admin/tools
PUT /admin/tools/{tool_name}
```

**GET Response**: `{"tools": [...]}` — list of all tools with their DB config (enabled status, etc.).

**PUT Request**:
```json
{
  "enabled": false
}
```

### 7.7 List / Update Role Permissions

```
GET /admin/role-permissions
PUT /admin/role-permissions
```

**GET Response**:
```json
{
  "permissions": [
    {"role": "authenticated", "tool_id": "0193...", "tool_name": "ping", "allowed": true}
  ]
}
```

**PUT Request**:
```json
{
  "permissions": [
    {"role": "authenticated", "tool_id": "0193...", "allowed": false}
  ]
}
```

### 7.8 Rate Limits

```
GET /admin/rate-limits
PUT /admin/rate-limits
```

**GET Response**:
```json
{
  "rate_limits": [
    {"role": "authenticated", "tool_id": null, "tool_name": null, "soft_limit": 1, "hard_limit": 500, "window_seconds": 60}
  ]
}
```

`tool_id: null` means global config.

**PUT Request**:
```json
{
  "rate_limits": [
    {"role": "authenticated", "tool_id": null, "soft_limit": 2, "hard_limit": 1000, "window_seconds": 60}
  ]
}
```

### 7.9 Logs

```
GET /admin/logs/tool-executions?offset=0&limit=20&tool=ping&user_id=...&from=...&to=...
GET /admin/logs/security-events?offset=0&limit=20&event_type=blocked_address&from=...&to=...
GET /admin/logs/audit?offset=0&limit=20&admin_id=...&action=...&from=...&to=...
```

**Response** (200): paginated array of the respective log type, with total count in pagination.

### 7.10 DNS Server Presets

```
GET    /admin/modules/{tool_name}/dns-servers
POST   /admin/modules/{tool_name}/dns-servers
PUT    /admin/modules/{tool_name}/dns-servers/{id}
DELETE /admin/modules/{tool_name}/dns-servers/{id}
PUT    /admin/modules/{tool_name}/dns-servers/reorder
```

**DNS server preset object**:
```json
{
  "id": "0193c8d4-...",
  "ip_address": "8.8.8.8",
  "description": "Google DNS",
  "sort_order": 0
}
```

**POST/PUT Request**: `{"ip_address": "8.8.8.8", "description": "Google DNS"}`
**Reorder Request**: `{"order": ["id1", "id3", "id2"]}` — sets sort_order by array position.

### 7.11 Global Settings

```
GET /admin/settings
PUT /admin/settings
```

**GET Response**:
```json
{
  "settings": {
    "log_retention_days": "90",
    "session_duration_hours": "24",
    "max_concurrent_sessions": "10"
  }
}
```

**PUT Request**: same shape. All values are strings (TEXT column).

---

## 8. Health

```
GET /health
```

No auth.

**Response** (200):
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

If a dependency is down: `"database": "unavailable"` — still returns 200 for the health endpoint (load balancer doesn't kill it), but the backend logs the failure.

---

## 9. Error Codes Reference

| Code | HTTP | message_key | Description |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | `errors.validation` | Request body or params invalid |
| `INVALID_CREDENTIALS` | 401 | `errors.invalid_credentials` | Login failed |
| `SESSION_EXPIRED` | 401 | `errors.session_expired` | Session cookie invalid or expired |
| `EMAIL_NOT_VERIFIED` | 403 | `errors.email_not_verified` | Action requires verified email |
| `TARGET_NOT_ALLOWED` | 422 | `errors.target_not_allowed` | IP blocked by security filter |
| `DNS_RESOLUTION_FAILED` | 422 | `errors.dns_resolution_failed` | Could not resolve hostname |
| `TOOL_DISABLED` | 403 | `errors.tool_disabled` | Tool is disabled by admin |
| `ROLE_NOT_ALLOWED` | 403 | `errors.role_not_allowed` | Role lacks permission for this tool |
| `RATE_LIMIT_EXCEEDED` | 429 | `errors.rate_limit_exceeded` | Soft or hard limit hit |
| `CSRF_MISMATCH` | 403 | `errors.csrf_mismatch` | CSRF token mismatch |
| `USER_BLOCKED` | 403 | `errors.user_blocked` | Account blocked by admin |
| `USER_LOCKED` | 423 | `errors.user_locked` | Account locked (temporary or admin) |
| `ACCOUNT_LOCKED` | 423 | `errors.account_locked` | Brute-force temporary lock |
| `TOKEN_EXPIRED` | 410 | `errors.token_expired` | Verification or reset token expired |
| `TOKEN_USED` | 410 | `errors.token_used` | Verification or reset token already used |
| `NOT_FOUND` | 404 | `errors.not_found` | Entity not found |
| `INTERNAL_ERROR` | 500 | `errors.internal_error` | Unexpected server error |
| `WHOIS_UNSUPPORTED_TLD` | 422 | `errors.whois_unsupported_tld` | TLD not supported by any known WHOIS/RDAP server |
| `WHOIS_CONNECTION_FAILED` | 502 | `errors.whois_connection_failed` | Could not connect to remote WHOIS/RDAP server |
| `MAC_OUI_PARSE_EMPTY` | 422 | `errors.mac_oui_parse_empty` | No valid MAC address or OUI found in the provided text |
| `EMAIL_ALREADY_EXISTS` | 409 | `errors.email_already_exists` | Registration duplicate (only used internally, same response as success) |

---

## 10. i18n message_key Catalog

The frontend MUST bundle translations for all these keys. The backend sends `message_key` values; the frontend translates via `t()`.

### 10.1 errors namespace

```
errors.target_not_allowed
errors.dns_resolution_failed
errors.invalid_credentials
errors.session_expired
errors.email_not_verified
errors.tool_disabled
errors.role_not_allowed
errors.rate_limit_exceeded
errors.csrf_mismatch
errors.user_blocked
errors.user_locked
errors.account_locked
errors.token_expired
errors.token_used
errors.not_found
errors.internal_error
errors.validation
errors.invalid_email
errors.password_too_short
errors.password_too_weak
errors.password_mismatch
errors.invalid_params
errors.ipv6_not_available
errors.whois_unsupported_tld
errors.whois_connection_failed
errors.mac_oui_parse_empty
```

### 10.2 auth namespace

```
auth.registration_success
auth.logout_success
auth.email_verified
auth.verification_resent
auth.reset_email_sent
auth.password_reset_success
auth.csrf_ready
```

### 10.3 tools namespace

```
tools.ping.name
tools.ping.description
tools.ping.param_target_label
tools.ping.param_target_desc
tools.ping.param_count_label
tools.ping.param_count_desc
tools.ping.param_timeout_label
tools.ping.param_timeout_desc
tools.ping.param_packet_size_label
tools.ping.param_packet_size_desc
tools.ping.param_df_bit_label
tools.ping.param_df_bit_desc
tools.ping.param_dscp_label
tools.ping.param_dscp_desc
tools.ping.param_max_duration_label
tools.ping.param_max_duration_desc

tools.traceroute.name
tools.traceroute.description
tools.traceroute.param_target_label
tools.traceroute.param_target_desc
tools.traceroute.param_protocol_label
tools.traceroute.param_protocol_desc
tools.traceroute.param_port_label
tools.traceroute.param_port_desc
tools.traceroute.param_probes_label
tools.traceroute.param_probes_desc
tools.traceroute.param_timeout_label
tools.traceroute.param_timeout_desc
tools.traceroute.param_max_distance_label
tools.traceroute.param_max_distance_desc
tools.traceroute.param_dns_resolution_label
tools.traceroute.param_dns_resolution_desc

tools.dns_lookup.name
tools.dns_lookup.description
tools.dns_lookup.param_target_label
tools.dns_lookup.param_target_desc
tools.dns_lookup.param_record_type_label
tools.dns_lookup.param_record_type_desc
tools.dns_lookup.param_resolver_label
tools.dns_lookup.param_resolver_desc
tools.dns_lookup.param_cname_label
tools.dns_lookup.param_cname_desc

tools.ssl_viewer.name
tools.ssl_viewer.description
tools.ssl_viewer.param_url_label
tools.ssl_viewer.param_url_desc

tools.mac_oui.name
tools.mac_oui.description
tools.mac_oui.param_text_label
tools.mac_oui.param_text_desc
tools.mac_oui.result_vendor
tools.mac_oui.result_address
tools.mac_oui.result_type
tools.mac_oui.result_first_seen
tools.mac_oui.result_last_seen
tools.mac_oui.history_title
tools.mac_oui.history_previous
tools.mac_oui.history_new
tools.mac_oui.history_type
tools.mac_oui.history_date
tools.mac_oui.no_results
tools.mac_oui.truncation_warning
tools.mac_oui.unknown_vendor
tools.mac_oui.parse_stats

tools.whois.name
tools.whois.description
tools.whois.param_target_label
tools.whois.param_target_desc
tools.whois.param_server_label
tools.whois.param_server_desc
tools.whois.result_domain
tools.whois.result_status
tools.whois.result_registrar
tools.whois.result_creation_date
tools.whois.result_expiration_date
tools.whois.result_updated_date
tools.whois.result_nameservers
tools.whois.result_registrant
tools.whois.result_admin_contact
tools.whois.result_tech_contact
tools.whois.result_raw_text
tools.whois.result_protocol
tools.whois.protocol_rdap
tools.whois.protocol_whois
tools.whois.not_found
tools.whois.redacted
tools.whois.unsupported_tld

tools.secret_generator.name
tools.secret_generator.description
tools.secret_generator.mode_password
tools.secret_generator.mode_token
tools.secret_generator.mode_hex
tools.secret_generator.param_length_label
tools.secret_generator.param_length_desc
tools.secret_generator.param_length_token_label
tools.secret_generator.param_length_token_desc
tools.secret_generator.param_length_hex_label
tools.secret_generator.param_length_hex_desc
tools.secret_generator.param_uppercase_label
tools.secret_generator.param_lowercase_label
tools.secret_generator.param_digits_label
tools.secret_generator.param_symbols_label
tools.secret_generator.strength_weak
tools.secret_generator.strength_fair
tools.secret_generator.strength_strong
tools.secret_generator.strength_very_strong
tools.secret_generator.entropy
tools.secret_generator.copy
tools.secret_generator.regenerate
tools.secret_generator.clipboard_unavailable
tools.secret_generator.js_disabled
tools.secret_generator.copied
tools.secret_generator.no_charset_selected
tools.secret_generator.auto_clear_notice

tools.tls_warning
tools.revocation_not_checked
```

### 10.4 notices namespace

```
notices.ipv6_not_available
notices.ipv4_fallback
```

### 10.5 admin namespace

```
admin.user_blocked
admin.user_unblocked
admin.user_locked
admin.user_unlocked
admin.user_deleted
admin.notes_updated
admin.tool_updated
admin.permissions_updated
admin.rate_limits_updated
admin.settings_updated
```

### 10.6 sessions namespace

```
sessions.revoked
sessions.limit_reached
```

### 10.7 common namespace

```
common.loading
common.error
common.save
common.cancel
common.close
common.yes
common.no
common.search
common.filter
common.next
common.previous
common.page_info
```
