"""Dependências das rotas: sessão do banco e usuário logado.

`CurrentUserDep` é o que as rotas protegidas recebem como parâmetro. Ele lê o token
`Authorization: Bearer`, valida a assinatura e devolve o `User`. Usado por `routes/runs.py` e `routes/users.py`.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.user import User
from app.db.session import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_session)
) -> User:
    """Lê o JWT do header, confere a assinatura e a validade, e busca o usuário pelo e-mail (`sub`). Sem token válido: 401."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )

        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception from None

    query = select(User).where(User.email == email)
    result = await db.execute(query)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    return user


SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
