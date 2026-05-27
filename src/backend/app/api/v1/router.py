from fastapi import APIRouter

from app.api.v1.endpoints.account import router as account_router
from app.api.v1.endpoints.admin_logs import router as admin_logs_router
from app.api.v1.endpoints.admin_modules import router as admin_modules_router
from app.api.v1.endpoints.admin_rate_limits import router as admin_rate_limits_router
from app.api.v1.endpoints.admin_settings import router as admin_settings_router
from app.api.v1.endpoints.admin_tools import router as admin_tools_router
from app.api.v1.endpoints.admin_users import router as admin_users_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.preferences import router as preferences_router
from app.api.v1.endpoints.public_settings import router as public_settings_router
from app.api.v1.endpoints.sessions import router as sessions_router
from app.api.v1.endpoints.tools import router as tools_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(account_router)
v1_router.include_router(tools_router)
v1_router.include_router(preferences_router)
v1_router.include_router(sessions_router)
v1_router.include_router(admin_users_router)
v1_router.include_router(admin_tools_router)
v1_router.include_router(admin_rate_limits_router)
v1_router.include_router(admin_modules_router)
v1_router.include_router(admin_logs_router)
v1_router.include_router(admin_settings_router)
v1_router.include_router(public_settings_router)
