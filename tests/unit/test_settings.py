"""La configuración no acepta el secreto de desarrollo cuando el entorno es producción."""

import pytest
from app.core.config import DEV_JWT_SECRET, Settings


def test_produccion_exige_un_secreto_propio() -> None:
    settings = Settings(environment="production", jwt_secret=DEV_JWT_SECRET)
    with pytest.raises(RuntimeError):
        settings.ensure_production_secrets()


def test_local_puede_usar_el_secreto_de_desarrollo() -> None:
    settings = Settings(environment="local", jwt_secret=DEV_JWT_SECRET)
    settings.ensure_production_secrets()
