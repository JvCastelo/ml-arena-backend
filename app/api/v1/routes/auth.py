"""Rota de login: `POST /api/v1/auth/login`.

Recebe o formulário (username = e-mail, password) no formato OAuth2 e devolve o token JWT.
A lógica fica em `app/services/auth_service.py`. Registra a ação LOGIN na auditoria.
"""

from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.token import Token
from app.services import auth_service, audit_service

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_access_token(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Autentica e devolve {access_token, token_type}. Espera form-data, não JSON. Grava LOGIN no log de auditoria (só em caso de sucesso)."""
    logged_user = await auth_service.authenticate_user(
        db, form_data.username, form_data.password
    )

    background_tasks.add_task(
        audit_service.log_user_action,
        user_id=logged_user["user_id"],
        action="LOGIN",
        ip_address=request.client.host if request.client else None,
        details={"email_used": form_data.username},
    )

    return logged_user
