"""Session cookie name management.

The __Host- prefix (RFC 6265bis) requires Secure, Path=/, and no Domain.
In development (HTTP), the prefix is omitted so browsers accept the cookie.
"""

from fastapi import Request

# Order matters: try __Host- prefixed first (prod), then unprefixed (dev)
SESSION_COOKIE_NAMES = ("__Host-sakn_session", "sakn_session")


def session_cookie_name(secure: bool) -> str:
    """Return the session cookie name to SET. Uses __Host- prefix when Secure flag is set."""
    return "__Host-sakn_session" if secure else "sakn_session"


def get_session_token(request: Request) -> str | None:
    """Read session token from request cookies, trying both cookie names."""
    for name in SESSION_COOKIE_NAMES:
        token = request.cookies.get(name)
        if token:
            return token
    return None
