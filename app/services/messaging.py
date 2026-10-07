"""Publicação no SNS: avisa que um CSV novo está no S3 e precisa virar plots.

O aviso é só um bilhete (run_id, s3_key, type, timestamp). O conteúdo do CSV fica no S3.
Chamado por `run_service.py` depois do upload. O tópico entrega a cópia na fila SQS que o worker lê.
"""

import json
from datetime import UTC, datetime

from app.core.aws import aws_session
from app.core.config import settings


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

    async with aws_session.client("sns") as sns:
        await sns.publish(TopicArn=settings.sns_topic_arn, Message=message)
