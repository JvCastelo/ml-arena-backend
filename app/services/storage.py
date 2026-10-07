"""Acesso ao S3: subir, baixar, apagar e gerar links temporários.

Único módulo que fala com o S3. Usado pelo `run_service.py` (CSV e URLs) e pelo
`worker/consumer.py` (baixa o CSV, sobe os PNGs). Credenciais vêm do ambiente (AWS_*).
"""

from app.core.aws import aws_session
from app.core.config import settings


def measured_predicted_key(run_id: int) -> str:
    """Chave do CSV no bucket: runs/{run_id}/measured_predicted.csv."""
    return f"runs/{run_id}/measured_predicted.csv"


async def upload_measured_predicted(run_id: int, data: bytes) -> str:
    """Sobe o CSV medidoxprevisto e devolve a chave do objeto no bucket."""
    key = measured_predicted_key(run_id)
    async with aws_session.client("s3") as s3:
        await s3.put_object(
            Bucket=settings.s3_bucket_name, Key=key, Body=data, ContentType="text/csv"
        )
    return key


async def download_object(key: str) -> bytes:
    """Baixa um objeto do S3 e devolve os bytes (usado pelo worker para ler o CSV)."""
    async with aws_session.client("s3") as s3:
        response = await s3.get_object(Bucket=settings.s3_bucket_name, Key=key)
        return await response["Body"].read()


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    """Sobe bytes (ex.: PNG) no S3 com o content-type informado."""
    async with aws_session.client("s3") as s3:
        s3.put_object(
            Bucket=settings.s3_bucket_name, Key=key, Body=data, ContentType="text/csv"
        )


PRESIGNED_URL_TTL_SECONDS = 300


async def presigned_url(key: str) -> str:
    """Link de leitura temporário. O bucket continua privado; a assinatura expira sozinha."""
    # Calcula a assinatura localmente, sem chamada de rede, então não precisa de thread.
    async with aws_session.client("s3") as s3:
        return await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": key},
            ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
        )


async def delete_objects(keys: list[str]) -> None:
    """Apaga os objetos dados, se houver algum. Usado quando um run é apagado."""
    if keys:
        async with aws_session.client("s3") as s3:
            await s3.delete_objects(
                Bucket=settings.s3_bucket_name,
                Delete={"Objects": [{"Key": key} for key in keys]},
            )
