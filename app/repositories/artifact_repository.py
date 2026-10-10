"""Acesso ao banco para artifacts (CSV e plots): criar, atualizar, buscar e listar.

Só faz SQL e commit. As regras (409, reenvio, status) ficam em `run_service.py` e `worker/consumer.py`.
"""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact


async def get_artifact_by_type(
    session: AsyncSession, run_id: int, type_: str
) -> Artifact | None:
    """Busca o artifact de um tipo dentro do run (ex.: o CSV). Retorna None se não existir."""
    stmt = select(Artifact).where(Artifact.run_id == run_id, Artifact.type == type_)
    return (await session.execute(stmt)).scalar_one_or_none()


async def claim_failed_artifact(session: AsyncSession, artifact: Artifact) -> bool:
    """Volta um artifact de failed pra pending. Só uma tentativa concorrente consegue (WHERE atômico)."""
    stmt = (
        update(Artifact)
        .where(Artifact.id == artifact.id, Artifact.status == "failed")
        .values(status="pending", error_message=None, size_bytes=None)
    )
    result = await session.execute(stmt)
    await session.commit()
    if result.rowcount != 1:
        return False
    await session.refresh(artifact)
    return True


async def create_artifact(
    session: AsyncSession, run_id: int, type_: str, s3_key: str, status: str
) -> Artifact:
    """Cria o artifact e comita. Se já existir um do mesmo tipo no run, levanta IntegrityError."""
    artifact = Artifact(run_id=run_id, type=type_, s3_key=s3_key, status=status)
    session.add(artifact)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(artifact)
    return artifact


async def update_artifact(
    session: AsyncSession, artifact: Artifact, **fields
) -> Artifact:
    """Atualiza campos do artifact (status, size_bytes, error_message) e comita."""
    for field, value in fields.items():
        setattr(artifact, field, value)
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def list_artifacts_for_run(session: AsyncSession, run_id: int) -> list[Artifact]:
    """Lista todos os artifacts de um run."""
    stmt = select(Artifact).where(Artifact.run_id == run_id)
    return list((await session.scalars(stmt)).all())
