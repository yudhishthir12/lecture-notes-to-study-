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
# UPLOAD_DIR (each Railway service gets its own disk, and volumes cannot be
# shared between services).
# =============================================================================
set -e

# 1. In-container Redis broker (in-memory; the task queue is not persisted).
redis-server --save "" --appendonly no --daemonize no &
for _ in $(seq 1 30); do redis-cli ping >/dev/null 2>&1 && break; sleep 1; done

# 2. Celery worker in the background.
celery -A app.workers.celery_app worker \
  --loglevel=info \
  -Q default \
  --concurrency="${CELERY_CONCURRENCY:-2}" &

# 3. API in the foreground (Railway routes HTTP traffic to $PORT).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 2
