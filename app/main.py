from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Ao desligar a API, fecha o pool de conexões com o banco."""
    yield
    await engine.dispose()


app = FastAPI(title="ML Arena", version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Health check do ALB: só diz que o processo está de pé, sem tocar no banco."""
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
