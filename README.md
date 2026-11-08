# GuitarCoach Backend

API FastAPI de GuitarCoach AI. El audio no llega a este servicio: el navegador escucha, juzga y envía telemetría. Aquí viven las cuentas, el catálogo, las guías, los intentos y los informes.

Tres repositorios forman el sistema. Este es el de la API. El esquema está en `guitarcoach-database` y la interfaz en `guitarcoach-frontend`.

| Documento | Qué explica |
| --- | --- |
| [docs/arquitectura.md](docs/arquitectura.md) | Monolito modular, capas, fronteras, petición, persistencia y seguridad. |
| [docs/modulos.md](docs/modulos.md) | Qué hace cada módulo y el contrato HTTP. |
| [docs/despliegue.md](docs/despliegue.md) | Local, Vercel, Supabase y Redis. |
| [CHANGELOG.md](CHANGELOG.md) | Versión 1.0.0. |

## Cómo ejecutarlo

Requisitos: Python 3.12. Postgres sale del otro repositorio (`docker compose up -d` en `guitarcoach-database`).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`GET /health` responde `{"status": "ok"}`.

Comprobaciones:

```powershell
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff format --check app tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest
```

Copia `.env.example` a `.env`. Con `USE_DATABASE=false` todo vive en memoria y las pruebas unitarias no necesitan Postgres. Con `true`, la API lee el esquema `guitarcoach` de `DATABASE_URL`. En producción `JWT_SECRET` no puede ser el valor de desarrollo ni tener menos de 32 caracteres.

Las pruebas de integración se omiten sin `DATABASE_URL`. Usa una base aparte de la de trabajo:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://guitarcoach:guitarcoach@localhost:54329/guitarcoach_test"
.\.venv\Scripts\python.exe -m pytest tests/integration
```

Con `TEST_REDIS_URL=redis://localhost:6379/0` también se comprueba el aviso del trabajo contra un Redis real.

## Forma del sistema

```mermaid
flowchart LR
  navegador[Navegador]
  api[API FastAPI]
  db[(Postgres esquema guitarcoach)]
  tutor[Groq]
  navegador -->|telemetria REST| api
  api --> db
  api -->|texto del informe| tutor
```

Un solo proceso, partido en módulos (`identity`, `catalog`, `guides`, `practice`, `coaching`, `learning`, `journey`). Cada uno tiene dominio, casos de uso, puertos e infraestructura, y solo enseña `public.py` a los demás. La explicación y el diagrama de capas están en [docs/arquitectura.md](docs/arquitectura.md).

```text
app/
  main.py          Composición: arma la aplicación y registra los módulos.
  bootstrap/       Une los repositorios en una transacción por petición.
  shared/          Configuración, errores, HTTP, sesión SQL, valores musicales.
  modules/         Una carpeta por capacidad de negocio.
```

## Vercel

El API es un proyecto de Vercel distinto del frontend. El objeto publicado es `app` en `app/main.py`. Python 3.12 está en `.python-version`.

Los valores del panel, el pooler de Supabase y cuándo hace falta Redis están en [docs/despliegue.md](docs/despliegue.md). `CORS_ORIGINS` es la URL del frontend, con o sin corchetes JSON. En Vercel, `REDIS_URL` apunta a Upstash (`rediss://`) para que el límite de `POST /auth/*` se comparta entre instancias; sin ella cada instancia cuenta por su lado.
