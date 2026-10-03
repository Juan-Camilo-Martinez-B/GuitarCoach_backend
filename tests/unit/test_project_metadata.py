"""El paquete declara el runtime y las herramientas de calidad."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_pyproject_exige_python_312_y_las_herramientas() -> None:
    project_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
    document = tomllib.loads(project_file.read_text(encoding="utf-8"))
    project = document["project"]
    assert project["requires-python"] == ">=3.12"
    assert "fastapi" in "".join(project["dependencies"])
    dev = project["optional-dependencies"]["dev"]
    assert any(item.startswith("mypy") for item in dev)
    assert any(item.startswith("ruff") for item in dev)
    assert any(item.startswith("pytest") for item in dev)
    assert document["tool"]["mypy"]["strict"] is True
