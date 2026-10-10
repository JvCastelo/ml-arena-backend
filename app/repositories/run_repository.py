"""Acesso ao banco para runs: consultas, criação, edição e remoção.

Só faz SQL e commit. As regras (dono, 404, status) ficam em `app/services/run_service.py`.
Quem chama: `run_service.py`.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Run


async def get_run_by_id_and_user(
    session: AsyncSession, run_id: int, user_id: int, with_artifacts: bool = False
) -> Run | None:
    """Busca um run pelo id, só se for do usuário. Retorna None se não existir ou não for dele."""
    stmt = select(Run).where(Run.id == run_id, Run.user_id == user_id)
    if with_artifacts:
        stmt = stmt.options(selectinload(Run.artifacts))
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_run(session: AsyncSession, user_id: int, run_data: dict) -> Run:
    """Insere um run do usuário e comita."""
    run = Run(user_id=user_id, **run_data)
    session.add(run)
    await session.commit()
    return run


async def get_runs_paginated(
    session: AsyncSession,
    user_id: int,
    limit: int,
    offset: int,
    algorithm: str | None,
    status_filter: str | None,
):
    """Lista os runs do usuário (mais novos primeiro), com filtros opcionais. Retorna a página e o total."""
    stmt = select(Run).where(Run.user_id == user_id)
    if algorithm:
        stmt = stmt.where(Run.algorithm == algorithm)
    if status_filter:
        stmt = stmt.where(Run.status == status_filter)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    page = stmt.order_by(Run.created_at.desc(), Run.id.desc())
    items = (await session.scalars(page.limit(limit).offset(offset))).all()

    return items, total


async def update_run(session: AsyncSession, run: Run, update_data: dict) -> Run:
    """Aplica os campos enviados no run e comita. Dicts (hyperparams, metrics) são mesclados, não substituídos."""
    for field, value in update_data.items():
        if isinstance(value, dict):
            current_value = getattr(run, field) or {}

            merged_value = {**current_value, **value}

            setattr(run, field, merged_value)
        else:
            setattr(run, field, value)
    await session.commit()
    await session.refresh(run)
    return run


async def delete_run(session: AsyncSession, run: Run) -> None:
    """Apaga o run e comita. Os artifacts vão junto pelo cascade do banco."""
    await session.delete(run)
    await session.commit()
