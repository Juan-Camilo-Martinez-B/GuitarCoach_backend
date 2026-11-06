"""Configuración tipada. Los secretos llegan por el entorno, nunca por el código."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Es público porque está en el repositorio: solo sirve para arrancar en local sin configurar.
DEV_JWT_SECRET = "dev-only-change-me-public-value-not-for-real-use"
PRODUCTION_ENVIRONMENT = "production"
# HS256 firma con 256 bits: una clave más corta que eso debilita la firma.
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Parámetros de proceso. Los valores por defecto solo sirven en local."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GuitarCoach AI"
    environment: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://guitarcoach:guitarcoach@localhost:54329/guitarcoach"
    use_database: bool = False
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 720
    cors_origins: list[str] = ["http://localhost:5173"]
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    daily_report_limit: int = 5
    scrape_min_interval_seconds: float = 1.0
    scrape_max_concurrency: int = 2
    auth_requests_per_minute: int = 20
    hit_window_ms: int = 150
    redis_url: str = ""

    def ensure_production_secrets(self) -> None:
        """Impide arrancar en producción con el secreto de desarrollo o con uno corto."""
        if self.environment.strip().lower() != PRODUCTION_ENVIRONMENT:
            return
        if self.jwt_secret == DEV_JWT_SECRET:
            raise RuntimeError("JWT_SECRET debe definirse fuera del código en producción.")
        if len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH:
            raise RuntimeError(
                f"JWT_SECRET debe tener al menos {MIN_JWT_SECRET_LENGTH} caracteres en producción."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
