import secrets

from fastapi import Request, Response

CSRF_COOKIE = "sakn_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str, secure: bool = False) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        httponly=False,  # JS must read it
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE, path="/")


def get_csrf_from_request(request: Request) -> str | None:
    return request.cookies.get(CSRF_COOKIE)


def validate_csrf(request: Request) -> bool:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token, header_token)
