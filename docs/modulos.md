# Módulos y contrato HTTP

El detalle de capas y de cómo se hablan está en [arquitectura.md](arquitectura.md). Aquí queda qué hace cada módulo y qué rutas publica. Todas las rutas de cuenta piden `Authorization: Bearer`, salvo el registro, el inicio de sesión, la salud y la búsqueda pública de canciones.

## Identidad

Cuentas, hash Argon2 y emisión del JWT. El resto de la API solo usa `bearer_user_id`.

| Método y ruta | Qué hace |
| --- | --- |
| `POST /auth/register` | Crea la cuenta. La contraseña tiene al menos 8 caracteres. El correo repetido responde 409. |
| `POST /auth/login` | Devuelve `access_token`. Un correo o una contraseña que no coinciden responden 401, `Credenciales inválidas.` |

## Catálogo

Canciones compartidas, su plan de estudio y la importación.

| Método y ruta | Qué hace |
| --- | --- |
| `GET /songs?q=` | Busca por título. Usa `pg_trgm`. |
| `POST /songs/import` | 202 y un trabajo. En Vercel espera a terminarlo antes de responder. |
| `GET /jobs/{id}` | Estado del trabajo, `song_id` y el error si falló. |
| `GET /songs/{id}/study` | Plan de estudio de esa canción. |
| `WS /ws/jobs/{id}` | El cliente manda el token al abrir. En Vercel el navegador usa `GET /jobs/{id}` si el socket no conecta. |

El catálogo de aula (Cambios abiertos, Ronda de menores, Lamento boliviano) se vuelve a sembrar al arrancar, por su URL de origen. Esas tres canciones no se borran.

## Guías

La guía es la versión de estudio que armó el alumno: secciones, acordes con inicio y duración, rasgueo, cejilla y, si el archivo la trae, la melodía. El documento `jsonb` rechaza la clave `lyrics`.

| Método y ruta | Qué hace |
| --- | --- |
| `POST /guides/from-tab` | Única forma de crear una guía. Recibe la tablatura (hasta 5 MB) y la guía que el navegador armó con alphaTab. El formato se reconoce por la firma del archivo. El mismo contenido del mismo usuario devuelve la guía existente. |
| `GET /guides` | Lista las del usuario. |
| `GET /guides/{id}` | La guía completa. Una ajena responde 404, igual que una inexistente. |
| `PUT /guides/{id}` | Guarda la corrección y el estado `borrador` o `revisada`. |
| `DELETE /guides/{id}` | La borra, y con ella el archivo. |
| `GET /guides/{id}/tab` | Devuelve el archivo para volver a tocarlo. |
| `POST /songs/upload` | Carta de acordes para la biblioteca, no una guía. Acepta texto y MusicXML. |

Cada guía tiene una canción de práctica para que el intento y el informe funcionen como en el catálogo. Esas canciones no salen en la búsqueda pública.

El lector de cartas entiende una línea de acordes, barras `|`, `.` para prolongar, `%` para repetir el compás, `x2` al final de la línea, secciones (`[Intro]`, `Coro:`, `{start_of_chorus}`), `Capo` y `{time}`. El rasgueo se escribe en casilleros (`D-DU-UDU`). MusicXML respeta divisiones, compás, la pista de guitarra, la cejilla y las repeticiones. Si el origen no trae notas, la guía queda sin melodía.

En Vercel el cuerpo de la petición se corta cerca de 4,5 MB, aunque la API acepte 5 MB.

## Práctica

| Método y ruta | Qué hace |
| --- | --- |
| `POST /attempts` | Guarda la telemetría que el navegador ya juzgó. |
| `GET /me/progress` | Precisión de los intentos del usuario. |

La ventana de acierto es de 150 ms y nunca más de medio tiempo: a 300 BPM son 100 ms.

## Coaching

| Método y ruta | Qué hace |
| --- | --- |
| `POST /attempts/{id}/report` | Pide el informe. Solo el dueño. |
| `GET /attempts/{id}/report` | Lo lee. |
| `DELETE /attempts/{id}` | Borra el intento y su informe. |
| `POST /me/coach` | Análisis según el modo `quiz` o `progresion`. |

Sin Groq, o si Groq falla, la respuesta trae `model: "analisis-local"`. Ese análisis no se guarda como definitivo: el siguiente intento vuelve a llamar al tutor. `DAILY_REPORT_LIMIT` cuenta los informes nuevos; una caché por hash no vuelve a llamar al modelo.

## Aprendizaje

| Método y ruta | Qué hace |
| --- | --- |
| `GET /me/curriculum` | Temario, con lecciones hechas, pendientes y bloqueadas, y el repaso si toca. |
| `POST /me/lessons/{id}/complete` | Marca la lección. |
| `POST /me/review` | El alumno ya vio el repaso del día. |

## Ruta del principiante

| Método y ruta | Qué hace |
| --- | --- |
| `GET /me/journey?today=AAAA-MM-DD` | Pasos, días, racha actual, mejor racha y logros. |
| `POST /me/journey` | Agrega `today`, `milestones` y `days`. Repetirlo no cambia lo ya guardado. |

La fecha la manda el navegador porque la racha sigue el día local del alumno. Se acepta como mucho un día de diferencia con el servidor. Los logros no tienen tabla: se calculan. Un intento guardado cumple «tocar», una guía cumple «subir una canción» y un módulo terminado suma su día, aunque el navegador no lo haya avisado.
