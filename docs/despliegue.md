# Despliegue

El audio no sale del navegador. Este servicio solo recibe telemetría, guarda canciones y pide informes al tutor.

## Variables

| Variable | Uso |
| --- | --- |
| `ENVIRONMENT` | `local` o `production`. En producción el secreto JWT de desarrollo detiene el arranque. |
| `DATABASE_URL` | Postgres con el driver `postgresql+asyncpg`. |
| `JWT_SECRET` | Secreto largo, distinto del valor de desarrollo. |
| `CORS_ORIGINS` | Lista JSON de orígenes. No uses `*`. |
| `GEMINI_API_KEY` | Clave del API de Gemini. Vacía en local. |
| `GEMINI_MODEL` | Por defecto `gemini-2.0-flash`. |
| `DAILY_REPORT_LIMIT` | Informes nuevos por usuario y día. La caché por hash no vuelve a llamar al modelo. |
| `AUTH_REQUESTS_PER_MINUTE` | Tope de `POST /auth/*` por cliente. |

## Variante de capa gratuita

Para un presupuesto de aula, la base puede ser Neon o Supabase y el tutor la API de Gemini. No hace falta Cloud SQL ni Vertex AI. El mismo contrato SQL y el mismo `Tutor` sirven en ambos sitios.

Configura alertas de presupuesto al 50 %, 90 % y 100 % del tope mensual antes de dejar la clave en Cloud Run.

## Cloud Run

El workflow `desplegar` es manual. Necesita el secreto `GCP_SA_KEY` y las variables `GCP_PROJECT` y `GCP_REGION`. La imagen escucha en el puerto 8080 y la sonda es `GET /health`.

```text
navegador -- telemetria REST --> API --> Postgres
                              \-> Gemini (solo texto del informe)
```
