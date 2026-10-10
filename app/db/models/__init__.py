"""Modelos SQLAlchemy do banco (o schema). Importar daqui registra todas as tabelas
em `Base.metadata`, que é o que o Alembic e os testes usam.
"""

from app.db.models.artifact import Artifact
from app.db.models.base import Base
from app.db.models.run import Run
from app.db.models.user import User

__all__ = ["Artifact", "Base", "Run", "User"]
