"""Registro e inicio de sesión."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import current_uow
from app.application.security import (
    ArgonPasswordHasher,
    JwtTokenIssuer,
    SystemClock,
)
from app.application.use_cases.auth import LoginUser, RegisterUser
from app.core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)


class LoginBody(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise RuntimeError("La configuración no está disponible.")
    return settings


@router.post("/register", status_code=201)
async def register(body: RegisterBody, request: Request) -> UserResponse:
    uow = current_uow(request)
    user = await RegisterUser(uow.users, ArgonPasswordHasher(), SystemClock()).execute(
        body.email,
        body.password,
        body.display_name,
    )
    await uow.commit()
    return UserResponse(id=str(user.id), email=user.email, display_name=user.display_name)


@router.post("/login")
async def login(body: LoginBody, request: Request) -> TokenResponse:
    settings = _settings(request)
    uow = current_uow(request)
    clock = SystemClock()
    issuer = JwtTokenIssuer(
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.jwt_ttl_minutes,
        clock,
    )
    token = await LoginUser(uow.users, ArgonPasswordHasher(), issuer).execute(
        body.email,
        body.password,
    )
    return TokenResponse(access_token=token)
