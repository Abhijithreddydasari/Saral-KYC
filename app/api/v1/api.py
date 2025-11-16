"""API router that aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1.endpoints import applications, assist, health

api_router = APIRouter()
api_router.include_router(health.router, prefix="/system")
api_router.include_router(applications.router)
api_router.include_router(assist.router)

