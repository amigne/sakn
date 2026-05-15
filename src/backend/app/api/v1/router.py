from fastapi import APIRouter

from app.api.v1.endpoints.tools import router as tools_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.preferences import router as preferences_router
from app.api.v1.endpoints.sessions import router as sessions_router
from app.api.v1.endpoints.account import router as account_router
from app.api.v1.endpoints.admin import router as admin_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(account_router)
v1_router.include_router(tools_router)
v1_router.include_router(preferences_router)
v1_router.include_router(sessions_router)
v1_router.include_router(admin_router)
