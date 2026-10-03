"""Agrega os routers da API v1 sob os prefixos de cada assunto.

Resultado: /api/v1/runs, /api/v1/auth e /api/v1/users. Incluído em `app/main.py`.
"""

from fastapi import APIRouter

from app.api.v1.routes import runs
from app.api.v1.routes import users
from app.api.v1.routes import auth

api_router = APIRouter()
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
