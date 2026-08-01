from fastapi import APIRouter

from backend.app.api.v1.routes import (
    adaptive_interviews,
    fixed_interviews,
    health,
    resumes,
    speech,
)


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(resumes.router)
api_router.include_router(fixed_interviews.router)
api_router.include_router(speech.router)
api_router.include_router(adaptive_interviews.router)
