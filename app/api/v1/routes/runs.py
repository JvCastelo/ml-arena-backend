from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUserDep, SessionDep
from app.db.models import Run, User
from app.schemas.run import (
    RunCreate,
    RunDetail,
    RunList,
    RunRead,
    RunStatus,
    RunUpdate,
)

router = APIRouter()


async def get_owned_run(
    session: AsyncSession, run_id: int, user: User, *, with_artifacts: bool = False
) -> Run:
    """Busca um run do usuário. Run inexistente ou de outro usuário => 404.

    O filtro por dono está na própria query, então não há como esquecer a
    checagem de permissão. Responder 404 (e não 403) evita revelar que o id existe.
    """
    stmt = select(Run).where(Run.id == run_id, Run.user_id == user.id)
    if with_artifacts:
        stmt = stmt.options(selectinload(Run.artifacts))
    run = (await session.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
async def create_run(payload: RunCreate, session: SessionDep, user: CurrentUserDep):
    """Cria um run do usuário logado (nasce com status `created`)."""
    run = Run(user_id=user.id, **payload.model_dump())
    session.add(run)
    await session.commit()  # explícito: um erro aqui precisa chegar ao cliente
    return run


@router.get("", response_model=RunList)
async def list_runs(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    algorithm: str | None = None,
    status_filter: Annotated[RunStatus | None, Query(alias="status")] = None,
):
    """Lista os runs do usuário, do mais novo ao mais antigo, com paginação."""
    stmt = select(Run).where(Run.user_id == user.id)
    if algorithm is not None:
        stmt = stmt.where(Run.algorithm == algorithm)
    if status_filter is not None:
        stmt = stmt.where(Run.status == status_filter)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    page = stmt.order_by(Run.created_at.desc(), Run.id.desc())
    items = (await session.scalars(page.limit(limit).offset(offset))).all()
    return RunList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    """Detalhe de um run, com a lista dos seus artifacts."""
    return await get_owned_run(session, run_id, user, with_artifacts=True)


@router.patch("/{run_id}", response_model=RunRead)
async def update_run(
    run_id: int, payload: RunUpdate, session: SessionDep, user: CurrentUserDep
):
    """Edita um run parcialmente: só os campos enviados mudam.

    O `status` não é editável pelo cliente (quem o define é o worker).
    """
    run = await get_owned_run(session, run_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(run, field, value)
    await session.commit()
    await session.refresh(run)  # recarrega o updated_at, calculado pelo banco
    return run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: int, session: SessionDep, user: CurrentUserDep):
    """Apaga o run; o banco apaga os artifacts (ON DELETE CASCADE).

    TODO: apagar também os objetos do S3 e registrar a ação no log de auditoria.
    """
    run = await get_owned_run(session, run_id, user)
    await session.delete(run)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
