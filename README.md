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
  tutor[Groq]
  navegador -->|telemetria REST| api
  api --> db
  api -->|texto del informe| tutor
```

## Arquitectura: monolito modular

Un solo proceso y una sola base de datos, con el código dividido por capacidades de negocio. Cada módulo se puede entender y cambiar sin leer los demás, y extraer uno más adelante no exige reescribirlo.

```text
app/
  main.py          Composición: arma la aplicación y registra los módulos.
  bootstrap/       Une los repositorios de todos los módulos en una transacción por petición.
  shared/          Lo que no es de nadie: configuración, errores, reloj, HTTP, sesión SQL, valores musicales.
  modules/
    identity/      Cuentas, contraseñas y JWT.
    catalog/       Canciones, plan de estudio, importación y su aviso por WebSocket y Redis.
    guides/        Guías de canciones y tablaturas de Guitar Pro.
    practice/      Intentos, evaluación y progreso.
    coaching/      Informe del tutor y análisis según el curso.
    learning/      Temario, avance y repaso.
    journey/       Ruta del principiante, racha y logros.
```

Cada módulo sigue las mismas capas:

| Capa | Qué contiene | Puede depender de |
| --- | --- | --- |
| `domain/` | Entidades y reglas puras | `shared`, interfaces públicas de otros módulos |
| `application/` | Casos de uso | `domain`, `ports` |
| `ports.py` | Lo que el módulo necesita del exterior, y su almacén (`CatalogStore`, `PracticeStore`…) | `domain` |
| `infrastructure/` | SQLAlchemy, memoria, Groq, Redis, scraping | todo lo anterior |
| `api` | Rutas de FastAPI | todo lo anterior |
| `public.py` | Lo único que ven los demás módulos | `domain`, `ports`, `application` |

Las fronteras no dependen de la disciplina: `tests/architecture/test_module_boundaries.py` rompe el CI si un módulo importa el interior de otro, si el dominio usa un framework o si la aplicación toca la infraestructura.

```mermaid
flowchart TD
  identity
  catalog
  guides --> catalog
  practice --> catalog
  learning
  coaching --> practice
  coaching --> catalog
  coaching --> learning
  journey --> practice
  journey --> guides
  journey --> learning
  identity -.->|bearer_user_id| catalog & guides & practice & coaching & learning & journey
```

Todos los módulos comparten la transacción de la petición. La API, las tablas y los mensajes no cambiaron con esta estructura.

### WebSocket y Redis

`POST /songs/import` responde 202 y deja el trabajo en cola. Al terminar, el trabajo se publica en el canal `guitarcoach:job:{id}` y `/ws/jobs/{id}` lo entrega al navegador. Con `REDIS_URL` el aviso llega a cualquier instancia; sin Redis, o si no responde, se queda en el proceso. Vive en `modules/catalog/infrastructure/realtime/bus.py` y `modules/catalog/api/realtime.py`.

## Ruta, racha y logros

| Endpoint | Qué hace |
| --- | --- |
| `GET /me/journey?today=AAAA-MM-DD` | Pasos cumplidos, días de práctica, racha actual, mejor racha y logros. |
| `POST /me/journey` | Agrega pasos y días (`today`, `milestones`, `days`) y devuelve lo mismo. Repetirlo no cambia nada. |

La fecha la manda el navegador porque la racha sigue el día local del alumno; se limita a un día de diferencia con el servidor. Los logros no se guardan: salen de los datos. Lo que la cuenta ya demuestra cuenta aunque el navegador no avise: un intento guardado cumple "tocar", una guía cumple "subir una canción" y un módulo terminado suma su día.

## Informe sin tutor externo

Si Groq no está configurado o falla, `POST /attempts/{id}/report` y `POST /me/coach` responden con un análisis local calculado con los datos reales (`model: "analisis-local"`). La pantalla del informe avisa cuando pasa, y ese análisis no se reutiliza para otro intento: el siguiente vuelve a intentar con Groq. El informe de un intento solo lo puede leer su dueño.

La ventana de acierto de un intento es de 150 ms, pero nunca más de medio tiempo: a 300 BPM son 100 ms.

## Persistencia

Con `USE_DATABASE=true` la API abre una sesión de PostgreSQL por petición y guarda usuarios, guías, intentos e informes en `DATABASE_URL`. Con `false` todo vive en memoria del proceso y se pierde al cerrarlo; así corren las pruebas unitarias. El esquema lo aplica `guitarcoach-database` (migraciones `0017_song_guides` para las guías y `0019_user_journey` para la ruta).

Las pruebas de integración se omiten sin `DATABASE_URL`. Para correrlas sin tocar la base de trabajo, usa una base aparte:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://guitarcoach:guitarcoach@localhost:54329/guitarcoach_test"
.\.venv\Scripts\python.exe -m pytest tests/integration
```

Con `TEST_REDIS_URL=redis://localhost:6379/0` también se comprueba el aviso del trabajo contra un Redis real.

## Guías de canciones

Una guía es la versión de estudio de una canción que eligió el usuario. Guarda secciones (intro, verso, coro…), acordes con su inicio y duración en pulsos, el rasgueo de cada sección, la cejilla y, si el origen la trae, la melodía con sus duraciones. **No guarda la letra**: los lectores la usan para ubicar los acordes y la descartan, y el esquema rechaza un documento con letra.

| Endpoint | Qué hace |
| --- | --- |
| `POST /guides/from-tab` | La única forma de crear una guía. Recibe la tablatura de Guitar Pro (hasta 5 MB) y la guía que el navegador armó de ella con alphaTab: acordes, rasgueos y notas de la guitarra. Valida la guía con el mismo esquema que `PUT`, reconoce el formato por la firma del archivo (no por la extensión) y guarda el archivo en `guide_tabs`. |
| `GET /guides/{id}/tab` | Devuelve el archivo de la tablatura para tocarla en la guía. |
| `GET /guides` | Lista las guías del usuario. |
| `GET /guides/{id}` | Devuelve la guía completa. |
| `PUT /guides/{id}` | Guarda la guía corregida en el editor y su estado (`borrador` o `revisada`). |

Reglas:

- Todos los endpoints piden el token. Una guía ajena responde 404, igual que una que no existe.
- Crear es idempotente: el mismo contenido para el mismo usuario devuelve la guía que ya existe (200 en vez de 201).
- Cada guía tiene una canción de práctica (`song_id`) para que los intentos y el informe funcionen igual que con el catálogo. Esas canciones no aparecen en la búsqueda pública.

Ya no se crean guías pegando texto, subiendo ChordPro ni analizando un audio: un cifrado o una grabación no dicen qué tocó la guitarra, y la tablatura sí. Los lectores de texto y MusicXML de `app/domain/services/guide_import.py` siguen en uso para la carta que se sube a la biblioteca (`POST /songs/upload`):

- Una línea solo de acordes (`G  D  Em  C`) da un compás por acorde. Acepta nombres en español (`Lam`, `Sol/Si`) y las variantes de los cancioneros (`C7M`, `Bm7(b5)`).
- Con barras, cada tramo entre `|` es un compás; `.` prolonga el acorde un casillero y `%` repite el compás anterior. `| D7 . G . |` son dos acordes de dos pulsos.
- `x2` al final de la línea la repite.
- `[Intro]`, `Coro:` o `{start_of_chorus}` abren una sección. `Capo 2` o `{capo: 2}` fijan la cejilla, y `{time: 3/4}` el compás.
- El rasgueo se escribe en casilleros: `D-DU-UDU` son ocho corcheas en 4/4 (D abajo, U arriba, X apagado, - silencio).
- MusicXML respeta `divisions`, el compás, los tipos de acorde, las ligaduras y los silencios. Rechaza documentos con entidades. Además:
  - **Parte**: lee la de guitarra (la que trae tablatura o se llama guitarra) y no la primera, que puede ser la voz o el piano.
  - **Altura real**: la guitarra se escribe una octava por encima de como suena. La nota sale de la cuerda y el traste de la tablatura, más la cejilla; si no hay tablatura, de lo escrito más `<transpose>`.
  - **Repeticiones**: despliega las barras de repetición y las casillas de 1.ª y 2.ª vez, para que la guía dure lo que dura la canción.
- **Sin melodía inventada**: si el origen no trae notas, la guía queda sin melodía. Antes se guardaban la fundamental y la tercera de cada acorde como si fueran la melodía, y eso sonaba a otra canción.

La variante de capa gratuita usa Neon o Supabase y la API de Groq. El detalle de variables, alertas de presupuesto y Cloud Run está en `docs/despliegue.md`. El registro de la versión 1.0.0 está en `CHANGELOG.md`.

Copia `.env.example` a `.env` para el resto de variables. En producción `JWT_SECRET` no puede quedar en el valor de desarrollo.

La imagen de contenedor escucha en el puerto 8080:

```powershell
docker build -t guitarcoach-backend .
docker run --rm -p 8080:8080 guitarcoach-backend
```
