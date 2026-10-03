"""Formato da resposta do login: o token e o tipo (sempre "bearer")."""

from pydantic import BaseModel


class Token(BaseModel):
    """Resposta do login: o JWT e o tipo do token."""

    access_token: str
    token_type: str
