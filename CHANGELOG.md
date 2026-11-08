# Registro de cambios

## Sin publicar

- El límite de `POST /auth/*` se comparte por Redis cuando hay `REDIS_URL` (Upstash en Vercel): ventana deslizante por IP en un *sorted set*. Si Redis falla, cuenta en memoria. Detrás de Vercel la IP sale de `x-real-ip`.
- Arquitectura de monolito modular: `identity`, `catalog`, `guides`, `practice`, `coaching`, `learning` y `journey`, con interfaces públicas y una prueba que hace cumplir las fronteras. Las rutas y los mensajes se conservan; el WebSocket y Redis siguen igual.
- Nuevo módulo `journey`: `GET` y `POST /me/journey` guardan la ruta, la racha y los logros en la cuenta.
- El informe y el análisis del curso ya no fallan sin Groq: responden con un análisis local.
- `GET /attempts/{id}/report` pide token y un informe ajeno responde 404 también al pedirlo por `POST`.
- La ventana de acierto nunca supera medio tiempo, para que puntuar a tempos altos tenga sentido.
- Guías desde tablaturas de Guitar Pro: `POST /guides/from-tab` valida la guía que arma el navegador, reconoce el formato por la firma del archivo y lo guarda en `guide_tabs`; `GET /guides/{id}/tab` lo devuelve.
- MusicXML: altura real de la guitarra (tablatura o `<transpose>`), elección de la parte de guitarra y repeticiones con casillas. Sin melodía inventada cuando el origen no trae notas.
- Se quitaron `POST /guides/paste`, `POST /guides/upload` y `POST /guides/from-audio`, junto con el análisis de audio (librosa) y sus variables `DAILY_AUDIO_LIMIT` y `AUDIO_TIMEOUT_SECONDS`.
- Guías de canciones privadas por usuario: pegar acordes, subir ChordPro o MusicXML y corregir en el editor. La letra nunca se guarda.
- Lectores que respetan compases, duraciones, secciones, cejilla, compás y rasgueo; acordes en español y con bajo.
- Guía desde un audio propio con librosa (pulso, croma, Viterbi y primer tiempo del compás). El audio se borra al terminar.
- El historial de progreso incluye el título de la canción. CORS permite PUT.
- La imagen de Docker incluye el análisis de audio.

## 1.0.0

- API de salud, registro, sesión y telemetría de intentos.
- Importación de canciones con cola local, robots.txt y caché por URL.
- Informes del tutor con validación de JSON, caché por métricas y límite diario.
- Límite de autenticación, CORS explícito y cabeceras de seguridad.
- Imagen de contenedor con usuario sin privilegios y sonda de salud.
