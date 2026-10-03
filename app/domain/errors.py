"""Errores de dominio. La API los traduce a HTTP; el dominio no conoce FastAPI."""


class DomainError(Exception):
    """Fallo de una regla de negocio, con un código estable para el cliente."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class InvalidValueError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_value")


class AuthenticationError(DomainError):
    def __init__(self, message: str = "Credenciales inválidas.") -> None:
        super().__init__(message, code="authentication_failed")


class NotFoundError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found")


class ConflictError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict")


class RateLimitExceededError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="rate_limited")


class ExternalServiceError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="external_service")
