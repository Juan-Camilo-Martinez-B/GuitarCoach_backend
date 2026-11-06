"""La configuración no acepta el secreto de desarrollo cuando el entorno es producción."""

import pytest
from app.shared.config import DEV_JWT_SECRET, MIN_JWT_SECRET_LENGTH, Settings


def test_produccion_exige_un_secreto_propio() -> None:
    settings = Settings(environment="production", jwt_secret=DEV_JWT_SECRET)
    with pytest.raises(RuntimeError):
        settings.ensure_production_secrets()


def test_produccion_rechaza_un_secreto_corto() -> None:
    settings = Settings(environment="production", jwt_secret="x" * (MIN_JWT_SECRET_LENGTH - 1))
    with pytest.raises(RuntimeError, match="al menos"):
        settings.ensure_production_secrets()


def test_produccion_rechaza_el_secreto_de_desarrollo_anterior() -> None:
    settings = Settings(environment="production", jwt_secret="dev-only-change-me")
    with pytest.raises(RuntimeError):
        settings.ensure_production_secrets()


def test_produccion_no_depende_de_mayusculas_ni_espacios() -> None:
    settings = Settings(environment=" Production ", jwt_secret=DEV_JWT_SECRET)
    with pytest.raises(RuntimeError):
        settings.ensure_production_secrets()


def test_produccion_acepta_un_secreto_propio_largo() -> None:
    settings = Settings(environment="production", jwt_secret="x" * MIN_JWT_SECRET_LENGTH)
    settings.ensure_production_secrets()


def test_el_secreto_de_desarrollo_alcanza_la_longitud_de_la_firma() -> None:
    assert len(DEV_JWT_SECRET) >= MIN_JWT_SECRET_LENGTH


def test_local_puede_usar_el_secreto_de_desarrollo() -> None:
    settings = Settings(environment="local", jwt_secret=DEV_JWT_SECRET)
    settings.ensure_production_secrets()
