"""Base declarativa de todos os modelos, com a convenção de nomes das constraints.

A `NAMING_CONVENTION` faz o Postgres criar nomes previsíveis (pk_, fk_, uq_, ck_),
para o Alembic conseguir alterar ou remover constraints depois.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Classe base de todos os modelos. Herda o mapeamento do SQLAlchemy e usa a NAMING_CONVENTION."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
