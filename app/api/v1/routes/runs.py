"""Rotas de runs: CRUD, listagem paginada, comparação e upload do CSV.

Todas exigem login (`CurrentUserDep`). As regras ficam em
`app/services/run_service.py`; a rota só traduz HTTP para o service e devolve a resposta.
"""

from typing import Annotated
from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile, status
from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.artifact import ArtifactRead
from app.services.csv_validation import MAX_CSV_BYTES
from app.schemas.run import (
    RunComparison,
    RunCreate,
    RunDetail,
    RunList,
    RunRead,
    RunStatus,
    RunUpdate,
)
from app.services import run_service
from app.repositories import run_repository

router = APIRouter()


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunCreate, session: SessionDep, user: CurrentUserDep):
    """Cria um run do usuário logado (nasce com status created)."""
    return await run_service.create_run(session, user.id, payload)


@router.get("", response_model=RunList)
async def list_runs(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    algorithm: str | None = None,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
):
    """Lista os runs do usuário, paginados (limit/offset), com filtros opcionais de algoritmo e status."""
    items, total = await run_repository.get_runs_paginated(
        session, user.id, limit, offset, algorithm, status_filter
    )
    return RunList(items=items, total=total, limit=limit, offset=offset)


# Precisa vir antes de "/{run_id}": senão "compare" é lido como id e responde 422.
@router.get("/compare", response_model=RunComparison)
async def compare(run_a: int, run_b: int, session: SessionDep, user: CurrentUserDep):
    """Dois runs do usuário lado a lado. 404 se algum deles não for seu."""
    return await run_service.compare_runs(session, user.id, run_a, run_b)


@router.post(
    "/{run_id}/measured-predicted",
    response_model=ArtifactRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_measured_predicted(
    run_id: int,
    session: SessionDep,
    user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """Sobe o CSV medidoxprevisto do run. Um por run: se já existir, 409."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "O arquivo precisa ser um .csv."
        )
    # Lê no máximo limite+1 bytes: se vier mais que isso, sabemos que passou do limite sem ler tudo.
    data = await file.read(MAX_CSV_BYTES + 1)
    if len(data) > MAX_CSV_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"O arquivo passa do limite de {MAX_CSV_BYTES // (1024 * 1024)} MB.",
        )
    return await run_service.upload_measured_predicted(session, run_id, user.id, data)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    """Detalhe de um run, com a lista de artifacts. 404 se não for do usuário."""
    return await run_service.get_owned_run_or_404(
        session, run_id, user.id, with_artifacts=True
    )


@router.patch("/{run_id}", response_model=RunRead)
async def update_run(
    run_id: int, payload: RunUpdate, session: SessionDep, user: CurrentUserDep
):
    """Edita campos do run (PATCH parcial). O status não é editável pelo cliente."""
    return await run_service.update_run(session, run_id, user.id, payload)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    """Apaga o run, seus artifacts (banco) e os arquivos no S3."""
    await run_service.delete_run(session, run_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
