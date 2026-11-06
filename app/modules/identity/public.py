"""Lo que el resto de la aplicación puede usar de la identidad."""

from app.modules.identity.application.guard import bearer_user_id

__all__ = ["bearer_user_id"]
