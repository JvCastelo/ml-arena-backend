"""Formatos JSON de entrada e saída de usuário (Pydantic).

Diferente do model do banco: `UserCreate` recebe a senha em texto (só na entrada) e
`UserResponse` nunca devolve o hash.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    """Corpo do cadastro: nome, e-mail e senha em texto (só na entrada; a senha vira hash antes de ir ao banco)."""

    name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Dados públicos do usuário na resposta. Nunca inclui a senha nem o hash."""

    id: int
    name: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
