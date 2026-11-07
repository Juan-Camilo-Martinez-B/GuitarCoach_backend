"""La guía es privada, no se duplica y deja una canción para practicar."""

import json

from app.main import create_app
from app.modules.guides.domain.guide_import import guide_from_text
from app.shared.config import Settings
from fastapi.testclient import TestClient

GP5 = b"\x18FICHIER GUITAR PRO v5.00" + b"\x00" * 64
# La guía que arma el navegador al leer la tablatura: secciones, acordes y golpes.
DOCUMENT = guide_from_text(
    "[Intro]\nG D Em C\n[Coro]\nAm D7",
    "x",
    title="Mi canción",
    artist="Ana",
    bpm=96,
    strum="D-DU-UDU",
).as_dict()


def _token(client: TestClient, email: str) -> dict[str, str]:
    body = {"email": email, "password": "secreto-largo", "display_name": "Ana"}
    assert client.post("/auth/register", json=body).status_code == 201
    token = client.post("/auth/login", json=body).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _client() -> TestClient:
    return TestClient(create_app(Settings(environment="local", auth_requests_per_minute=100)))


def _upload(client: TestClient, headers: dict[str, str], document: str | None = None):
    return client.post(
        "/guides/from-tab",
        data={"guide": document or json.dumps(DOCUMENT)},
        files={"file": ("riff.gp5", GP5, "application/octet-stream")},
        headers=headers,
    )


def test_subir_dos_veces_la_misma_tablatura_devuelve_la_misma_guia() -> None:
    with _client() as client:
        headers = _token(client, "repetir@example.com")
        first = _upload(client, headers)
        second = _upload(client, headers)
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        body = first.json()
        assert body["status"] == "borrador"
        assert [section["name"] for section in body["guide"]["sections"]] == ["Intro", "Coro"]
        assert "lyrics" not in body["guide"]


def test_los_flujos_de_texto_y_audio_ya_no_existen() -> None:
    with _client() as client:
        headers = _token(client, "viejos@example.com")
        files = {"file": ("vals.cho", b"[Am] [E7]", "text/plain")}
        gone = {404, 405}
        assert client.post("/guides/paste", json={}, headers=headers).status_code in gone
        assert client.post("/guides/upload", files=files, headers=headers).status_code in gone
        assert client.post("/guides/from-audio", files=files, headers=headers).status_code in gone


def test_otro_usuario_no_ve_ni_corrige_la_guia() -> None:
    with _client() as client:
        owner = _token(client, "duena@example.com")
        intruder = _token(client, "otro@example.com")
        guide_id = _upload(client, owner).json()["id"]
        assert client.get(f"/guides/{guide_id}", headers=intruder).status_code == 404
        assert client.get("/guides", headers=intruder).json() == []
        document = client.get(f"/guides/{guide_id}", headers=owner).json()["guide"]
        update = {"status": "revisada", "guide": document}
        assert client.put(f"/guides/{guide_id}", json=update, headers=intruder).status_code == 404


def test_corregir_la_guia_la_marca_revisada_y_cambia_la_cancion() -> None:
    with _client() as client:
        headers = _token(client, "editar@example.com")
        created = _upload(client, headers).json()
        document = created["guide"]
        document["chords"][0]["chord"] = "Cadd9"
        document["bpm"] = 80
        response = client.put(
            f"/guides/{created['id']}",
            json={"status": "revisada", "guide": document},
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "revisada"
        assert body["guide"]["chords"][0]["chord"] == "Cadd9"
        assert body["song_id"] != created["song_id"]
        study = client.get(f"/songs/{body['song_id']}/study").json()
        assert study["chords"][0]["symbol"] == "Cadd9"


def test_la_guia_no_acepta_letra_ni_acordes_inventados() -> None:
    with _client() as client:
        headers = _token(client, "validar@example.com")
        created = _upload(client, headers).json()
        document = created["guide"]
        document["chords"][0]["chord"] = "H7"
        response = client.put(
            f"/guides/{created['id']}",
            json={"status": "revisada", "guide": document},
            headers=headers,
        )
        assert response.status_code == 422


def test_el_dueno_borra_la_guia_y_su_archivo_y_otro_no_puede() -> None:
    with _client() as client:
        owner = _token(client, "borra-guia@example.com")
        intruder = _token(client, "intruso-guia@example.com")
        guide_id = _upload(client, owner).json()["id"]
        assert client.delete(f"/guides/{guide_id}", headers=intruder).status_code == 404
        assert client.get(f"/guides/{guide_id}/tab", headers=owner).status_code == 200
        assert client.delete(f"/guides/{guide_id}", headers=owner).status_code == 204
        assert client.get(f"/guides/{guide_id}", headers=owner).status_code == 404
        assert client.get(f"/guides/{guide_id}/tab", headers=owner).status_code == 404
        assert client.get("/guides", headers=owner).json() == []


def test_la_cancion_de_la_guia_no_sale_en_la_busqueda_publica() -> None:
    with _client() as client:
        headers = _token(client, "privada@example.com")
        _upload(client, headers)
        found = client.get("/songs", params={"q": "Mi canción"}).json()
        assert found == []


def _tab_document() -> str:
    document = json.loads(json.dumps(DOCUMENT))
    document["title"] = "Riff"
    document["melody"] = [{"start": 0, "beats": 1, "midi": 64}]
    return json.dumps(document)


def test_la_tablatura_crea_la_guia_y_guarda_el_archivo() -> None:
    with _client() as client:
        headers = _token(client, "tab@example.com")
        intruder = _token(client, "tab-otro@example.com")
        document = _tab_document()
        files = {"file": ("riff.gp5", GP5, "application/octet-stream")}
        created = client.post(
            "/guides/from-tab", data={"guide": document}, files=files, headers=headers
        )
        assert created.status_code == 201
        body = created.json()
        assert body["source_kind"] == "tablatura"
        assert body["guide"]["melody"][0]["midi"] == 64
        again = client.post(
            "/guides/from-tab", data={"guide": document}, files=files, headers=headers
        )
        assert again.status_code == 200
        assert again.json()["id"] == body["id"]
        tab = client.get(f"/guides/{body['id']}/tab", headers=headers)
        assert tab.status_code == 200
        assert tab.content == GP5
        assert tab.headers["x-tab-format"] == "gp345"
        assert client.get(f"/guides/{body['id']}/tab", headers=intruder).status_code == 404


def test_la_tablatura_se_reconoce_por_su_contenido() -> None:
    with _client() as client:
        headers = _token(client, "tab-falsa@example.com")
        document = _tab_document()
        fake = {"file": ("riff.gp5", b"%PDF-1.7 no es una tablatura", "application/pdf")}
        rejected = client.post(
            "/guides/from-tab", data={"guide": document}, files=fake, headers=headers
        )
        assert rejected.status_code in {400, 422}
        broken = client.post(
            "/guides/from-tab",
            data={"guide": '{"title": "sin secciones"}'},
            files={"file": ("riff.gp5", GP5, "application/octet-stream")},
            headers=headers,
        )
        assert broken.status_code in {400, 422}


def test_la_tablatura_se_pide_por_un_id_valido() -> None:
    with _client() as client:
        headers = _token(client, "sin-tab@example.com")
        guide_id = _upload(client, headers).json()["id"]
        assert client.get(f"/guides/{guide_id}/tab", headers=headers).status_code == 200
        assert client.get("/guides/no-es-un-id/tab", headers=headers).status_code == 422
