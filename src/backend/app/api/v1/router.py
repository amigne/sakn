from fastapi import APIRouter

from app.api.v1.endpoints.tools import router as tools_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(tools_router)
