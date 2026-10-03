from datetime import datetime
from typing import Any

from app.core.aws import aws_session
from app.core.config import settings


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

    timestamp = datetime.utcnow().isoformat() + "Z"

    item = {
        "user_id": str(user_id),
        "timestamp": timestamp,
        "action": action,
    }

    if resource_id is not None:
        item["resource_id"] = str(resource_id)
    if ip_address is not None:
        item["ip_address"] = ip_address
    if details:
        item["details"] = details

    async with aws_session.resource("dynamodb") as dynamodb:
        table = await dynamodb.Table(settings.dynamodb_audit_table)
        await table.put_item(Item=item)
