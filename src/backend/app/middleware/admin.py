"""Admin middleware — verify administrator role on /admin/* routes."""

from fastapi import HTTPException, Request


async def require_admin(request: Request) -> None:
    """Dependency: raise 403 if the authenticated user is not an administrator."""
    role = getattr(request.state, "role", "visitor")
    if role != "administrator":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
