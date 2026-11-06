"""Lo que todo almacén de un módulo sabe hacer: cerrar o deshacer la transacción."""

from typing import Protocol


class Transactional(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
