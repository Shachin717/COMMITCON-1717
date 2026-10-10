from fastapi import APIRouter
from app.api.admin import admin_router
from app.api.v1.endpoints import auth, health

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(admin_router, prefix="/admin")

__all__ = ["api_router"]
