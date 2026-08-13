# 🎬 AI Video Clipper Pipeline (SaaS Backend)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Celery-5.4%2B-green?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-7--alpine-red?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Plataforma backend asíncrona de alto rendimiento diseñada para la ingesta automatizada de videos largos de YouTube (16:9), transcripción precisa palabra por palabra mediante STT local, análisis semántico con LLMs para detección de fragmentos virales (hooks de 30-60s) y reencuadre vertical (9:16) con subtítulos dinámicos usando FFmpeg.

---

## 🏗️ Arquitectura del Sistema

El sistema utiliza el patrón **API REST Síncrona + Workers Asíncronos Desacoplados**. La API responde de inmediato con `202 Accepted` y delega la ejecución pesada a una cadena de tareas orquestadas mediante **Celery Canvas (`chain`)**.

```mermaid
flowchart TD
    Client[Cliente HTTP / Frontend] -->|1. POST /api/v1/jobs| API[FastAPI Web Server]
    API -->|2. Encola Pipeline & Persiste Job| Redis[(Redis Broker / Job Store)]
    API -->|3. Responde 202 Accepted| Client

    subgraph Celery Pipeline [Orquestación Celery Canvas]
        Task1[1. ingest_media_task] -->|audio.wav| Task2[2. transcribe_audio_task]
        Task2 -->|transcript.json| Task3[3. analyze_hook_task]
        Task3 -->|clip_analysis.json| Task4[4. render_clip_task]
    end

    Redis -->|4. Pop Work| Celery Pipeline
    Task1 -->|yt-dlp + FFmpeg| Storage[storage/downloads/{job_id}/]
    Task2 -->|faster-whisper STT| Storage
    Task3 -->|Groq / Gemini API| Storage
    Task4 -->|FFmpeg Crop 9:16 + Subtítulos ASS| FinalClip[final_clip.mp4]
    
    FinalClip -.->|Opcional| Supabase[Supabase Cloud Storage]
```

---

## ⚡ Características Clave

- **Procesamiento Asíncrono No Bloqueante:** Gestión de estados en tiempo real con polling via Redis (`PENDING` $\rightarrow$ `COMPLETED`).
- **Transcripción Local Optimizada:** Integración con `faster-whisper` (CTranslate2) con cuantización `int8` en CPU para timestamps palabra por palabra (*word-level timestamps*).
- **Detección Inteligente de Hooks:** Inferencia con modelos de lenguaje (Groq Llama 3.3 / Gemini Flash) forzando respuestas estructuradas Pydantic/JSON.
- **Renderizado Multimedia Directo:** Motor FFmpeg para recorte dinámico 16:9 a 9:16 y quemado de subtítulos estilo Reels/TikTok (`.ass`).
- **Arquitectura $0 USD:** Diseñado para correr completamente local sobre contenedores Docker sin costos de infraestructura.

---

## 🛠️ Tech Stack

- **Backend Framework:** Python 3.12, FastAPI, Pydantic v2
- **Orquestación Asíncrona:** Celery, Redis
- **Ingesta de Medios:** `yt-dlp`, FFmpeg
- **Speech-to-Text:** `faster-whisper` (CPU int8 / GPU execution)
- **Modelos IA (LLM):** Groq API (`llama-3.3-70b-versatile`), Google AI Studio (`gemini-1.5-flash`)
- **Almacenamiento:** Local Storage System + Supabase Storage API

---

## 🚦 Ciclo de Vida del Job (`JobStatus`)

| Estado | Progreso (%) | Descripción |
| :--- | :---: | :--- |
| `PENDING` | 0% | Tarea creada encolada en Redis. |
| `DOWNLOADING` | 10% | `yt-dlp` descargando video y extrayendo `.wav`. |
| `DOWNLOADED` | 25% | Archivos multimedia listos en almacenamiento local. |
| `TRANSCRIBING` | 35% | `faster-whisper` procesando el audio. |
| `TRANSCRIBED` | 50% | `transcript.json` generado con timestamps a nivel palabra. |
| `ANALYZING` | 65% | Consulta al LLM para identificar el hook viral (30-60s). |
| `ANALYZED` | 75% | Fragmento identificado y validado. |
| `RENDERING` | 85% | FFmpeg aplicando crop 9:16 y subtítulos `.ass`. |
| `COMPLETED` | 100% | Clip final generado listo para distribución (`final_clip.mp4`). |
| `FAILED` | 0% | Manejo de excepción con detalle de error guardado en Redis. |

---

## 📁 Estructura del Repositorio

```
IA_REEL/
├── app/
│   ├── api/                  # Endpoints REST y dependencias
│   │   └── routes/           # Healthcheck y administración de Jobs
│   ├── core/                 # Configuración central (pydantic-settings) y logging
│   ├── models/               # Esquemas Pydantic (domain, analysis, transcription)
│   ├── services/             # Lógica de negocio pura
│   │   ├── ai/               # Detector de Hooks con Groq/Gemini
│   │   ├── media/            # Downloader wrapper de yt-dlp
│   │   ├── render/           # Generador de subtítulos ASS y motor FFmpeg
│   │   └── transcription/    # Servicio STT faster-whisper
│   └── workers/              # Configuración de Celery, tareas atómicas y pipeline
│       └── tasks/            # Ingest, Transcribe, Analyze, Render
├── docker/                   # Dockerfile de worker y docker-compose.yml
├── storage/                  # Almacenamiento local de medios (gitignored)
├── tests/                    # Suite de pruebas unitarias con Pytest
├── .env.example              # Plantilla de variables de entorno
├── requirements.txt          # Dependencias del proyecto
└── README.md
```

---

## 🚀 Guía de Inicio Rápido

### Prerrequisitos

- Python 3.12+
- Docker & Docker Compose
- **FFmpeg** instalado en el sistema (`sudo dnf install ffmpeg` / `sudo apt install ffmpeg`)

### 1. Clonar e Instalar Entorno Local

```bash
git clone [https://github.com/TU_USUARIO/ai-video-clipper-pipeline.git](https://github.com/TU_USUARIO/ai-video-clipper-pipeline.git)
cd ai-video-clipper-pipeline

# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
```

### 2. Iniciar Servicios con Docker y Celery

```bash
# Iniciar contenedor de Redis
docker compose -f docker/docker-compose.yml up -d redis

# Terminal 1: Iniciar API de FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Iniciar Celery Worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=1
```

---

## 📡 Uso de la API REST

### Crear un nuevo Job de Procesamiento

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "[https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)"}'
```

**Respuesta HTTP (`202 Accepted`):**
```json
{
  "id": "e4a2f8b0-1234-4567-89ab-cdef01234567",
  "source_url": "[https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)",
  "status": "pending",
  "progress": 0,
  "message": "Job queued for processing",
  "created_at": "2026-08-13T04:00:00Z"
}
```

### Consultar el Estado del Job

```bash
curl http://localhost:8000/api/v1/jobs/e4a2f8b0-1234-4567-89ab-cdef01234567
```

Documentación interactiva disponible en Swagger UI: `http://localhost:8000/docs`

---

## 🧪 Pruebas Unitarias

La suite de pruebas utiliza mocks para aislar servicios externos (APIs de LLM, descargas e inferencias):

```bash
pytest tests/ -v
```

---

## 🤝 Autor

Desarrollado por **Augusto Enrique Pugliano**  
Estudiante Avanzado de Ingeniería Informática | Backend & AI Software Developer
