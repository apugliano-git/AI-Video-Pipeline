# AI Video Clipper Pipeline

Plataforma backend asíncrona para la ingesta automatizada de videos largos de YouTube (16:9), transcripción precisa palabra por palabra con Speech-to-Text local, análisis semántico con LLMs para detección de fragmentos virales (hooks de 30-60s) y reencuadre vertical (9:16) con subtítulos dinámicos mediante FFmpeg.

---

## Arquitectura del Sistema

El sistema utiliza un patrón de **API REST Síncrona + Workers Asíncronos Desacoplados**. La API responde de inmediato con código `202 Accepted` y delega la ejecución pesada a una cadena de tareas orquestadas mediante Celery Canvas (`chain`).

```mermaid
flowchart TD
    Client[Cliente HTTP / Frontend] -->|1. POST /api/v1/jobs| API[FastAPI Web Server]
    API -->|2. Encola Pipeline & Persiste Job| Redis[(Redis Broker / Job Store)]
    API -->|3. Responde 202 Accepted| Client

    subgraph CeleryPipeline [Orquestación Celery Canvas]
        Task1[1. ingest_media_task] -->|audio.wav| Task2[2. transcribe_audio_task]
        Task2 -->|transcript.json| Task3[3. analyze_hook_task]
        Task3 -->|clip_analysis.json| Task4[4. render_clip_task]
    end

    Redis -->|4. Pop Work| Task1
    Task1 -->|yt-dlp + FFmpeg| Storage[storage/downloads/job_id/]
    Task2 -->|faster-whisper STT| Storage
    Task3 -->|Groq / Gemini API| Storage
    Task4 -->|FFmpeg Crop 9:16 + Subtítulos ASS| FinalClip[final_clip.mp4]

    FinalClip -.->|Opcional| Supabase[Supabase Cloud Storage]
