#!/usr/bin/env sh
# =============================================================================
# LectureForge AI - Backend process launcher
# -----------------------------------------------------------------------------
# Three processes run in this one container:
#   1. redis-server  -> Celery broker (in-container; no external Redis needed)
#   2. celery worker -> background
#   3. uvicorn (API) -> foreground, bound to $PORT
#
# The worker shares the API's filesystem so it can read uploaded files from
# UPLOAD_DIR (each service instance gets its own disk, so the worker must run
# in the same container as the API).
# =============================================================================
set -e

# 1. In-container Redis broker (in-memory; the task queue is not persisted).
redis-server --save "" --appendonly no --daemonize no &
for _ in $(seq 1 30); do redis-cli ping >/dev/null 2>&1 && break; sleep 1; done

# 2. Celery worker in the background. Keep concurrency low on small instances.
celery -A app.workers.celery_app worker \
  --loglevel=info \
  -Q default \
  --concurrency="${CELERY_CONCURRENCY:-1}" &

# 3. API in the foreground. Honor the platform's WEB_CONCURRENCY (Render sets
#    this based on available CPUs) and default to a single worker so the Redis +
#    Celery + API processes fit comfortably in one instance's memory.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-1}"
