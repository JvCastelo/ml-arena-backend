import json

from redis import asyncio as aioredis

from app.core.config import settings

redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_cache(key: str) -> dict | None:
    """Busca um valor no Redis e converte de JSON para dicionário."""
    data = await redis_client.get(key)
    if data:
        return json.loads(data)
    return None


async def set_cache(key: str, value: dict, expire_seconds: int = 300) -> None:
    """Salva um dicionário do Redis como JSON, com tempo de expiração padrão de 5 minutos."""
    await redis_client.set(key, json.dumps(value), ex=expire_seconds)


async def invalidate_user_cache(user_id: int) -> None:
    """Apaga todas as chaves de cache associadas a um usuário específico."""
    cursor = b"0"
    match_pattern = f"runs_user_{user_id}:*"

    while cursor:
        cursor, keys = await redis_client.scan(cursor=cursor, match=match_pattern)
        if keys:
            await redis_client.delete(*keys)
