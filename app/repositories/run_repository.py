from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.models import Run


async def get_run_by_id_and_user(
    session: AsyncSession, run_id: int, user_id: int, with_artifacts: bool = False
) -> Run | None:
    stmt = select(Run).where(Run.id == run_id, Run.user_id == user_id)
    if with_artifacts:
        stmt = stmt.options(selectinload(Run.artifacts))
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_run(session: AsyncSession, user_id: int, run_data: dict) -> Run:
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
    await session.delete(run)
    await session.commit()
