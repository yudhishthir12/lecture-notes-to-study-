# ==============================================================================
# LectureForge AI - Production Backend Dockerfile
# Multi-purpose container for FastAPI web API and Celery background workers.
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing bytecode and enable unbuffered standard I/O
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies:
# - build-essential, libpq-dev, libffi-dev: C build tools and PostgreSQL libraries
# - tesseract-ocr, tesseract-ocr-eng: Optical character recognition fallback
# - libglib2.0-0, libpango-1.0-0, libpangocairo-1.0-0, libgdk-pixbuf-2.0-0, shared-mime-info: WeasyPrint PDF generator
# - curl: Health check probing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and migrations
COPY . /app

# Create persistent storage directories for uploads and exported study packs
RUN mkdir -p /app/uploads /app/exports && chmod -R 777 /app/uploads /app/exports

# Create dedicated non-root application user and the persistent-data root
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --home /app appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appgroup /app && \
    chmod +x /app/entrypoint.sh

# NOTE: the container starts as root so entrypoint.sh can fix ownership of any
# mounted volumes/disks (e.g. Render persistent disks are root-owned), then it
# drops privileges to `appuser` before running the application.

# Expose FastAPI HTTP server port
EXPOSE 8000

# Health check definition
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Fix volume ownership + run migrations, then start the given command as appuser
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command: launch production Uvicorn server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
