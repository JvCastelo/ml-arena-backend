from fastapi import APIRouter

from app.api.v1.routes import runs
from app.api.v1.routes import users
from app.api.v1.routes import auth

api_router = APIRouter()
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
