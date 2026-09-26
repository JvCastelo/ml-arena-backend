from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Uma sessão por requisição: commit se deu certo, rollback se deu erro.

    Atenção: no FastAPI este commit roda depois de a resposta ser enviada, então
    um erro nele não chega ao cliente. Rotas que escrevem devem chamar
    `await session.commit()` elas mesmas antes de retornar.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Versão "com `async with`" para usar fora do FastAPI (notebook, worker, scripts)
session_scope = asynccontextmanager(get_session)
