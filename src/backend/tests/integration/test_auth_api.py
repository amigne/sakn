"""Integration tests for auth endpoints: register → verify → login → preferences → sessions → logout."""
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailVerification, User
from app.models.base import utcnow
from app.models.log import SecurityEventLog
from app.security.tokens import generate_token, hash_token
from app.services.auth_service import _hash_email_for_log
from app.services.rate_limit_service import _auth_counters

STRONG_PW = "MyC0rrectHorseBatteryStaple!"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear in-memory rate limit counters between tests."""
    _auth_counters.clear()
    yield


def _extract_cookies(response) -> dict[str, str]:
    cookies = {}
    for cookie in response.headers.get_list("set-cookie"):
        if "=" in cookie:
            name, rest = cookie.split("=", 1)
            value = rest.split(";")[0] if ";" in rest else rest
            cookies[name.strip()] = value.strip()
    return cookies


REGISTER_BODY = {
    "first_name": "Test",
    "last_name": "User",
}


class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_register_verify_login_logout(self, client: AsyncClient, db_session: AsyncSession):
        # 1. Register
        resp = await client.post("/api/v1/auth/register", json={
            "email": "flowtest@example.com",
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })
        assert resp.status_code == 201
        assert resp.json()["message_key"] == "auth.registration_success"

        # 2. Get user and verification token
        result = await db_session.execute(select(User).where(User.email == "flowtest@example.com"))
        user = result.scalar_one_or_none()
        assert user is not None

        result = await db_session.execute(
            select(EmailVerification).where(
                EmailVerification.user_id == user.id,
                EmailVerification.used == False,
            )
        )
        verification_row = result.scalar_one_or_none()
        assert verification_row is not None

        token = generate_token()
        verification_row.token_hash = hash_token(token)
        await db_session.commit()

        # 3. Verify email
        resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert resp.status_code == 200
        assert resp.json()["message_key"] == "auth.email_verified"

        # 4. Login
        resp = await client.post("/api/v1/auth/login", json={
            "email": "flowtest@example.com",
            "password": STRONG_PW,
        })
        assert resp.status_code == 200
        login_data = resp.json()
        assert "user" in login_data
        assert login_data["user"]["email"] == "flowtest@example.com"

        cookies = _extract_cookies(resp)
        assert "sakn_session" in cookies
        assert "sakn_csrf" in cookies

        session_c = cookies["sakn_session"]
        csrf_c = cookies["sakn_csrf"]

        # 5. Get preferences
        resp = await client.get("/api/v1/preferences", headers={
            "Cookie": f"sakn_session={session_c}",
        })
        assert resp.status_code == 200
        assert "preferences" in resp.json()

        # 6. Update preferences
        resp = await client.put("/api/v1/preferences", json={"theme": "dark"}, headers={
            "Cookie": f"sakn_session={session_c}; sakn_csrf={csrf_c}",
            "X-CSRF-Token": csrf_c,
        })
        assert resp.status_code == 200
        assert resp.json()["preferences"].get("theme") == "dark"

        # 7. List sessions
        resp = await client.get("/api/v1/sessions", headers={
            "Cookie": f"sakn_session={session_c}",
        })
        assert resp.status_code == 200
        assert len(resp.json()["sessions"]) >= 1

        # 8. Logout
        resp = await client.post("/api/v1/auth/logout", headers={
            "Cookie": f"sakn_session={session_c}; sakn_csrf={csrf_c}",
            "X-CSRF-Token": csrf_c,
        })
        assert resp.status_code == 200

        # 9. Session invalid after logout
        resp = await client.get("/api/v1/sessions", headers={
            "Cookie": f"sakn_session={session_c}",
        })
        assert resp.status_code == 401

        # 10. Login again
        resp = await client.post("/api/v1/auth/login", json={
            "email": "flowtest@example.com",
            "password": STRONG_PW,
        })
        assert resp.status_code == 200
        assert "user" in resp.json()


class TestBruteForceProtection:
    @pytest.mark.asyncio
    async def test_login_lockout(self, client: AsyncClient, db_session: AsyncSession):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "lockout@example.com",
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })
        assert resp.status_code == 201

        result = await db_session.execute(select(User).where(User.email == "lockout@example.com"))
        user = result.scalar_one_or_none()
        user.status = "active"
        user.email_verified_at = utcnow()
        await db_session.commit()

        for _ in range(5):
            resp = await client.post("/api/v1/auth/login", json={
                "email": "lockout@example.com",
                "password": "WrongPassword1!",
            })
            assert resp.status_code == 401

        # Correct password should fail (locked)
        resp = await client.post("/api/v1/auth/login", json={
            "email": "lockout@example.com",
            "password": STRONG_PW,
        })
        assert resp.status_code == 401


class TestEnumerationProtection:
    @pytest.mark.asyncio
    async def test_register_duplicate_enumeration(self, client: AsyncClient):
        resp1 = await client.post("/api/v1/auth/register", json={
            "email": "enumerate@example.com",
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/auth/register", json={
            "email": "enumerate@example.com",
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })
        assert resp2.status_code == 201
        assert resp2.json() == resp1.json()

    @pytest.mark.asyncio
    async def test_login_nonexistent_enumeration(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": STRONG_PW,
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["message_key"] == "errors.invalid_credentials"

    @pytest.mark.asyncio
    async def test_password_reset_enumeration(self, client: AsyncClient):
        resp1 = await client.post("/api/v1/auth/request-password-reset", json={
            "email": "exists@example.com",
        })
        resp2 = await client.post("/api/v1/auth/request-password-reset", json={
            "email": "doesnotexist@example.com",
        })
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["message_key"] == resp2.json()["message_key"]


class TestCsrf:
    @pytest.mark.asyncio
    async def test_csrf_required_for_state_changing(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout", headers={
            "Cookie": "sakn_session=fake-token",
        })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_csrf_ok_with_header(self, client: AsyncClient, db_session: AsyncSession):
        await client.post("/api/v1/auth/register", json={
            "email": "csrftest@example.com",
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })
        result = await db_session.execute(select(User).where(User.email == "csrftest@example.com"))
        user = result.scalar_one_or_none()
        user.status = "active"
        user.email_verified_at = utcnow()
        await db_session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "csrftest@example.com",
            "password": STRONG_PW,
        })
        cookies = _extract_cookies(resp)
        session_c = cookies.get("sakn_session", "")
        csrf_c = cookies.get("sakn_csrf", "")

        resp = await client.post("/api/v1/auth/logout", headers={
            "Cookie": f"sakn_session={session_c}; sakn_csrf={csrf_c}",
            "X-CSRF-Token": csrf_c,
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_csrf_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/csrf")
        assert resp.status_code == 200
        assert "sakn_csrf" in _extract_cookies(resp)


class TestSessionCookies:
    @pytest.mark.asyncio
    async def test_session_cookie_properties(self, client: AsyncClient, db_session: AsyncSession):
        await client.post("/api/v1/auth/register", json={
            "email": "cookietest@example.com",
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })
        result = await db_session.execute(select(User).where(User.email == "cookietest@example.com"))
        user = result.scalar_one_or_none()
        user.status = "active"
        user.email_verified_at = utcnow()
        await db_session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "cookietest@example.com",
            "password": STRONG_PW,
        })

        headers = resp.headers.get_list("set-cookie")
        session_h = ""
        csrf_h = ""
        for h in headers:
            if h.startswith("sakn_session="):
                session_h = h
            elif h.startswith("sakn_csrf="):
                csrf_h = h

        assert "HttpOnly" in session_h
        assert "samesite=lax" in session_h.lower()
        assert "HttpOnly" not in csrf_h
        assert "samesite=lax" in csrf_h.lower()


class TestPasswordValidation:
    @pytest.mark.asyncio
    async def test_weak_password_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "password": "weak",
            "password_confirm": "weak",
            **REGISTER_BODY,
        })
        assert resp.status_code == 200
        assert resp.json()["message_key"] == "errors.password_too_short"

    @pytest.mark.asyncio
    async def test_password_mismatch(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "mismatch@example.com",
            "password": STRONG_PW,
            "password_confirm": "DifferentPass1!",
            **REGISTER_BODY,
        })
        assert resp.status_code == 200
        assert resp.json()["message_key"] == "errors.password_mismatch"


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_security_headers(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/csrf")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "style-src-elem 'self'" in csp
        assert "style-src-attr 'unsafe-inline'" in csp
        assert "object-src 'none'" in csp
        assert "base-uri 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
        assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert resp.headers["Cross-Origin-Embedder-Policy"] == "unsafe-none"


class TestIPBruteForce:
    """Credential stuffing scenario: 2 users x 2 failures = 4 → 5th attempt gets 429."""

    @pytest.fixture(autouse=True)
    def _clear_counter(self):
        from app.services import auth_service
        # Use an in-memory counter to simulate Redis (tests have no Redis)
        self._ip_counts: dict[str, int] = {}
        original_check = auth_service._check_ip_bruteforce
        original_record = auth_service._record_ip_bruteforce

        async def _fake_check(ip: str) -> bool:
            return self._ip_counts.get(ip, 0) >= 4  # threshold for test

        async def _fake_record(ip: str) -> None:
            self._ip_counts[ip] = self._ip_counts.get(ip, 0) + 1

        auth_service._check_ip_bruteforce = _fake_check
        auth_service._record_ip_bruteforce = _fake_record
        yield
        auth_service._check_ip_bruteforce = original_check
        auth_service._record_ip_bruteforce = original_record

    @pytest.mark.asyncio
    async def test_credential_stuffing_blocked(self, client: AsyncClient, db_session: AsyncSession):
        # Register 2 users (stay within the 3 req/h registration rate limit)
        users = []
        for i in range(2):
            email = f"stuff{i}@example.com"
            await client.post("/api/v1/auth/register", json={
                "email": email,
                "password": STRONG_PW,
                "password_confirm": STRONG_PW,
                **REGISTER_BODY,
            })
            result = await db_session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            user.status = "active"
            user.email_verified_at = utcnow()
            users.append(user)
        await db_session.commit()

        # 2 failed logins per user = 4 failed attempts (count → 4, threshold = 4)
        for user in users:
            for _ in range(2):
                resp = await client.post("/api/v1/auth/login", json={
                    "email": user.email,
                    "password": "wrong-password-for-sure",
                })
                assert resp.status_code == 401

        # 5th attempt → 429 (count = 4 >= threshold 4)
        resp = await client.post("/api/v1/auth/login", json={
            "email": users[0].email,
            "password": "wrong-password-for-sure",
        })
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in resp.headers


class TestEmailHashLogging:
    """Issue #70: SecurityEventLog.details must never contain raw email."""

    @pytest.mark.asyncio
    async def test_registration_duplicate_logs_email_hash(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Duplicate registration logs email_hash, not raw email."""
        email = "hashreg@example.com"
        # First registration succeeds
        await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })

        # Second registration triggers registration_duplicate
        await client.post("/api/v1/auth/register", json={
            "email": email,
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            **REGISTER_BODY,
        })

        expected_hash = _hash_email_for_log(email)
        row = await db_session.execute(
            select(SecurityEventLog).where(
                SecurityEventLog.event_type == "registration_duplicate",
                SecurityEventLog.details.contains(expected_hash),
            )
        )
        event = row.scalar_one_or_none()
        assert event is not None, "Expected a registration_duplicate security event"
        details = json.loads(event.details)
        assert "email_hash" in details
        assert details["email_hash"] == expected_hash
        assert email not in event.details

    @pytest.mark.asyncio
    async def test_login_failed_no_user_logs_email_hash(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Login attempt with nonexistent email logs email_hash, not raw email."""
        email = "hashlogin@example.com"
        await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": STRONG_PW,
        })

        expected_hash = _hash_email_for_log(email)
        row = await db_session.execute(
            select(SecurityEventLog).where(
                SecurityEventLog.event_type == "login_failed_no_user",
                SecurityEventLog.details.contains(expected_hash),
            )
        )
        event = row.scalar_one_or_none()
        assert event is not None, "Expected a login_failed_no_user security event"
        details = json.loads(event.details)
        assert "email_hash" in details
        assert details["email_hash"] == expected_hash
        assert email not in event.details

    @pytest.mark.asyncio
    async def test_password_reset_no_user_logs_email_hash(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Password reset for nonexistent email logs email_hash, not raw email."""
        email = "hashreset@example.com"
        await client.post("/api/v1/auth/request-password-reset", json={
            "email": email,
        })

        expected_hash = _hash_email_for_log(email)
        row = await db_session.execute(
            select(SecurityEventLog).where(
                SecurityEventLog.event_type == "password_reset_request_no_user",
                SecurityEventLog.details.contains(expected_hash),
            )
        )
        event = row.scalar_one_or_none()
        assert event is not None, "Expected a password_reset_request_no_user event"
        details = json.loads(event.details)
        assert "email_hash" in details
        assert details["email_hash"] == expected_hash
        assert email not in event.details

    def test_hash_email_for_log_case_insensitive(self):
        """Same email with different casing produces the same hash."""
        assert _hash_email_for_log("Foo@Bar.com") == _hash_email_for_log("foo@bar.com")

    def test_hash_email_for_log_strips_whitespace(self):
        """Leading/trailing whitespace is stripped before hashing."""
        assert _hash_email_for_log("  user@example.com  ") == _hash_email_for_log("user@example.com")

    def test_hash_email_for_log_different_emails_different_hash(self):
        """Different emails always produce different hashes."""
        assert _hash_email_for_log("user@example.com") != _hash_email_for_log("user@other.com")


class TestFieldLevelValidation:
    """Issue #2: Pydantic validation errors return details.fields with per-field messages."""

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422
        data = resp.json()
        error = data["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["message_key"] == "errors.validation"
        fields = error["details"]["fields"]
        assert "email" in fields
        assert fields["email"]["message_key"] == "errors.field_required"
        assert "password" in fields
        assert "password_confirm" in fields
        assert "first_name" in fields
        assert "last_name" in fields

    @pytest.mark.asyncio
    async def test_register_wrong_type(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": ["not", "a", "string"],
            "password": STRONG_PW,
            "password_confirm": STRONG_PW,
            "first_name": "Test",
            "last_name": "User",
        })
        assert resp.status_code == 422
        data = resp.json()
        fields = data["error"]["details"]["fields"]
        assert "email" in fields
        assert fields["email"]["message_key"] == "errors.invalid_type"

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422
        data = resp.json()
        fields = data["error"]["details"]["fields"]
        assert "email" in fields
        assert fields["email"]["message_key"] == "errors.field_required"
        assert "password" in fields

    @pytest.mark.asyncio
    async def test_reset_password_missing_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/reset-password", json={})
        assert resp.status_code == 422
        data = resp.json()
        fields = data["error"]["details"]["fields"]
        assert "token" in fields
        assert "password" in fields
        assert "password_confirm" in fields

    @pytest.mark.asyncio
    async def test_existing_endpoints_unaffected(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/csrf")
        assert resp.status_code == 200
        data = resp.json()
        assert "message_key" in data
