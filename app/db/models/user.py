"""Tabela `users`: quem se cadastra e faz login (e-mail + senha com hash bcrypt).

Usada por `app/repositories/user_repository.py`, pelo `app/api/deps.py` (identifica
o usuário do token) e pelo `run.py` (cada run aponta para o seu dono).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

if TYPE_CHECKING:
    from app.db.models.run import Run


class User(Base):
    """Usuário da plataforma. Cada run pertence a um usuário e é privado a ele."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Sem cascade: o banco recusa apagar um usuário que ainda tem runs.
    runs: Mapped[list[Run]] = relationship(back_populates="user")
