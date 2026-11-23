# LectureForge AI 🎓⚡

**Production-grade AI pipeline transforming raw academic lecture slides, notes, and textbook chapters into comprehensive, publication-ready study packs.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14.2-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📑 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Quick Start with Docker](#quick-start-with-docker)
- [Local Development Setup (without Docker)](#local-development-setup-without-docker)
- [Environment Variables](#environment-variables)
- [API Endpoints Reference](#api-endpoints-reference)
- [Project Directory Structure](#project-directory-structure)
- [Testing Instructions](#testing-instructions)
- [Export Formats](#export-formats)
- [Pipeline Configuration](#pipeline-configuration)
- [Troubleshooting](#troubleshooting)

---

## 🌟 Overview

LectureForge AI ingests heterogeneous lecture materials (PDF slide decks, PowerPoint presentations, and plain text notes), cleans presentation noise (recurring headers/footers, slide numbers), splits documents semantically into chunked sections with exact provenance citations, and synthesizes structured study packs via Google Gemini 2.0 Flash.

Every generated study pack undergoes strict deterministic static analysis and multi-metric LLM self-evaluation before publishing. Outputs are downloadable as publication-grade styled PDFs, GitHub Flavored Markdown documents, and Anki CSV flashcards.

---

## 🏛️ Architecture

```
                                  +-----------------------------+
                                  |   Next.js 14 Frontend UI    |
                                  |  (React 18 + TailwindCSS)   |
                                  |       Port: 3000            |
                                  +--------------+--------------+
                                                 |
                                     HTTP REST / JSON
                                                 |
                                                 v
+-----------------------------------------------------------------------------------------------+
|                                  FastAPI Backend API (Port: 8000)                             |
|                                                                                               |
|  +--------------------+     +---------------------+     +----------------------------------+  |
|  | Documents Router   |     | Study Packs Router  |     | Lifecycle Lifespan & Middleware  |  |
|  +---------+----------+     +----------+----------+     +----------------+-----------------+  |
+------------|---------------------------|---------------------------------|--------------------+
             |                           |                                 |
             | Upload / Query            | Retrieve / Export               | Connection Pool
             v                           v                                 v
+--------------------+         +--------------------+          +-----------------------+
| File System Store  |         | WeasyPrint Engine  |          | PostgreSQL 16 DB      |
| /app/uploads       |         | /app/exports       |          | - documents           |
| /app/exports       |         +--------------------+          | - study_packs         |
+--------------------+                                         | - pipeline_runs       |
             ^                                                 +-----------+-----------+
             |                                                             |
             | Dispatches Task                                             |
             |                                                             |
+------------+-------------------------------------------------------------+--------------------+
|                                    Celery Task Worker                                         |
|                                                                                               |
|   +-------------------+    +--------------------+    +--------------------+                   |
|   | 1. DocumentParser | -> | 2. NoiseFilter     | -> | 3. SemanticChunker |                   |
|   | (PDF/PPTX/TXT)    |    | (Header/Footer/No.)|    | (Heading/Overlap)  |                   |
|   +-------------------+    +--------------------+    +---------+----------+                   |
|                                                                |                              |
|   +-------------------+    +--------------------+              v                              |
|   | 6. RetryRouter    | <- | 5. StudyPackEval   | <- +--------------------+                   |
|   | (Max 2 Attempts)  |    | (Audit & Scoring)  |    | 4. AI Pipeline     |                   |
|   +-------------------+    +--------------------+    | (Gemini 2.0 Flash) |                   |
|                                                      +---------+----------+                   |
+----------------------------------------------------------------|------------------------------+
                                                                 |
                                       Redis 7 Cache / Broker   | (External API)
                                       redis://redis:6379/0      v
                                                       +--------------------+
                                                       | Google Gemini API  |
                                                       | (gemini-2.0-flash) |
                                                       +--------------------+
```

---

## ⚡ Key Features

1. **Multi-Format Ingestion**:
   - High-fidelity **PDF** extraction with PyMuPDF layout analysis, table extraction, and OCR fallback for scanned pages.
   - **PowerPoint (.pptx)** slide title detection, shape tree unfolding, table parsing, and bullet hierarchy preservation.
   - **Plain Text (.txt, .md)** with multi-encoding fallback (`utf-8`, `utf-8-sig`, `cp1252`, `latin-1`).

2. **Conservative Noise Filtering**:
   - Cross-page frequency detection to strip running slide titles and institution footers.
   - Robust standalone page number stripping (e.g., `Page 1`, `1 of 20`, `- 5 -`, `[ 3 ]`).
   - Whitespace and newline normalization without damaging formulas or list numbering.

3. **Hierarchical Semantic Chunking**:
   - Preserves logical document outline (`Heading -> Paragraph -> Sentences -> Words`).
   - Configurable token chunk size and sliding character overlap window.
   - Source provenance citation tracking (`source_pages`, `slide_numbers`, `section_title`).

4. **Multi-Stage AI Pipeline**:
   - Automated concept extraction, executive digest, detailed synthesis, formulas, and vocabulary.
   - 3-tier practice question generator: Multiple Choice Questions (MCQ), Short Answer, and Conceptual.
   - MCQ integrity enforcement: exactly 4 options labeled A–D, validated correct answers, and step-by-step reasoning.

5. **Self-Correction & Quality Audit Engine**:
   - Multi-metric evaluation rubric:
     - **Faithfulness & Grounding** (35%)
     - **Topic Coverage** (25%)
     - **Answer Accuracy** (25%)
     - **Pedagogical Clarity** (15%)
   - Automated targeted retry router for failing sections (up to 2 retry attempts).

6. **Publication & Study Exports**:
   - **Markdown (.md)**: Clean GFM typography with interactive checklists, LaTeX math blocks, and quality audits.
   - **PDF (.pdf)**: Academic letter format generated with CSS3 Paged Media via WeasyPrint.
   - **Anki Flashcards (.csv)**: RFC 4180 compliant CSV containing Front, Back, and hierarchical tags (`topic::`, `difficulty::`, `type::`).

---

## 🛠️ Tech Stack

| Domain | Technology | Description |
| :--- | :--- | :--- |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance Python 3.11 asynchronous web framework |
| **Async Tasks** | [Celery](https://docs.celeryq.dev/) + [Redis](https://redis.io/) | Distributed background task queue and message broker |
| **Database** | [PostgreSQL 16](https://www.postgresql.org/) | Relational database with UUID keys and JSON storage |
| **ORM & Migrations** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + [Alembic](https://alembic.sqlalchemy.org/) | Modern async database session management |
| **AI / LLM** | [Google GenAI SDK](https://github.com/google-gemini/generative-ai-python) | Gemini 2.0 Flash with structured Pydantic response schemas |
| **Document Processing**| [PyMuPDF](https://pymupdf.readthedocs.io/), [python-pptx](https://python-pptx.readthedocs.io/) | Native layout parsing, table extraction, and shape processing |
| **PDF Generation** | [WeasyPrint](https://weasyprint.org/) | HTML5/CSS3 to PDF publishing engine |
| **Frontend** | [Next.js 14](https://nextjs.org/) (App Router) | Standalone Node.js 20 production runner |
| **UI Components** | [TailwindCSS](https://tailwindcss.com/) + [Radix UI](https://www.radix-ui.com/) | Accessible, responsive dark/light mode student dashboard |
| **Containerization** | [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/) | Production multi-stage Dockerfiles and container orchestration |

---

## 🚀 Quick Start with Docker

The fastest way to run LectureForge AI is using Docker Compose.

### 1. Clone & Configure Environment

```bash
cd lectureforge-ai
cp .env.example .env
```

Edit `.env` and provide your Google Gemini API key:
```ini
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 2. Build and Start All Containers

```bash
docker compose up --build -d
```

Docker Compose launches 5 interconnected services:
- **`postgres`**: Database on `localhost:5432`
- **`redis`**: Task broker on `localhost:6379`
- **`backend`**: FastAPI REST API on `http://localhost:8000` (Interactive docs: `http://localhost:8000/docs`)
- **`celery-worker`**: Background worker for long-running AI extractions
- **`frontend`**: Next.js student dashboard on `http://localhost:3000`

### 3. Verify Health

```bash
# Check container statuses
docker compose ps

# View backend logs
docker compose logs -f backend

# Probe backend health check
curl http://localhost:8000/health
```

### 4. Stop Services

```bash
docker compose down
```

To wipe persistent database and upload volumes:
```bash
docker compose down -v
```

---

## 💻 Local Development Setup (without Docker)

If you prefer running services directly on your host machine:

### Prerequisites
- Python 3.11+
- Node.js 20+ and npm
- PostgreSQL 15+ running locally
- Redis 7+ running locally
- Native system dependencies for WeasyPrint:
  - **Debian / Ubuntu**: `sudo apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libffi-dev shared-mime-info`
  - **macOS (Homebrew)**: `brew install pango libffi cairo`
  - **Windows**: Install GTK3 runtime from [MSYS2](https://www.msys2.org/) or rely on the automated HTML fallback.

### 1. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Start Celery Worker (in a separate terminal)

```bash
cd backend
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
celery -A app.workers.celery_app worker --loglevel=info
```

### 3. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🔐 Environment Variables

| Variable | Description | Default | Required? |
| :--- | :--- | :--- | :---: |
| `GEMINI_API_KEY` | Google Gemini API Key for synthesis and evaluation | `None` | **Yes** (for AI generation) |
| `GEMINI_MODEL` | Gemini LLM model identifier | `gemini-2.0-flash` | No |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://lectureforge:lectureforge@localhost:5432/lectureforge` | Yes |
| `DATABASE_URL_SYNC` | Synchronous PostgreSQL connection string | `postgresql://lectureforge:lectureforge@localhost:5432/lectureforge` | Yes |
| `POSTGRES_USER` | PostgreSQL superuser | `lectureforge` | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL password | `lectureforge` | Yes |
| `POSTGRES_DB` | PostgreSQL database name | `lectureforge` | Yes |
| `REDIS_URL` | Redis instance URL | `redis://localhost:6379/0` | Yes |
| `CELERY_BROKER_URL` | Message broker for asynchronous tasks | `redis://localhost:6379/0` | Yes |
| `CELERY_RESULT_BACKEND` | Task result store | `redis://localhost:6379/1` | Yes |
| `NEXT_PUBLIC_API_URL` | Public-facing backend URL for frontend requests | `http://localhost:8000` | Yes |
| `MAX_UPLOAD_SIZE_MB` | Maximum allowed document upload file size | `50` | No |
| `UPLOAD_DIR` | Filesystem storage path for uploaded documents | `uploads` | No |
| `EXPORT_DIR` | Filesystem storage path for exported files | `exports` | No |
| `PROMPT_VERSION` | Version tag for prompt template registry | `v1.0` | No |
| `MAX_RETRY_ATTEMPTS` | Automated self-correction loop limit | `2` | No |
| `CHUNK_SIZE` | Target character size for semantic text chunking | `2000` | No |
| `CHUNK_OVERLAP` | Character overlap between consecutive chunks | `200` | No |
| `CORS_ORIGINS` | Comma-separated allowed origins for CORS | `http://localhost:3000,http://frontend:3000` | No |

---

## 📡 API Endpoints Reference

Interactive OpenAPI documentation is live at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### System Endpoints
| Method | Endpoint | Description | Response Status |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Application root health check | `200 OK` |
| `GET` | `/api/health` | API subsystem container health check | `200 OK` |

### Document Management
| Method | Endpoint | Description | Request Body | Response Status |
| :--- | :--- | :--- | :--- | :---: |
| `POST` | `/api/documents/upload` | Upload lecture note (`.pdf`, `.pptx`, `.txt`) | `multipart/form-data` | `201 Created` |
| `GET` | `/api/documents` | List uploaded documents with pagination | Query: `page`, `page_size`, `status` | `200 OK` |
| `GET` | `/api/documents/{id}` | Retrieve document details and text preview | None | `200 OK` / `404` |
| `GET` | `/api/documents/{id}/status` | Poll real-time processing progress | None | `200 OK` / `404` |
| `POST` | `/api/documents/{id}/generate`| Trigger AI study pack generation | None | `200 OK` / `400` |
| `DELETE`| `/api/documents/{id}` | Delete document, disk files, and study packs | None | `204 No Content` |

### Study Packs & Exports
| Method | Endpoint | Description | Request Body | Response Status |
| :--- | :--- | :--- | :--- | :---: |
| `GET` | `/api/study-packs/{id}` | Fetch full structured study pack | None | `200 OK` / `404` |
| `POST` | `/api/study-packs/{id}/regenerate` | Regenerate specific section | `{"sections": ["questions"]}` | `200 OK` |
| `GET` | `/api/study-packs/{id}/evaluation` | Fetch automated quality audit report | None | `200 OK` |
| `GET` | `/api/study-packs/{id}/export/markdown` | Download formatted Markdown file (`.md`) | None | `200 OK` |
| `GET` | `/api/study-packs/{id}/export/pdf` | Download publication-grade PDF (`.pdf`) | None | `200 OK` |
| `GET` | `/api/study-packs/{id}/export/anki` | Download Anki flashcards CSV (`.csv`) | None | `200 OK` |

---

## 📁 Project Directory Structure

```
lectureforge-ai/
├── docker-compose.yml              # Multi-container orchestration (5 services)
├── .env.example                    # Template environment variables
├── README.md                       # Comprehensive system documentation
│
├── backend/
│   ├── Dockerfile                  # Production Debian-slim container with WeasyPrint deps
│   ├── pytest.ini                  # Pytest configuration (auto-asyncio, filters)
│   ├── requirements.txt            # Locked backend dependencies
│   ├── alembic.ini                 # Database migration configuration
│   ├── alembic/                    # Database version scripts
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                 # FastAPI application root & middleware
│   │   ├── api/                    # API route definitions
│   │   │   ├── router.py           # Combined API router
│   │   │   ├── documents.py        # Uploads, document lifecycle
│   │   │   └── study_packs.py      # Study pack endpoints & file streaming
│   │   ├── core/                   # Core infrastructure
│   │   │   ├── config.py           # Pydantic BaseSettings
│   │   │   ├── database.py         # Async SQLAlchemy session factory
│   │   │   └── logging.py          # Structlog configuration
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   └── document.py         # Document, StudyPack, PipelineRun tables
│   │   ├── schemas/                # Pydantic validation models
│   │   │   ├── document.py         # Document DTO schemas
│   │   │   ├── pipeline.py         # Intermediate chunk & extraction DTOs
│   │   │   └── study_pack.py       # Full study pack schema & MCQ validators
│   │   ├── services/               # Extraction & text processing
│   │   │   ├── pdf_parser.py       # PyMuPDF layout & table parsing
│   │   │   ├── pptx_parser.py      # python-pptx slide parsing
│   │   │   ├── txt_parser.py       # Multi-encoding text reader
│   │   │   ├── noise_filter.py     # Recurring headers & footer cleaner
│   │   │   ├── chunker.py          # Semantic section & overlap chunker
│   │   │   ├── llm_service.py      # Gemini 2.0 Flash client with retries
│   │   │   ├── prompt_registry.py  # Versioned system prompts
│   │   │   └── ocr_service.py      # Tesseract OCR fallback
│   │   ├── evaluation/             # Quality audit engine
│   │   │   ├── evaluator.py        # 4-factor scoring & deterministic checks
│   │   │   └── retry_router.py     # Targeted retry plan generation
│   │   ├── exporters/              # Artifact generation
│   │   │   ├── markdown_exporter.py # GFM Markdown renderer
│   │   │   ├── anki_exporter.py    # RFC 4180 Anki CSV flashcards
│   │   │   └── pdf_exporter.py     # WeasyPrint academic letter renderer
│   │   └── workers/                # Celery asynchronous workers
│   │       ├── celery_app.py       # Celery broker configuration
│   │       └── tasks.py            # Async document processing pipeline
│   └── tests/                      # Comprehensive backend test suite (116+ tests)
│       ├── conftest.py             # SQLite async in-memory db & fixtures
│       ├── test_parsers.py         # PDF, PPTX, TXT parser tests
│       ├── test_noise_filter.py    # Header/footer/page number removal tests
│       ├── test_chunker.py         # Semantic chunking & overlap tests
│       ├── test_schemas.py         # Schema & MCQ validator tests
│       ├── test_evaluation.py      # Self-reflection & scoring tests
│       ├── test_exporters.py       # Markdown, Anki, PDF export tests
│       └── test_api.py             # Integration tests for FastAPI endpoints
│
└── frontend/
    ├── Dockerfile                  # Multi-stage Next.js standalone runner
    ├── package.json                # Frontend packages & scripts
    ├── vitest.config.ts            # Vitest unit test configuration
    ├── next.config.js              # Next.js standalone output & rewrites
    ├── tailwind.config.ts          # Styling theme configuration
    ├── app/                        # Next.js App Router
    │   ├── page.tsx                # Dashboard homepage
    │   ├── layout.tsx              # Root HTML layout with providers
    │   ├── documents/              # Document management views
    │   └── study-packs/            # Study pack inspection tabs
    ├── components/                 # UI components
    │   ├── dashboard/              # Document metrics & recent items
    │   ├── layout/                 # Sidebar, header, navigation
    │   ├── study-pack/             # Summary, concepts, questions tabs
    │   ├── upload/                 # Drag-and-drop upload dialog
    │   └── ui/                     # Radix UI primitives
    ├── lib/                        # Client libraries
    │   ├── api.ts                  # Typed backend client with XHR progress
    │   └── utils.ts                # Styling & formatting utilities
    ├── types/                      # TypeScript definitions
    │   └── index.ts
    └── __tests__/                  # Frontend tests
        └── api.test.ts             # API client mock tests (fetch, XHR)
```

---

## 🧪 Testing Instructions

The test suite is structured to execute quickly and deterministically **without requiring external network connections or live Gemini API keys**.

### Backend Tests (Pytest)

Run all backend unit and integration tests:

```bash
cd backend
python -m pytest tests/ -v
```

Generate test coverage report:

```bash
python -m pytest tests/ --cov=app --cov-report=term-missing
```

### Frontend Tests (Vitest)

Execute the frontend API client tests:

```bash
cd frontend
npm test
```

---

## 📦 Export Formats

LectureForge AI generates artifacts tailored for diverse learning styles:

1. **Academic Markdown (`.md`)**:
   - Ready for Notion, Obsidian, GitHub, or static note sites.
   - Organized into numbered chapters: Executive Overview, Detailed Summary, Concepts, Key Terms, Formulas, Practice Questions, Answer Key, and Audit Report.
   - Interactive checkbox practice questions (`- [ ] **A)** ...`) with separate solutions and reasoning.

2. **Publication-grade PDF (`.pdf`)**:
   - Styled with CSS3 Paged Media via WeasyPrint.
   - Custom formal cover title page, running header, running footer with dynamic page numbering (`Page X of Y`), and code block syntax highlighting.

3. **Anki Flashcards CSV (`.csv`)**:
   - Designed for direct import into [Anki](https://apps.ankiweb.net/).
   - 3-column format: `Front`, `Back`, `Tags`.
   - Practice questions display the prompt and options on the front, with model solutions and reasoning on the back.
   - Glossary items display terms on the front and definitions on the back.
   - Categorized by hierarchical tags: `lectureforge`, `topic::<slug>`, `difficulty::<level>`, `type::<category>`.

---

## ⚙️ Pipeline Configuration

The generation pipeline can be fine-tuned via `.env` settings:

- **Target Chunk Size (`CHUNK_SIZE`)**: Controls the maximum character threshold before splitting a section into contiguous chunks (Default: `2000`).
- **Overlap Window (`CHUNK_OVERLAP`)**: Maintains contextual continuity between adjacent split chunks (Default: `200`).
- **Maximum Self-Correction Retries (`MAX_RETRY_ATTEMPTS`)**: Defines how many automated revision loops the `RetryRouter` can dispatch if a study pack scores below the 4.0/5.0 threshold (Default: `2`).
- **Prompt Registry Version (`PROMPT_VERSION`)**: Enables seamless A/B prompt testing and system versioning (Default: `v1.0`).

---

## 🔧 Troubleshooting

### 1. `Gemini API key not configured` (HTTP 400)
- **Cause**: Generation endpoint was triggered without a configured API key.
- **Fix**: Add your API key to `.env` (`GEMINI_API_KEY=AIzaSy...`) and restart containers:
  ```bash
  docker compose up -d backend celery-worker
  ```

### 2. WeasyPrint Native Library Missing
- **Symptoms**: PDF export returns an error or creates an `.html` fallback file instead of a `.pdf`.
- **Cause**: The host OS lacks Cairo and Pango C libraries.
- **Fix**: When using Docker, WeasyPrint libraries are fully pre-installed in the Docker image. On local host machines, install system packages via your OS package manager (`apt-get install libpango-1.0-0` or `brew install pango`).

### 3. File Upload Rejection (`HTTP 413 Entity Too Large`)
- **Cause**: Uploaded file exceeds `MAX_UPLOAD_SIZE_MB` (default 50MB).
- **Fix**: Increase `MAX_UPLOAD_SIZE_MB=100` in `.env` and restart backend.

### 4. Celery Worker Disconnection
- **Symptoms**: Document status remains stuck on `uploaded` or `parsing`.
- **Fix**: Ensure Redis is running and reachable by inspecting worker logs:
  ```bash
  docker compose logs -f celery-worker
  ```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
