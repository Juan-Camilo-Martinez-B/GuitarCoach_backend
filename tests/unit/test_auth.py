"""Registro e inicio de sesión, sin base de datos."""

from app.bootstrap.unit_of_work import InMemoryUnitOfWork
from app.main import create_app
from app.modules.identity.application.auth import LoginUser, RegisterUser
from app.modules.identity.application.security import ArgonPasswordHasher, JwtTokenIssuer
from app.shared.clock import SystemClock
from app.shared.config import Settings
from fastapi.testclient import TestClient


async def test_registra_e_inicia_sesion() -> None:
    uow = InMemoryUnitOfWork()
    hasher = ArgonPasswordHasher()
    clock = SystemClock()
    user = await RegisterUser(uow.users, hasher, clock).execute(
        "Ana@example.com",
        "secreto-largo",
        "Ana",
    )
    assert user.email == "ana@example.com"
    token = await LoginUser(
        uow.users,
        hasher,
        JwtTokenIssuer("secreto-de-prueba-con-longitud-suficiente", "HS256", 30, clock),
    ).execute("ana@example.com", "secreto-largo")
    issuer = JwtTokenIssuer("secreto-de-prueba-con-longitud-suficiente", "HS256", 30, clock)
    assert issuer.read_user_id(token) == user.id


def test_el_endpoint_de_registro_y_login_devuelve_un_token() -> None:
    client = TestClient(
        create_app(
            Settings(environment="local", jwt_secret="secreto-de-prueba-con-longitud-suficiente")
        )
    )
    created = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "secreto-largo", "display_name": "Ana"},
    )
    assert created.status_code == 201
    logged = client.post(
        "/auth/login",
        json={"email": "ana@example.com", "password": "secreto-largo"},
    )
    assert logged.status_code == 200
    assert logged.json()["token_type"] == "bearer"
    duplicate = client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "secreto-largo", "display_name": "Ana"},
    )
    assert duplicate.status_code == 409
