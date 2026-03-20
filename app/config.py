import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "cognitive_service"

    POSTGRES_HOST: str = os.getenv('COGNITIVE_DB_HOST', os.getenv('AUTH_DB_HOST', 'db'))
    POSTGRES_PORT: int = int(os.getenv('COGNITIVE_DB_PORT', os.getenv('AUTH_DB_PORT', '5432')))
    POSTGRES_USER: str = os.getenv('COGNITIVE_DB_USER', os.getenv('AUTH_DB_USER', 'doadmin'))
    POSTGRES_PASSWORD: str = os.getenv('COGNITIVE_DB_PASSWORD', os.getenv('AUTH_DB_PASSWORD', ''))
    POSTGRES_DB: str = os.getenv('COGNITIVE_DB_NAME', os.getenv('AUTH_DB_NAME', 'defaultdb'))

    class Config:
        env_file = ".env"
        env_prefix = "COG_"
        case_sensitive = False


settings = Settings()

DATABASE_URL = (
    os.getenv("COGNITIVE_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}?ssl=require"
    )
)
