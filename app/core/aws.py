import aioboto3
from app.core.config import settings

aws_session = aioboto3.Session(
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    aws_session_token=settings.aws_session_token,
    region_name=settings.aws_region,
)
