FROM python:3.12-slim

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml README.md ./
COPY app ./app

# Incluye el análisis de audio (librosa). numba guarda su caché en /tmp porque el
# usuario de la app no puede escribir en site-packages.
ENV NUMBA_CACHE_DIR=/tmp/numba-cache
RUN pip install --no-cache-dir ".[analysis]"

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
