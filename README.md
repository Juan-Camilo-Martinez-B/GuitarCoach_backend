# GuitarCoach Backend

API FastAPI de GuitarCoach AI. El audio no llega a este servicio: el cliente envía telemetría.

## Cómo ejecutarlo

Requisitos: Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff format --check app tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

`GET /health` responde `{"status": "ok"}`.

El cliente envía `POST /attempts` con la telemetría ya juzgada en el navegador. `POST /attempts/{id}/report` pide el informe y `GET /me/progress` devuelve la precisión de los intentos. `POST /songs/import` responde 202 y el estado se consulta en `GET /jobs/{id}`.

```mermaid
flowchart LR
  navegador[Navegador]
  api[API FastAPI]
  db[(Postgres)]
  tutor[Gemini]
  navegador -->|telemetria REST| api
  api --> db
  api -->|texto del informe| tutor
```

## Persistencia

Con `USE_DATABASE=true` la API abre una sesión de PostgreSQL por petición y guarda usuarios, guías, intentos e informes en `DATABASE_URL`. Con `false` todo vive en memoria del proceso y se pierde al cerrarlo; así corren las pruebas unitarias. El esquema lo aplica `guitarcoach-database` (migración `0017_song_guides` para las guías).

Las pruebas de integración se omiten sin `DATABASE_URL`. Para correrlas sin tocar la base de trabajo, usa una base aparte:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://guitarcoach:guitarcoach@localhost:54329/guitarcoach_test"
.\.venv\Scripts\python.exe -m pytest tests/integration
```

## Guías de canciones

Una guía es la versión de estudio de una canción que eligió el usuario. Guarda secciones (intro, verso, coro…), acordes con su inicio y duración en pulsos, el rasgueo de cada sección, la cejilla y, si el origen la trae, la melodía con sus duraciones. **No guarda la letra**: los lectores la usan para ubicar los acordes y la descartan, y el esquema rechaza un documento con letra.

| Endpoint | Qué hace |
| --- | --- |
| `POST /guides/paste` | Recibe título, artista y el texto copiado de un cancionero (acordes sobre la letra), con tempo, compás, cejilla y rasgueo opcionales. |
| `POST /guides/upload` | Recibe ChordPro (`.cho`, `.chopro`, `.pro`, `.txt`) o MusicXML sin comprimir, de hasta 200 KB. |
| `GET /guides` | Lista las guías del usuario. |
| `GET /guides/{id}` | Devuelve la guía completa. |
| `PUT /guides/{id}` | Guarda la guía corregida en el editor y su estado (`borrador` o `revisada`). |

Reglas:

- Todos los endpoints piden el token. Una guía ajena responde 404, igual que una que no existe.
- Crear es idempotente: el mismo contenido para el mismo usuario devuelve la guía que ya existe (200 en vez de 201).
- Cada guía tiene una canción de práctica (`song_id`) para que los intentos y el informe funcionen igual que con el catálogo. Esas canciones no aparecen en la búsqueda pública.

Cómo lee el texto `app/domain/services/guide_import.py`:

- Una línea solo de acordes (`G  D  Em  C`) da un compás por acorde. Acepta nombres en español (`Lam`, `Sol/Si`) y las variantes de los cancioneros (`C7M`, `Bm7(b5)`).
- Con barras, cada tramo entre `|` es un compás; `.` prolonga el acorde un casillero y `%` repite el compás anterior. `| D7 . G . |` son dos acordes de dos pulsos.
- `x2` al final de la línea la repite.
- `[Intro]`, `Coro:` o `{start_of_chorus}` abren una sección. `Capo 2` o `{capo: 2}` fijan la cejilla, y `{time: 3/4}` el compás.
- El rasgueo se escribe en casilleros: `D-DU-UDU` son ocho corcheas en 4/4 (D abajo, U arriba, X apagado, - silencio).
- MusicXML respeta `divisions`, el compás, los tipos de acorde, las ligaduras y los silencios. Rechaza documentos con entidades.

La variante de capa gratuita usa Neon o Supabase y la API de Gemini. El detalle de variables, alertas de presupuesto y Cloud Run está en `docs/despliegue.md`. El registro de la versión 1.0.0 está en `CHANGELOG.md`.

Copia `.env.example` a `.env` para el resto de variables. En producción `JWT_SECRET` no puede quedar en el valor de desarrollo.

La imagen de contenedor escucha en el puerto 8080:

```powershell
docker build -t guitarcoach-backend .
docker run --rm -p 8080:8080 guitarcoach-backend
```
