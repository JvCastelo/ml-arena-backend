from typing import Any
from app.repositories import audit_repository


async def log_user_action(
    user_id: int,
    action: str,
    resource_id: int | str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Serviço central de auditoria.
    Prepara e higieniza os dados antes de enviá-los para armazenamento.
    """
    if details:
        safe_details = details.copy()

        sensitive_keys = ["password", "password_hash", "token", "secret"]

        for key in sensitive_keys:
            if key in safe_details:
                safe_details[key] = "*** MASCARADO ***"

        details = safe_details

    await audit_repository.insert_log(
        user_id=user_id,
        action=action,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details,
    )
