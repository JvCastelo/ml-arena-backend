from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.artifact import ArtifactRead

RunStatus = Literal["created", "processing", "done", "failed"]


class RunCreate(BaseModel):
    """Corpo do POST /runs. O dono vem do usuário logado, nunca do corpo."""

    name: str = Field(min_length=1, max_length=120)
    algorithm: str = Field(min_length=1, max_length=120)
    hyperparams: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)


class RunUpdate(BaseModel):
    """Corpo do PATCH /runs/{id}.

    Todos os campos são opcionais, mas um campo enviado não pode ser null. O
    `status` fica de fora de propósito: quem o define é o worker.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    algorithm: str | None = Field(default=None, min_length=1, max_length=120)
    hyperparams: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> Self:
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} não pode ser null")
        return self


class RunRead(BaseModel):
    """Run como a API devolve. O `user_id` não é exposto."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    algorithm: str
    hyperparams: dict[str, Any]
    metrics: dict[str, Any]
    status: RunStatus
    error_message: str | None
    processing_duration_s: float | None
    created_at: datetime
    updated_at: datetime


class RunDetail(RunRead):
    """Run com a lista de artifacts (GET /runs/{id})."""

    artifacts: list[ArtifactRead]


class RunList(BaseModel):
    """Página de runs: `total` é o número de runs que batem com o filtro."""

    items: list[RunRead]
    total: int
    limit: int
    offset: int
