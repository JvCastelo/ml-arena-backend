from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtifactRead(BaseModel):
    """Artifact como a API devolve. A chave do S3 não é exposta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    size_bytes: int | None
    error_message: str | None
    created_at: datetime
