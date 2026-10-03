"""Cada evento de log es una línea JSON."""

import io
import json
import logging

from app.core.logging import configure_logging


def test_el_log_es_json_con_nivel_y_mensaje() -> None:
    stream = io.StringIO()
    configure_logging("INFO", stream)
    logging.getLogger("guitarcoach.test").info("afinador listo")
    payload = json.loads(stream.getvalue())
    assert payload["level"] == "INFO"
    assert payload["message"] == "afinador listo"
    assert payload["logger"] == "guitarcoach.test"
