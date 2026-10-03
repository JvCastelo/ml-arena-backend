"""Publicação no SNS: avisa que um CSV novo está no S3 e precisa virar plots.

O aviso é só um bilhete (run_id, s3_key, type, timestamp). O conteúdo do CSV fica no S3.
Chamado por `run_service.py` depois do upload. O tópico entrega a cópia na fila SQS que o worker lê.
"""

import asyncio
import json
from datetime import UTC, datetime
from functools import cache

import boto3

from app.core.config import settings


@cache
def _sns_client():
    """Cliente boto3 do SNS, criado uma vez e reaproveitado."""
    return boto3.client("sns", region_name=settings.aws_region)


def _publish(message: str) -> None:
    """Publica a mensagem no tópico. Versão síncrona."""
    _sns_client().publish(TopicArn=settings.sns_topic_arn, Message=message)


async def publish_csv_uploaded(run_id: int, s3_key: str, type_: str) -> None:
    """Avisa o worker que um CSV novo está no S3 e precisa virar plots."""
    message = json.dumps(
        {
            "run_id": run_id,
            "s3_key": s3_key,
            "type": type_,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    # boto3 é síncrono: roda numa thread pra não travar o event loop.
    await asyncio.to_thread(_publish, message)
