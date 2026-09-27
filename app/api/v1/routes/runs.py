from typing import Annotated
from fastapi import APIRouter, Query, Response, status
from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.run import RunCreate, RunDetail, RunList, RunRead, RunStatus, RunUpdate
from app.services import run_service
from app.repositories import run_repository

router = APIRouter()


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunCreate, session: SessionDep, user: CurrentUserDep):
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
    items, total = await run_repository.get_runs_paginated(
        session, user.id, limit, offset, algorithm, status_filter
    )
    return RunList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    return await run_service.get_owned_run_or_404(
        session, run_id, user.id, with_artifacts=True
    )


@router.patch("/{run_id}", response_model=RunRead)
async def update_run(
    run_id: int, payload: RunUpdate, session: SessionDep, user: CurrentUserDep
):
    return await run_service.update_run(session, run_id, user.id, payload)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    await run_service.delete_run(session, run_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
