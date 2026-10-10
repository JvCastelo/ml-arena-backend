"""Regras de negócio das runs: dono, CRUD, comparação e upload do CSV.

Este é o cérebro entre as rotas (`app/api/v1/routes/runs.py`) e os repositórios.
Chama `run_repository` e `artifact_repository` (banco), `storage` (S3),
`messaging` (SNS) e `csv_validation` (checagem do CSV). Erros de regra viram HTTPException.
"""

import logging

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache, invalidate_user_cache, set_cache
from app.db.models import Artifact, Run
from app.repositories import artifact_repository, run_repository
from app.schemas.run import (
    ComparedRun,
    RunComparison,
    RunCreate,
    RunList,
    RunRead,
    RunUpdate,
)
from app.services import messaging, storage
from app.services.csv_validation import (
    CsvValidationError,
    validate_measured_predicted_csv,
)

logger = logging.getLogger(__name__)

# Nome do plot na resposta da API -> tipo do artifact no banco.
PLOT_ARTIFACT_TYPES = {
    "measured_predicted": "plot_measured_predicted",
    "residuals": "plot_residuals",
}
MEASURED_PREDICTED_CSV = "csv_measured_predicted"


async def get_owned_run_or_404(
    session: AsyncSession, run_id: int, user_id: int, with_artifacts: bool = False
) -> Run:
    """Busca um run do usuário. Se não existir ou for de outro usuário, levanta 404 (sem revelar qual dos dois)."""
    run = await run_repository.get_run_by_id_and_user(
        session, run_id, user_id, with_artifacts
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


async def list_runs(
    session: AsyncSession,
    user_id: int,
    limit: int,
    offset: int,
    algorithm: str | None,
    status_filter: str | None,
) -> dict:
    """Busca as runs no cache; se não achar, vai no banco e salva no cache."""
    cache_key = f"runs_user_{user_id}:lim_{limit}:off_{offset}:alg_{algorithm}:stat_{status_filter}"

    cached_data = await get_cache(cache_key)

    if cached_data:
        return cached_data

    items, total = await run_repository.get_runs_paginated(
        session, user_id, limit, offset, algorithm, status_filter
    )

    response_data = RunList(
        items=items, total=total, limit=limit, offset=offset
    ).model_dump(mode="json")

    await set_cache(cache_key, response_data, expire_seconds=300)

    return response_data


async def create_run(session: AsyncSession, user_id: int, payload: RunCreate) -> Run:
    """Cria um run do usuário a partir do payload validado."""
    run = await run_repository.create_run(session, user_id, payload.model_dump())
    await invalidate_user_cache(user_id)
    return run


async def update_run(
    session: AsyncSession, run_id: int, user_id: int, payload: RunUpdate
) -> Run:
    """Edita só os campos enviados (PATCH parcial). O status não é editável aqui."""
    run = await get_owned_run_or_404(session, run_id, user_id)
    update_data = payload.model_dump(exclude_unset=True)
    update_run = await run_repository.update_run(session, run, update_data)
    await invalidate_user_cache(user_id)
    return update_run


async def delete_run(session: AsyncSession, run_id: int, user_id: int) -> Run:
    """Apaga o run no banco e, depois, os arquivos dele no S3 (melhor esforço)."""
    run = await get_owned_run_or_404(session, run_id, user_id, with_artifacts=True)
    s3_keys = [artifact.s3_key for artifact in run.artifacts]
    # Banco primeiro: o cascade apaga os artifacts. Depois o S3. Se o S3 falhar,
    # sobra arquivo órfão no bucket, mas nunca linha apontando pra arquivo que sumiu.
    await run_repository.delete_run(session, run)
    try:
        await storage.delete_objects(s3_keys)
    except (BotoCoreError, ClientError):
        logger.exception(
            "Run %s apagado, mas falhou ao apagar objetos do S3: %s", run_id, s3_keys
        )
    await invalidate_user_cache(user_id)
    return run


async def _compared(run: Run) -> ComparedRun:
    # Só plot já gerado (status done) ganha URL. Os outros continuam null.
    """Monta um lado da comparação. Plot com status done ganha URL pré-assinada; os demais ficam null."""
    done = {
        artifact.type: artifact
        for artifact in run.artifacts
        if artifact.status == "done"
    }
    plots: dict[str, str | None] = {}

    for key, artifact_type in PLOT_ARTIFACT_TYPES.items():
        if artifact_type in done:
            plots[key] = await storage.presigned_url(done[artifact_type].s3_key)
        else:
            plots[key] = None

    return ComparedRun(**RunRead.model_validate(run).model_dump(), plots=plots)


async def compare_runs(
    session: AsyncSession, user_id: int, run_a_id: int, run_b_id: int
) -> RunComparison:
    # Os dois passam pelo mesmo filtro de dono: se algum não for do usuário, 404.
    """Devolve os dois runs prontos pra tela de comparação, ambos checados quanto ao dono."""
    run_a = await get_owned_run_or_404(session, run_a_id, user_id, with_artifacts=True)
    run_b = await get_owned_run_or_404(session, run_b_id, user_id, with_artifacts=True)
    return RunComparison(run_a=await _compared(run_a), run_b=await _compared(run_b))


async def _start_csv_upload(session: AsyncSession, run: Run) -> Artifact:
    """Registra o artifact como pending antes do upload. Decide o 409 pelo status do que já existe."""
    key = storage.measured_predicted_key(run.id)
    existing = await artifact_repository.get_artifact_by_type(
        session, run.id, MEASURED_PREDICTED_CSV
    )

    if existing is None:
        try:
            return await artifact_repository.create_artifact(
                session, run.id, MEASURED_PREDICTED_CSV, key, status="pending"
            )
        except IntegrityError:
            # Duas requisições criaram ao mesmo tempo: o UNIQUE do banco deixou só uma passar.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Já existe um upload em andamento para este run.",
            ) from None

    if existing.status == "failed" and await artifact_repository.claim_failed_artifact(
        session, existing
    ):
        return existing

    if existing.status == "done":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este run já tem um CSV medidoxprevisto. Apague o run e crie outro.",
        )
    raise HTTPException(
        status.HTTP_409_CONFLICT, "Já existe um upload em andamento para este run."
    )


async def upload_measured_predicted(
    session: AsyncSession, run_id: int, user_id: int, data: bytes
) -> Artifact:
    """Sobe o CSV medidoxprevisto de um run. Um CSV por run: se já existir, 409."""
    run = await get_owned_run_or_404(session, run_id, user_id)
    try:
        validate_measured_predicted_csv(data)
    except CsvValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    artifact = await _start_csv_upload(session, run)

    # Sobe o arquivo e depois avisa o worker. Se qualquer um dos dois falhar, o artifact
    # fica failed e o reenvio funciona (a mesma regra do item 2).
    try:
        await storage.upload_measured_predicted(run.id, data)
        await messaging.publish_csv_uploaded(
            run.id, artifact.s3_key, MEASURED_PREDICTED_CSV
        )
    except (BotoCoreError, ClientError):
        # Mensagem genérica: o erro bruto do boto3 pode expor nome de bucket e detalhes da AWS.
        await artifact_repository.update_artifact(
            session,
            artifact,
            status="failed",
            error_message="Falha ao processar o envio do CSV. Tente de novo.",
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Falha ao processar o envio do CSV. Tente de novo.",
        ) from None

    updated_artifact = await artifact_repository.update_artifact(
        session, artifact, status="done", size_bytes=len(data)
    )

    await invalidate_user_cache(user_id)

    return updated_artifact
