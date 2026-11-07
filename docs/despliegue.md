# Despliegue

El audio no sale del navegador. Este servicio recibe telemetría, guarda canciones y guías, y pide el texto del informe al tutor.

Hay dos formas de dejarlo corriendo: la máquina local, para desarrollar, y Vercel contra Supabase, que es el despliegue actual. El workflow `desplegar` sigue pudiendo publicar una imagen en Cloud Run; escucha en el puerto 8080 y usa `GET /health` como sonda.

## Variables

| Variable | Uso |
| --- | --- |
| `ENVIRONMENT` | `local` o `production`. En producción un `JWT_SECRET` de desarrollo, o de menos de 32 caracteres, detiene el arranque. |
| `USE_DATABASE` | `true` abre Postgres. `false` deja todo en memoria y se pierde al cerrar el proceso. |
| `DATABASE_URL` | `postgresql+asyncpg://`. En Supabase, el usuario es `postgres.<ref>`, el host es el pooler de sesión (`aws-0-….pooler.supabase.com`) y el puerto es `5432`. |
| `JWT_SECRET` | Al menos 32 caracteres. Genéralo con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Cambiarlo cierra las sesiones abiertas. |
| `JWT_TTL_MINUTES` | Caducidad del token. 720 cubre una tarde de práctica. |
| `CORS_ORIGINS` | Origen exacto del frontend. Vale una URL (`https://guitar-coach-frontend.vercel.app`) o un JSON (`["https://…"]`). Una barra final se ignora. No uses `*`: hay credenciales. |
| `GROQ_API_KEY` | Clave del tutor. Vacía: los informes salen del análisis local. |
| `GROQ_MODEL` | Por defecto `openai/gpt-oss-120b`. Si el modelo deja de existir, la respuesta trae `model: "analisis-local"`. |
| `DAILY_REPORT_LIMIT` | Informes nuevos por usuario y día. |
| `AUTH_REQUESTS_PER_MINUTE` | Tope de `POST /auth/*` por cliente. |
| `REDIS_URL` | Vacío: el aviso del trabajo se queda en el proceso. `redis://localhost:6379/0` lo publica y `/ws/jobs/{id}` lo entrega. En Vercel déjala vacía. |
| `LOG_LEVEL` | `INFO` en condiciones normales. |

`JWT_SECRET`, `DATABASE_URL` y `GROQ_API_KEY` son secretos. `CORS_ORIGINS` y `VITE_API_URL` del frontend son configuración normal: el build y el arranque tienen que poder leerlas.

La URL de Supabase que muestra el panel a veces trae `sslmode` y `channel_binding`. El motor los quita, porque asyncpg no los acepta, y abre TLS por su cuenta. No hace falta pegarlos.

## Local

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Postgres y Redis salen de `guitarcoach-database`:

```powershell
docker compose up -d
```

`GET http://127.0.0.1:8000/health` responde `{"status":"ok"}`. El origen permitido en local es `http://localhost:5173`.

## Vercel

Proyecto distinto del frontend. Vercel detecta el objeto `app` de `app/main.py` (`tool.vercel.entrypoint`). Python 3.12 está fijado en `.python-version`. `vercel.json` deja la función en 60 segundos y deja fuera pruebas, el entorno virtual y las cachés.

En el panel, entorno Production:

| Variable | Valor |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `USE_DATABASE` | `true` |
| `DATABASE_URL` | la URL `postgresql+asyncpg://` del pooler, puerto 5432 |
| `JWT_SECRET` | una clave de al menos 32 caracteres |
| `JWT_TTL_MINUTES` | `720` |
| `CORS_ORIGINS` | `https://guitar-coach-frontend.vercel.app` |
| `GROQ_API_KEY` | la clave, si el tutor externo está en uso |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `DAILY_REPORT_LIMIT` | `5` |
| `AUTH_REQUESTS_PER_MINUTE` | `20` |
| `LOG_LEVEL` | `INFO` |

No definas `REDIS_URL`. Vercel crea `VERCEL=1`: la importación de una canción termina dentro de la misma petición.

Después de publicar, `GET /health` debe responder 200. Un 500 con `FUNCTION_INVOCATION_FAILED` en los logs de la función suele ser `CORS_ORIGINS` ilegible o un secreto que no cumple la regla de producción. El cuerpo de una tablatura de más de unos 4,5 MB puede rechazarlo el límite de Vercel.

## Redis en una demo local

El curso puede ver el aviso sin desplegar Redis en Vercel:

1. `docker compose up -d` en `guitarcoach-database` (Redis 7 en el puerto 6379).
2. `REDIS_URL=redis://localhost:6379/0` en el `.env` del API, y reinicia uvicorn.
3. `redis-cli SUBSCRIBE guitarcoach:job:*`
4. Importa una canción desde el navegador. El mensaje aparece en la suscripción y el socket `/ws/jobs/{id}` lo entrega a la pantalla.

## Imagen

```powershell
docker build -t guitarcoach-backend .
docker run --rm -p 8080:8080 --env-file .env guitarcoach-backend
```

El workflow `desplegar` es manual. Necesita el secreto `GCP_SA_KEY` y las variables `GCP_PROJECT` y `GCP_REGION`.
