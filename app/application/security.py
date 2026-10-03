"""Hash de contraseñas y JWT. El dominio no conoce estos algoritmos."""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.domain.errors import AuthenticationError

MIN_PASSWORD_LENGTH = 8


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: UUID) -> str: ...

    def read_user_id(self, token: str) -> UUID: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class ArgonPasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._hasher.verify(password, password_hash)


class JwtTokenIssuer:
    def __init__(self, secret: str, algorithm: str, ttl_minutes: int, clock: Clock) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._ttl_minutes = ttl_minutes
        self._clock = clock

    def issue(self, user_id: UUID) -> str:
        expires = self._clock.now() + timedelta(minutes=self._ttl_minutes)
        token = jwt.encode(
            {"sub": str(user_id), "exp": expires},
            self._secret,
            algorithm=self._algorithm,
        )
        return token if isinstance(token, str) else token.decode("ascii")

    def read_user_id(self, token: str) -> UUID:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError as error:
            raise AuthenticationError("El token no es válido.") from error
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise AuthenticationError("El token no identifica a un usuario.")
        return UUID(subject)
