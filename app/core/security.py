"""Segurança: hash de senha (bcrypt) e criação de token JWT.

Usado por `app/services/auth_service.py` (cadastro e login). A validação do
token recebido fica em `app/api/deps.py`, que usa a mesma `SECRET_KEY`.
"""

from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Contexto do bcrypt. O passlib guarda o salt e o custo dentro do próprio hash.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Confere se a senha digitada bate com o hash guardado (refaz a conta com o mesmo salt)."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Gera o hash bcrypt de uma senha nova. Nunca guardamos a senha em texto puro."""
    return pwd_context.hash(password)


def create_access_token(subject: str | any) -> str:
    """Cria o Token JWT guardando o email (ou ID) do usuário."""
    # `exp` é a validade: depois desse horário o token é recusado na validação.
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    # `sub` (subject) é de quem é o token. Aqui é o e-mail do usuário.
    to_encode = {"exp": expire, "sub": str(subject)}

    # A assinatura (HMAC com a SECRET_KEY) é o que impede alguém de forjar ou alterar o token.
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )

    return encoded_jwt
