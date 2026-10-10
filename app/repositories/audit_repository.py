from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.core.aws import aws_session
from app.core.config import settings


def _to_dynamo(value: Any) -> Any:
    """Converte floats para Decimal, porque o DynamoDB não aceita float do Python."""
    if isinstance(value, float):
        # str() evita a imprecisão binária: Decimal(0.1) vira 0.10000000055...
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


async def insert_log(
    user_id: int,
    action: str,
    resource_id: int | str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Grava um log de auditoria no DynamoDB de forma assíncrona.
    """

    timestamp = datetime.now(UTC).isoformat()

    item = {
        "user_id": str(user_id),
        "timestamp": f"{timestamp}#{uuid4().hex[:8]}",  # chave composta: timestamp + sufixo aleatório
        "action": action,
    }

    if resource_id is not None:
        item["resource_id"] = str(resource_id)
    if ip_address is not None:
        item["ip_address"] = ip_address
    if details:
        item["details"] = _to_dynamo(details)

    async with aws_session.resource("dynamodb") as dynamodb:
        table = await dynamodb.Table(settings.dynamodb_audit_table)
        await table.put_item(Item=item)
