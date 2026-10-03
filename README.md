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

Copia `.env.example` a `.env` para el resto de variables. En producción `JWT_SECRET` no puede quedar en el valor de desarrollo.

La imagen de contenedor escucha en el puerto 8080:

```powershell
docker build -t guitarcoach-backend .
docker run --rm -p 8080:8080 guitarcoach-backend
```
