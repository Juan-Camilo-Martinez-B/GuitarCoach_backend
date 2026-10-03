"""El manejador global no filtra excepciones de dominio como 500."""

from app.api.middleware.errors import register_exception_handlers
from app.domain.errors import NotFoundError
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_not_found_responde_404_con_codigo_estable() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing")
    def missing() -> None:
        raise NotFoundError("No está.")

    response = TestClient(app).get("/missing")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "No está."}
