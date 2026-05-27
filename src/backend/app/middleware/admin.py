"""Admin middleware — verify administrator role on /admin/* routes."""

from fastapi import HTTPException, Request

from app.constants.roles import ROLE_ADMINISTRATOR, ROLE_VISITOR


async def require_admin(request: Request) -> None:
    """Dependency: raise 403 if the authenticated user is not an administrator."""
    role = getattr(request.state, "role", ROLE_VISITOR)
    if role != ROLE_ADMINISTRATOR:
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
