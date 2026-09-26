from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas das variáveis de ambiente (ou do `.env`, se existir).

    Todas são obrigatórias: faltando alguma, a aplicação não sobe.
    """

    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @computed_field
    @property
    def database_url(self) -> str:
        """Monta a URL do banco assíncrono automaticamente"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
