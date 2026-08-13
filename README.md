# AI Video Clipper Pipeline

SaaS backend for automated video clipping: ingest YouTube URLs, transcribe with Whisper, detect viral hooks with LLM, and render vertical clips with FFmpeg.

## Phase 1 — Ingesta ✅

- FastAPI REST API
- Celery + Redis async job queue
- yt-dlp media download + audio extraction

## Phase 2 — Transcripción ✅

- faster-whisper (CPU-efficient, word-level timestamps)
- Celery chain: `ingest → transcribe`
- Output: `storage/downloads/{job_id}/transcript.json`

## Quick Start

### Prerequisites

- Python 3.12+
- FFmpeg (`sudo dnf install ffmpeg` on Fedora)
- Docker & Docker Compose

### Setup

```bash
# Clone and enter project
cd IA_REEL

# Virtual environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env

# Start Redis
docker compose -f docker/docker-compose.yml up -d redis

# Terminal 1 — API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Celery worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=1
```

### API Usage

```bash
# Submit a job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Poll status
curl http://localhost:8000/api/v1/jobs/{job_id}
```

Interactive docs: http://localhost:8000/docs

## Project Structure

```
app/
├── api/routes/       # HTTP endpoints
├── core/             # Config, logging
├── models/           # Schemas & domain enums
├── services/         # Business logic (downloader, job store)
├── workers/          # Celery app & tasks
└── main.py           # FastAPI entry
docker/               # Docker Compose & worker image
storage/              # Local media (gitignored)
```

## Roadmap

| Week | Milestone |
|------|-----------|
| 1 | Ingesta + Celery + Redis ✅ |
| 2 | Whisper transcription + word timestamps ✅ |
| 3 | LLM hook detection (Groq/Gemini) |
| 4 | FFmpeg crop 9:16 + ASS subtitles + Supabase |
