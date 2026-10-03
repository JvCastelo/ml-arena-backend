"""Configuração da aplicação, lida das variáveis de ambiente (ou do `.env`).

Usado por praticamente tudo: `app/db/session.py` (banco), `app/core/security.py`
(JWT), `app/services/storage.py` (S3), `app/services/messaging.py` (SNS),
`worker/consumer.py` (SQS). Se uma variável obrigatória faltar, o import falha
e a aplicação nem sobe, em vez de quebrar numa requisição qualquer.
"""

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas das variáveis de ambiente (ou do `.env`, se existir).

    Todas são obrigatórias: faltando alguma, a aplicação não sobe.
    """

    # Banco (RDS na AWS, container `db` no compose)
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    # JWT: a chave assina os tokens; o algoritmo e a validade têm default
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    # AWS: região, bucket, tópico, fila e tabela de auditoria
    aws_region: str
    s3_bucket_name: str
    sns_topic_arn: str
    sqs_queue_url: str
    dynamodb_audit_table: str | None = None
    # Chaves opcionais: se ausentes, o boto3 usa a cadeia padrão (ambiente, IAM role)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None

    # `extra="ignore"`: variáveis que não estão aqui (ex.: AWS_* usadas pelo boto3) são ignoradas
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @computed_field
    @property
    def database_url(self) -> str:
        """URL assíncrona do banco, montada a partir das partes acima."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


# Instância única, criada no import. Os outros módulos fazem `from app.core.config import settings`.
settings = Settings()
