"""Rotas de usuário: cadastro (`POST /api/v1/users/`) e dados do usuário logado (`GET /api/v1/users/me`).

A regra do cadastro fica em `app/services/auth_service.py`. O cadastro é registrado na auditoria.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas.user import UserCreate, UserResponse
from app.services import audit_service, auth_service

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    """Cadastra um usuário novo e devolve os dados públicos (sem a senha). 201 se criou. Grava CREATE_USER na auditoria."""
    user_created = await auth_service.register_user(db, user_in)

    background_tasks.add_task(
        audit_service.log_user_action,
        user_id=user_created.id,
        action="CREATE_USER",
        ip_address=request.client.host if request.client else None,
        details=user_in.model_dump(mode="json"),
    )
    return user_created


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Devolve o usuário do token. Útil pra confirmar que a autenticação está funcionando."""
    return current_user
