from fastapi import APIRouter

from app.api.v1.routes import runs

api_router = APIRouter()
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
