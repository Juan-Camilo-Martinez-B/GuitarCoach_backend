"""Configuración tipada. Los secretos llegan por el entorno, nunca por el código."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me"
PRODUCTION_ENVIRONMENT = "production"


class Settings(BaseSettings):
    """Parámetros de proceso. Los valores por defecto solo sirven en local."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GuitarCoach AI"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://guitarcoach:guitarcoach@localhost:54329/guitarcoach"
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:5173"]
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    daily_report_limit: int = 5
    scrape_min_interval_seconds: float = 1.0
    scrape_max_concurrency: int = 2
    auth_requests_per_minute: int = 20
    hit_window_ms: int = 150

    def ensure_production_secrets(self) -> None:
        """Impide arrancar en producción con el secreto de desarrollo."""
        if self.environment == PRODUCTION_ENVIRONMENT and self.jwt_secret == DEV_JWT_SECRET:
            raise RuntimeError("JWT_SECRET debe definirse fuera del código en producción.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
