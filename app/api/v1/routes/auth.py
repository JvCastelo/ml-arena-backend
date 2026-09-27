from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.token import Token
from app.services import auth_service

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(get_session),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    return await auth_service.authenticate_user(
        db, form_data.username, form_data.password
    )
