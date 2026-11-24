#!/usr/bin/env sh
# ==============================================================================
# LectureForge AI - Backend container entrypoint
#   1. Ensures runtime storage dirs exist and are writable by the app user
#      (mounted volumes / Render persistent disks arrive root-owned).
#   2. Optionally applies Alembic migrations (RUN_MIGRATIONS=true).
#   3. Drops root privileges to `appuser` and execs the given command.
# ==============================================================================
set -e

UPLOAD_DIR="${UPLOAD_DIR:-/app/uploads}"
EXPORT_DIR="${EXPORT_DIR:-/app/exports}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"

# Some orchestrators pass the whole command line as a single string (Render's
# dockerCommand, Compose string `command`). Wrap it so the shell interprets
# pipes/chains instead of treating the entire string as one binary name.
if [ "$#" -eq 1 ]; then
  case "$1" in
    *" "*|*"&"*|*";"*) set -- /bin/sh -c "$1" ;;
  esac
fi

if [ "$(id -u)" = "0" ]; then
  # Running as root: prepare storage, then drop privileges to appuser.
  mkdir -p "$UPLOAD_DIR" "$EXPORT_DIR"
  chown -R appuser:appgroup "$UPLOAD_DIR" "$EXPORT_DIR" || true

  if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
    gosu appuser alembic upgrade head
    echo "[entrypoint] Migrations up to date."
  fi

  echo "[entrypoint] Starting as appuser: $*"
  exec gosu appuser "$@"
fi

# Already running as a non-root user: migrate (if enabled) and run.
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
  alembic upgrade head
  echo "[entrypoint] Migrations up to date."
fi

exec "$@"
