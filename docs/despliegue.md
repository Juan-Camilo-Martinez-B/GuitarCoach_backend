# Despliegue

El audio no sale del navegador. Este servicio solo recibe telemetría, guarda canciones y pide informes al tutor.

## Variables

| Variable | Uso |
| --- | --- |
| `ENVIRONMENT` | `local` o `production`. `deploy.yml` lo fija en `production`, donde un secreto JWT de desarrollo o corto detiene el arranque. |
| `DATABASE_URL` | Postgres con el driver `postgresql+asyncpg`. |
| `JWT_SECRET` | Al menos 32 caracteres, distinto del valor de desarrollo. Genéralo con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Cambiarlo cierra todas las sesiones abiertas. |
| `CORS_ORIGINS` | Lista JSON de orígenes. No uses `*`. |
| `GROQ_API_KEY` | Clave del API de Groq. Vacía en local. |
| `GROQ_MODEL` | Por defecto `openai/gpt-oss-120b`. Si Groq retira el modelo, la API responde con el análisis local: comprueba `model` en la respuesta. |
| `DAILY_REPORT_LIMIT` | Informes nuevos por usuario y día. La caché por hash no vuelve a llamar al modelo. |
| `AUTH_REQUESTS_PER_MINUTE` | Tope de `POST /auth/*` por cliente. |
| `REDIS_URL` | Vacío deja el aviso en el proceso. `redis://localhost:6379/0` publica el fin del trabajo y `/ws/jobs/{id}` lo entrega. |

## Variante de capa gratuita

Para un presupuesto de aula, la base puede ser Neon o Supabase y el tutor la API de Groq. No hace falta Cloud SQL ni Vertex AI. El mismo contrato SQL y el mismo `Tutor` sirven en ambos sitios.

Configura alertas de presupuesto al 50 %, 90 % y 100 % del tope mensual antes de dejar la clave en Cloud Run.

## Cloud Run

El workflow `desplegar` es manual. Necesita el secreto `GCP_SA_KEY` y las variables `GCP_PROJECT` y `GCP_REGION`. La imagen escucha en el puerto 8080 y la sonda es `GET /health`.

```text
navegador -- telemetria REST --> API --> Postgres
                              \-> Groq (solo texto del informe)
```
