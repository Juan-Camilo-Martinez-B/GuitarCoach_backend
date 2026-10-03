"""Registro e inicio de sesión."""

from uuid import uuid4

from app.application.security import MIN_PASSWORD_LENGTH, Clock, PasswordHasher, TokenIssuer
from app.domain.entities.user import User
from app.domain.errors import AuthenticationError, ConflictError, InvalidValueError
from app.domain.interfaces.repositories import UserRepository


class RegisterUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, clock: Clock) -> None:
        self._users = users
        self._hasher = hasher
        self._clock = clock

    async def execute(self, email: str, password: str, display_name: str) -> User:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise InvalidValueError("La contraseña debe tener al menos 8 caracteres.")
        normalized = email.strip().lower()
        if await self._users.get_by_email(normalized) is not None:
            raise ConflictError("Ya existe una cuenta con ese correo.")
        user = User(
            id=uuid4(),
            email=normalized,
            display_name=display_name.strip(),
            level="beginner",
            password_hash=self._hasher.hash(password),
            oauth_subject=None,
            latency_offset_ms=0,
            created_at=self._clock.now(),
        )
        await self._users.add(user)
        return user


class LoginUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenIssuer) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def execute(self, email: str, password: str) -> str:
        user = await self._users.get_by_email(email.strip().lower())
        if user is None or user.password_hash is None:
            raise AuthenticationError()
        if not self._hasher.verify(password, user.password_hash):
            raise AuthenticationError()
        return self._tokens.issue(user.id)
