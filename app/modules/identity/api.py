"""Registro e inicio de sesión."""

from typing import cast

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.modules.identity.application.auth import LoginUser, RegisterUser
from app.modules.identity.application.security import ArgonPasswordHasher, JwtTokenIssuer
from app.modules.identity.ports import IdentityStore
from app.shared.clock import SystemClock
from app.shared.http.deps import current_settings, current_uow

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


def _store(request: Request) -> IdentityStore:
    return cast(IdentityStore, current_uow(request))


@router.post("/register", status_code=201)
async def register(body: RegisterBody, request: Request) -> UserResponse:
    uow = _store(request)
    user = await RegisterUser(uow.users, ArgonPasswordHasher(), SystemClock()).execute(
        body.email,
        body.password,
        body.display_name,
    )
    await uow.commit()
    return UserResponse(id=str(user.id), email=user.email, display_name=user.display_name)


@router.post("/login")
async def login(body: LoginBody, request: Request) -> TokenResponse:
    settings = current_settings(request)
    uow = _store(request)
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
