# Registro de cambios

## Sin publicar

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
