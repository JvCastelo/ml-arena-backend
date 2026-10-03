from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password, create_access_token
from app.repositories import user_repository
from app.schemas.user import UserCreate


async def register_user(session: AsyncSession, user_in: UserCreate):
    existing_user = await user_repository.get_user_by_email(session, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Este email já está em uso."
        )

    hashed_pwd = get_password_hash(user_in.password)
    return await user_repository.create_user(
        session, user_in.name, user_in.email, hashed_pwd
    )


async def authenticate_user(session: AsyncSession, email: str, password: str) -> dict:
    user = await user_repository.get_user_by_email(session, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email ou senha incorretos"
        )

    return {
        "access_token": create_access_token(subject=user.email),
        "token_type": "bearer",
        "user_id": user.id,
    }
