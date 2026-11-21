# syntax=docker/dockerfile:1
FROM python:3.12-slim

# The commit this image is built from; CI passes --build-arg GIT_SHA=<sha> and
# /health reports it as "version". Not a secret.
ARG GIT_SHA=dev
ENV PORT=8000 \
    GIT_SHA=${GIT_SHA} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser

# Dependencies first: changing source code does not reinstall packages.
# Versions are pinned in requirements.txt.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs at runtime: no tests, no .env, never COPY . .
COPY --chown=appuser:appuser app.py ./
COPY --chown=appuser:appuser tabby/ ./tabby/
COPY --chown=appuser:appuser migrations/ ./migrations/

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)" || exit 1

CMD ["python", "app.py"]
