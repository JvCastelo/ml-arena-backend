"""Rotas de usuário: cadastro (`POST /api/v1/users/`) e dados do usuário logado (`GET /api/v1/users/me`).

A regra do cadastro fica em `app/services/auth_service.py`.
"""

from fastapi import APIRouter, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_session
from app.db.models import User
from app.schemas.user import UserCreate, UserResponse
from app.services import auth_service

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_session)):
    """Cadastra um usuário novo e devolve os dados públicos (sem a senha). 201 se criou."""
    return await auth_service.register_user(db, user_in)


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Devolve o usuário do token. Útil pra confirmar que a autenticação está funcionando."""
    return current_user
