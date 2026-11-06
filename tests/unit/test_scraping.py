"""Cola local, adaptador de fixture, robots y caché de canciones."""

from pathlib import Path

import pytest
from app.bootstrap.unit_of_work import InMemoryUnitOfWork
from app.modules.catalog.application.import_song import ImportSong
from app.modules.catalog.application.scraping.rate_limiter import DomainRateLimiter
from app.modules.catalog.application.scraping.registry import ScraperRegistry
from app.modules.catalog.application.scraping.robots import is_allowed
from app.modules.catalog.infrastructure.scraping.open_fixture import OpenFixtureScraper
from app.shared.clock import SystemClock
from app.shared.tasks.local_dispatcher import LocalTaskDispatcher

HTML = (Path(__file__).resolve().parents[1] / "fixtures" / "open_chart.html").read_text(
    encoding="utf-8"
)
SOURCE = "https://example.com/charts/progresion"
ROBOTS = "User-agent: *\nAllow: /\n"


async def test_el_dispatcher_marca_el_trabajo_al_terminar() -> None:
    dispatcher = LocalTaskDispatcher()

    async def handler(payload: dict[str, str]) -> None:
        assert payload["job_id"]

    dispatcher.register("import_song", handler)
    job_id = dispatcher.enqueue("import_song", {"job_id": "1"})
    await dispatcher.join(job_id)
    state = dispatcher.get(job_id)
    assert state is not None
    assert state.status == "done"


def test_el_fixture_normaliza_el_titulo_y_los_acordes() -> None:
    chart = OpenFixtureScraper(HTML, SOURCE).collect("progresion")
    assert chart.title == "Progresión abierta"
    assert [chord.chord.symbol for chord in chart.chords] == ["C", "G", "Am", "F"]


def test_robots_puede_bloquear_una_ruta() -> None:
    blocked = "User-agent: *\nDisallow: /privado\n"
    assert is_allowed(blocked, "https://example.com/publico")
    assert not is_allowed(blocked, "https://example.com/privado/chart")


async def test_importar_dos_veces_reutiliza_la_cancion() -> None:
    uow = InMemoryUnitOfWork()
    registry = ScraperRegistry()
    registry.register("open-fixture", OpenFixtureScraper(HTML, SOURCE))
    importer = ImportSong(
        uow,
        registry,
        DomainRateLimiter(0, 2),
        SystemClock(),
        "open-fixture",
        ROBOTS,
    )
    first = await importer.start(None, "progresion")
    await importer.run(first.id)
    second = await importer.start(None, "progresion")
    await importer.run(second.id)
    stored_first = await uow.jobs.get(first.id)
    stored_second = await uow.jobs.get(second.id)
    assert stored_first is not None and stored_second is not None
    assert stored_first.song_id == stored_second.song_id
    assert len(await uow.songs.search("Progresión")) == 1


def test_un_registro_vacio_no_inventa_adaptadores() -> None:
    with pytest.raises(KeyError):
        ScraperRegistry().get("no-existe")
