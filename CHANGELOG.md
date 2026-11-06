# Registro de cambios

## Sin publicar

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
