"""Acesso ao S3: subir, baixar, apagar e gerar links temporários.

Único módulo que fala com o S3. Usado pelo `run_service.py` (CSV e URLs) e pelo
`worker/consumer.py` (baixa o CSV, sobe os PNGs). Credenciais vêm do ambiente (AWS_*).
"""

import asyncio
from functools import cache

import boto3

from app.core.config import settings


@cache
def _s3_client():
    # boto3 lê AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN do ambiente.
    """Cliente boto3 do S3, criado uma vez e reaproveitado (cache). Lê as credenciais do ambiente."""
    return boto3.client("s3", region_name=settings.aws_region)


def measured_predicted_key(run_id: int) -> str:
    """Chave do CSV no bucket: runs/{run_id}/measured_predicted.csv."""
    return f"runs/{run_id}/measured_predicted.csv"


def _put_object(key: str, data: bytes) -> None:
    """Grava o CSV no S3. Versão síncrona, chamada dentro de uma thread."""
    _s3_client().put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType="text/csv",
    )


async def upload_measured_predicted(run_id: int, data: bytes) -> str:
    """Sobe o CSV medido×previsto e devolve a chave do objeto no bucket."""
    key = measured_predicted_key(run_id)
    # boto3 é síncrono: roda numa thread pra não travar o event loop do FastAPI.
    await asyncio.to_thread(_put_object, key, data)
    return key


def _get_object(key: str) -> bytes:
    """Lê o conteúdo de um objeto do S3. Versão síncrona."""
    return (
        _s3_client().get_object(Bucket=settings.s3_bucket_name, Key=key)["Body"].read()
    )


async def download_object(key: str) -> bytes:
    """Baixa um objeto do S3 e devolve os bytes (usado pelo worker para ler o CSV)."""
    return await asyncio.to_thread(_get_object, key)


def _put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Grava bytes no S3 com o content-type informado. Versão síncrona."""
    _s3_client().put_object(
        Bucket=settings.s3_bucket_name, Key=key, Body=data, ContentType=content_type
    )


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    """Sobe bytes (ex.: PNG) no S3 com o content-type informado."""
    await asyncio.to_thread(_put_bytes, key, data, content_type)


PRESIGNED_URL_TTL_SECONDS = 300


def presigned_url(key: str) -> str:
    """Link de leitura temporário. O bucket continua privado; a assinatura expira sozinha."""
    # Calcula a assinatura localmente, sem chamada de rede, então não precisa de thread.
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key},
        ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
    )


def _delete_objects(keys: list[str]) -> None:
    """Apaga vários objetos do S3 numa chamada só. Versão síncrona."""
    _s3_client().delete_objects(
        Bucket=settings.s3_bucket_name,
        Delete={"Objects": [{"Key": key} for key in keys]},
    )


async def delete_objects(keys: list[str]) -> None:
    """Apaga os objetos dados, se houver algum. Usado quando um run é apagado."""
    if keys:
        await asyncio.to_thread(_delete_objects, keys)
