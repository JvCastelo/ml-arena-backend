import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    return Settings(
        db_host=_require("DB_HOST"),
        db_port=int(_require("DB_PORT")),
        db_user=_require("DB_USER"),
        db_password=_require("DB_PASSWORD"),
        db_name=_require("DB_NAME"),
    )


settings = load_settings()
