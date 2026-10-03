"""Acesso ao banco para usuários: busca por e-mail e criação.

Quem chama: `app/services/auth_service.py`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Busca um usuário pelo e-mail (é o login). Retorna None se não existir."""
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    return result.scalars().first()


async def create_user(
    session: AsyncSession, name: str, email: str, password_hash: str
) -> User:
    """Cria o usuário com o hash da senha (nunca a senha pura) e comita."""
    db_user = User(name=name, email=email, password_hash=password_hash)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user
