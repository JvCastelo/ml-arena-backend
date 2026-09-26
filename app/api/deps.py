from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# PROVISÓRIO — remover antes do deploy. Qualquer cliente pode se passar por
# qualquer usuário mandando o header X-User-Id. Será substituído pela leitura
# do JWT, mantendo a mesma assinatura (as rotas só dependem de CurrentUserDep).
async def get_current_user(
    session: SessionDep,
    x_user_id: Annotated[int | None, Header()] = None,
) -> User:
    """Usuário logado, identificado (por ora) pelo header X-User-Id. 401 se ausente."""
    if x_user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-User-Id header")

    user = await session.get(User, x_user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
