"""Las fronteras del monolito modular se comprueban aquí: una violación rompe el CI."""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
FRAMEWORKS = ("fastapi", "starlette", "sqlalchemy", "redis", "httpx", "pydantic")


def _imports(path: Path) -> Iterator[str]:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
        elif isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)


def _sources(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.py"))


def _module_of(path: Path) -> str:
    return path.relative_to(APP / "modules").parts[0]


MODULE_FILES = _sources(APP / "modules")


@pytest.mark.parametrize("path", MODULE_FILES, ids=lambda item: str(item.relative_to(APP)))
def test_un_modulo_solo_ve_a_otro_por_su_interfaz_publica(path: Path) -> None:
    if path.parent == APP / "modules":
        return
    mine = _module_of(path)
    for imported in _imports(path):
        parts = imported.split(".")
        if parts[:2] != ["app", "modules"] or parts[2] == mine:
            continue
        assert parts[3:] == ["public"], f"{path.name} importa {imported}; usa su public.py"


@pytest.mark.parametrize("path", MODULE_FILES, ids=lambda item: str(item.relative_to(APP)))
def test_un_modulo_no_depende_de_la_composicion(path: Path) -> None:
    for imported in _imports(path):
        assert not imported.startswith(("app.bootstrap", "app.main")), imported


@pytest.mark.parametrize("path", _sources(APP / "shared"), ids=lambda item: item.name)
def test_el_nucleo_compartido_no_conoce_los_modulos(path: Path) -> None:
    for imported in _imports(path):
        assert not imported.startswith(("app.modules", "app.bootstrap", "app.main")), imported


@pytest.mark.parametrize(
    "path",
    [item for item in MODULE_FILES if "domain" in item.parts],
    ids=lambda item: str(item.relative_to(APP)),
)
def test_el_dominio_no_conoce_frameworks_ni_infraestructura(path: Path) -> None:
    for imported in _imports(path):
        assert imported.split(".")[0] not in FRAMEWORKS, f"{path.name} importa {imported}"
        assert ".infrastructure" not in imported, f"{path.name} importa {imported}"
        assert ".application" not in imported, f"{path.name} importa {imported}"
        if imported.startswith("app.modules"):
            assert ".api" not in imported, f"{path.name} importa {imported}"


@pytest.mark.parametrize(
    "path",
    [item for item in MODULE_FILES if "application" in item.parts],
    ids=lambda item: str(item.relative_to(APP)),
)
def test_la_aplicacion_no_conoce_la_infraestructura(path: Path) -> None:
    for imported in _imports(path):
        assert ".infrastructure" not in imported, f"{path.name} importa {imported}"
        assert imported.split(".")[0] not in ("fastapi", "sqlalchemy"), imported


def test_las_interfaces_publicas_no_arrastran_infraestructura() -> None:
    for path in (APP / "modules").glob("*/public.py"):
        for imported in _imports(path):
            assert ".infrastructure" not in imported, f"{path} expone {imported}"
            assert ".api" not in imported, f"{path} expone {imported}"
