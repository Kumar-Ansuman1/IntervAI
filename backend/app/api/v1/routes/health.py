from fastapi import APIRouter


router = APIRouter()


@router.get("/")
def home():
    return {"status": "healthy", "project": "IntervAI"}


@router.get("/health")
def health_check():
    return {"status": "healthy", "project": "IntervAI"}
