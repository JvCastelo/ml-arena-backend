from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    return result.scalars().first()


async def create_user(
    session: AsyncSession, name: str, email: str, password_hash: str
) -> User:
    db_user = User(name=name, email=email, password_hash=password_hash)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user
