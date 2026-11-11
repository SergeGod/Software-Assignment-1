# syntax=docker/dockerfile:1
FROM python:3.12-slim

# PORT and DATA_DIR are read by tabby/config.py. The SQLite file is written
# under DATA_DIR, so mount a volume there to keep data across restarts.
ENV PORT=8000 \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Run as a non-root user that owns only the app and data folders.
RUN useradd --create-home --uid 10001 appuser \
 && mkdir -p /data \
 && chown -R appuser:appuser /data /app

# Dependencies first: changing source code does not reinstall packages.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser app.py ./
COPY --chown=appuser:appuser tabby/ ./tabby/

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=2)" || exit 1

CMD ["python", "app.py"]
