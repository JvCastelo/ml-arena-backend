from fastapi import APIRouter, Request, status, Depends, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_session
from app.db.models import User
from app.schemas.user import UserCreate, UserResponse
from app.services import auth_service, audit_service

router = APIRouter()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
):
    user_created = await auth_service.register_user(db, user_in)

    background_tasks.add_task(
        audit_service.log_user_action,
        user_id=user_created.id,
        action="CREATE_USER",
        ip_address=request.client.host if request.client else None,
        details=user_in.model_dump(mode="json"),
    )
    return user_created


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
