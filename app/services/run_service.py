from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import run_repository
from app.schemas.run import RunCreate, RunUpdate
from app.db.models import Run


async def get_owned_run_or_404(
    session: AsyncSession, run_id: int, user_id: int, with_artifacts: bool = False
) -> Run:
    run = await run_repository.get_run_by_id_and_user(
        session, run_id, user_id, with_artifacts
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


async def create_run(session: AsyncSession, user_id: int, payload: RunCreate) -> Run:
    return await run_repository.create_run(session, user_id, payload.model_dump())


async def update_run(
    session: AsyncSession, run_id: int, user_id: int, payload: RunUpdate
) -> Run:
    run = await get_owned_run_or_404(session, run_id, user_id)
    update_data = payload.model_dump(exclude_unset=True)
    return await run_repository.update_run(session, run, update_data)


async def delete_run(session: AsyncSession, run_id: int, user_id: int) -> Run:
    run = await get_owned_run_or_404(session, run_id, user_id)
    await run_repository.delete_run(session, run)
    return run
