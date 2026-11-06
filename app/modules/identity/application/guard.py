"""Quién hace la petición. Los demás módulos solo necesitan saber esto de la identidad."""

from uuid import UUID

from app.modules.identity.application.security import JwtTokenIssuer
from app.shared.clock import SystemClock
from app.shared.config import Settings
from app.shared.errors import AuthenticationError


def bearer_user_id(authorization: str, settings: Settings) -> UUID:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Falta el token.")
    issuer = JwtTokenIssuer(
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.jwt_ttl_minutes,
        SystemClock(),
    )
    return issuer.read_user_id(token)
