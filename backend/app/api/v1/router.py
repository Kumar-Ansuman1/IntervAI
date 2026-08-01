from fastapi import APIRouter

from backend.app.api.v1.routes import (
    health,
    interviews,
    resumes,
    speech,
)


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(resumes.router)
api_router.include_router(speech.router)
api_router.include_router(interviews.router)
