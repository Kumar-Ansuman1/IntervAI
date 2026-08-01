from fastapi import FastAPI

from backend.app.api.v1.router import api_router


app = FastAPI(title="IntervAI API")
app.include_router(api_router)
