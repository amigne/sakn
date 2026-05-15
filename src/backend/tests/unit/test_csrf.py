import secrets

import pytest
from fastapi import Request, Response
from starlette.testclient import TestClient

from app.security.csrf import (
    CSRF_COOKIE,
    CSRF_HEADER,
    generate_csrf_token,
    set_csrf_cookie,
    clear_csrf_cookie,
    validate_csrf,
    get_csrf_from_request,
)


class TestCsrfTokenGeneration:
    def test_generate_token(self):
        t1 = generate_csrf_token()
        t2 = generate_csrf_token()
        assert len(t1) == 43
        assert t1 != t2


class TestCsrfCookie:
    def test_set_csrf_cookie(self):
        resp = Response()
        token = generate_csrf_token()
        set_csrf_cookie(resp, token, secure=False)
        cookie_header = resp.headers.get("set-cookie", "")
        assert CSRF_COOKIE in cookie_header
        assert token in cookie_header
        assert "HttpOnly" not in cookie_header  # JS must read it

    def test_set_csrf_cookie_secure(self):
        resp = Response()
        token = generate_csrf_token()
        set_csrf_cookie(resp, token, secure=True)
        cookie_header = resp.headers.get("set-cookie", "")
        assert "Secure" in cookie_header

    def test_clear_csrf_cookie(self):
        resp = Response()
        clear_csrf_cookie(resp)
        cookie_header = resp.headers.get("set-cookie", "")
        assert "Max-Age=0" in cookie_header or f"{CSRF_COOKIE}=;" in cookie_header


class TestCsrfValidation:
    def test_valid_csrf(self):
        token = generate_csrf_token()
        # Build a mock request
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"cookie", f"{CSRF_COOKIE}={token}".encode()),
                (b"x-csrf-token", token.encode()),
            ],
        }
        request = Request(scope)
        assert validate_csrf(request)

    def test_missing_cookie(self):
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"x-csrf-token", b"some-token")],
        }
        request = Request(scope)
        assert not validate_csrf(request)

    def test_missing_header(self):
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"cookie", f"{CSRF_COOKIE}=some-token".encode())],
        }
        request = Request(scope)
        assert not validate_csrf(request)

    def test_mismatch(self):
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [
                (b"cookie", f"{CSRF_COOKIE}=token-a".encode()),
                (b"x-csrf-token", b"token-b"),
            ],
        }
        request = Request(scope)
        assert not validate_csrf(request)

    def test_safe_methods_skip(self):
        # GET requests don't need CSRF header, but we just test the validator is callable
        token = generate_csrf_token()
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [(b"cookie", f"{CSRF_COOKIE}={token}".encode())],
        }
        request = Request(scope)
        # CSRF validation still works on GET, but middleware should skip it
        assert not validate_csrf(request)
