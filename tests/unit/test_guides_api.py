"""La guía es privada, no se duplica y deja una canción para practicar."""

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

PASTED = {
    "title": "Mi canción",
    "artist": "Ana",
    "text": "[Intro]\nG D Em C\n[Coro]\nAm D7\nletra que no se guarda",
    "bpm": 96,
    "strum": "D-DU-UDU",
}


def _token(client: TestClient, email: str) -> dict[str, str]:
    body = {"email": email, "password": "secreto-largo", "display_name": "Ana"}
    assert client.post("/auth/register", json=body).status_code == 201
    token = client.post("/auth/login", json=body).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _client() -> TestClient:
    return TestClient(create_app(Settings(environment="local", auth_requests_per_minute=100)))


def test_pegar_dos_veces_lo_mismo_devuelve_la_misma_guia() -> None:
    with _client() as client:
        headers = _token(client, "pegar@example.com")
        first = client.post("/guides/paste", json=PASTED, headers=headers)
        second = client.post("/guides/paste", json=PASTED, headers=headers)
        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        body = first.json()
        assert body["status"] == "borrador"
        assert [section["name"] for section in body["guide"]["sections"]] == ["Intro", "Coro"]
        assert "lyrics" not in body["guide"]
        assert "letra" not in str(body["guide"])


def test_otro_usuario_no_ve_ni_corrige_la_guia() -> None:
    with _client() as client:
        owner = _token(client, "duena@example.com")
        intruder = _token(client, "otro@example.com")
        guide_id = client.post("/guides/paste", json=PASTED, headers=owner).json()["id"]
        assert client.get(f"/guides/{guide_id}", headers=intruder).status_code == 404
        assert client.get("/guides", headers=intruder).json() == []
        document = client.get(f"/guides/{guide_id}", headers=owner).json()["guide"]
        update = {"status": "revisada", "guide": document}
        assert client.put(f"/guides/{guide_id}", json=update, headers=intruder).status_code == 404


def test_corregir_la_guia_la_marca_revisada_y_cambia_la_cancion() -> None:
    with _client() as client:
        headers = _token(client, "editar@example.com")
        created = client.post("/guides/paste", json=PASTED, headers=headers).json()
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
        created = client.post("/guides/paste", json=PASTED, headers=headers).json()
        document = created["guide"]
        document["chords"][0]["chord"] = "H7"
        response = client.put(
            f"/guides/{created['id']}",
            json={"status": "revisada", "guide": document},
            headers=headers,
        )
        assert response.status_code == 422


def test_la_cancion_de_la_guia_no_sale_en_la_busqueda_publica() -> None:
    with _client() as client:
        headers = _token(client, "privada@example.com")
        client.post("/guides/paste", json=PASTED, headers=headers)
        found = client.get("/songs", params={"q": "Mi canción"}).json()
        assert found == []


def test_subir_un_archivo_crea_la_guia_y_pide_sesion() -> None:
    with _client() as client:
        files = {"file": ("vals.cho", b"{title: Vals}\n{time: 3/4}\n[Am] [E7]", "text/plain")}
        assert client.post("/guides/upload", files=files).status_code == 422
        headers = _token(client, "subir@example.com")
        response = client.post("/guides/upload", files=files, headers=headers)
        assert response.status_code == 201
        assert response.json()["source_kind"] == "chordpro"
        assert response.json()["guide"]["beats_per_bar"] == 3.0
