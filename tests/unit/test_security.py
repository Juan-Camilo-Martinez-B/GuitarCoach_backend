"""Las respuestas llevan cabeceras de seguridad y un origen CORS concreto."""

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_incluye_cabeceras_y_el_origen_local() -> None:
    client = TestClient(create_app(Settings(environment="local")))
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_un_origen_comodin_impide_arrancar() -> None:
    with pytest.raises(RuntimeError):
        create_app(Settings(environment="local", cors_origins=["*"]))


def test_el_editor_de_guias_puede_enviar_put_desde_el_origen_local() -> None:
    client = TestClient(create_app(Settings(environment="local")))
    response = client.options(
        "/guides/00000000-0000-0000-0000-000000000000",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
