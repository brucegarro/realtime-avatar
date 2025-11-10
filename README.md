# Realtime Avatar: Multilingual Conversational Avatar System

A low-latency, multilingual conversational avatar system with GPU acceleration that generates realistic talking-head videos using voice cloning and AI animation.

## 🎯 Project Overview

**Current Phase**: Phase 1 (Script → Video MVP) ✅ **+ Ditto Audio-Driven Avatar**  
**Performance**: Sub-10-second video generation on CUDA GPUs (estimated)

This system creates a digital avatar that:
- 🗣️ Speaks in Bruce's cloned voice (multilingual: EN/ZH/ES)
- 🎭 Animates from reference images using **Ditto** (audio-driven LivePortrait)
- ⚡ **Real-time capable** generation with GPU acceleration
- 💰 Scales to zero cost when idle (Cloud Run GPU)
- 🔧 Supports local development (M3 MPS) and cloud production (GCP CUDA)

## 🎬 Avatar Technology: Ditto

**Ditto** (antgroup/ditto-talkinghead) - Audio-driven talking head synthesis framework:
- Built on LivePortrait components (appearance extraction, motion, warping)
- HuBERT audio encoder for speech analysis
- LMDM diffusion model for motion generation
- Real-time capable on modern GPUs (L4, A100, etc.)
- High-quality 1432x1432 output resolution

## 📊 Performance

| Metric | CPU Only | M3 MPS | L4 GPU (Est.) | Improvement |
|--------|----------|---------|---------------|-------------|
| TTS Generation | ~126s | ~2.4s | ~12s | **10x faster** |
| Avatar Generation | N/A | N/A | **<10s** (Ditto) | **Real-time capable** |
| Speed vs Realtime | 27x slower | 0.54x (faster!) | 0.6x (faster!) | **45x improvement** |

**Note:** Ditto performance estimates based on L4 GPU. CPU-only tests: ~2 minutes per 16-second video.

## �📋 Development Phases

- **Phase 1** ✅ **COMPLETE**: Script → Pre-rendered video (GPU accelerated)
- **Phase 2** 🚧 (Next): Semi-interactive chat with response clips
- **Phase 3** 📅 (Future): Real-time WebRTC streaming conversation

## 🏗️ Architecture

```
┌──────────────────────────────────────┐
│  GPU Service (Native, Port 8001)     │
│  - TTS with MPS/CUDA acceleration   │
│  - Ditto Avatar Generation (CUDA)   │
│  - Lip Sync (future)                 │
└──────────────┬───────────────────────┘
               │ HTTP API
┌──────────────▼───────────────────────┐
│  Runtime Service (Docker, Port 8000) │
│  - FastAPI orchestration             │
│  - Business logic                    │
│  - Asset management                  │
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  Evaluator (Automated Testing)       │
│  - Test scenarios                    │
│  - Performance metrics               │
└──────────────────────────────────────┘
```

### Avatar Backends
- **Ditto** (default): Audio-driven, real-time capable, CUDA optimized
- **SadTalker**: Fallback option, MPS compatible
- **LivePortrait**: Video-driven (deprecated - not audio-driven)

### Deployment Modes
- **Local Dev**: Docker runtime + native GPU service (M3 MPS + SadTalker)
- **Production**: Cloud Run + GCP GPU instance (L4 CUDA + Ditto)

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.9+ (for GPU service)
- ffmpeg
- macOS M1/M2/M3 (for local GPU) or Linux

### Setup

1. **Extract voice samples from videos**:
### Local Development (with GPU Acceleration)

1. **Setup GPU service** (for M3 Macs):
```bash
cd runtime
./setup_gpu_service.sh
./run_gpu_service.sh  # Runs in background on port 8001
```

2. **Extract voice samples**:
```bash
./scripts/extract_voice_samples.sh
```

3. **Build Docker images**:
```bash
./scripts/build_images.sh
```

4. **Start runtime service**:
```bash
docker compose up runtime  # Automatically connects to GPU service
```

5. **Test generation**:
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from GPU acceleration!", "language": "en"}'
```

6. **Run evaluator** (optional):
```bash
docker compose --profile evaluator up evaluator
```

Or use the all-in-one setup script:
```bash
./scripts/setup_local.sh
```

### Without GPU (CPU only)

Set `USE_EXTERNAL_GPU_SERVICE=false` in `docker-compose.yml` to run TTS in Docker (slower).

## 📁 Project Structure

```
realtime-avatar/
├── assets/                  # Reference media
│   ├── images/             # Avatar reference images
│   ├── videos/             # Reference motion videos
│   └── voice/              # Voice samples for cloning
├── runtime/                 # Main inference service
│   ├── models/             # Model wrappers (TTS, Avatar, ASR, LLM)
│   │   └── tts_client.py   # GPU service client
│   ├── pipelines/          # Generation pipelines
│   ├── utils/              # Utilities
│   ├── gpu_service.py      # GPU acceleration service (NEW)
│   ├── GPU_SERVICE.md      # GPU service documentation
│   └── app.py              # FastAPI application
├── evaluator/              # Testing & metrics
│   ├── scenarios/          # Test scenarios
│   ├── metrics/            # Metric calculators
│   └── run_evaluator.py    # Main runner
├── web/                    # React UI (stub)
├── infrastructure/         # Terraform (stub)
└── scripts/                # Utility scripts
```

## 🔬 Testing & Evaluation

The evaluator runs automated tests and generates metrics:
- ✅ English short/medium utterances
- ✅ Chinese (Mandarin) short/medium
- ✅ Spanish short/medium
- ✅ Language switching (EN→ZH, EN→ES, EN→ZH→ES)

### Metrics Collected
- **Latency**: TTS time, avatar rendering time, total time
- **Voice Quality**: Speaker similarity, F0/pitch analysis
- **Language**: Detection accuracy, correctness
- **Lip Sync**: Audio-video coherence (basic heuristic)

### Run Evaluator
```bash
docker compose --profile evaluator up evaluator
```

Results are saved to `evaluator/outputs/` as JSON files.

## 🎨 API Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### Generate Video
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! I am Bruce'\''s digital avatar.",
    "language": "en",
    "reference_image": "bruce_neutral.jpg"
  }'
```

### Download Generated Video
```bash
curl http://localhost:8000/api/v1/videos/{filename} -o output.mp4
```

## 🛠️ Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| **TTS** | XTTS-v2 | Multilingual voice cloning |
| **Avatar** | LivePortrait | Single-image animation (placeholder) |
| **ASR** | faster-whisper | Phase 3 |
| **LLM** | Qwen-2.5 | Phase 2+ |
| **API** | FastAPI | Python async |
| **Container** | Docker | CPU (local) / GPU (prod) |
| **Orchestration** | Docker Compose | Local dev |
| **Cloud** | GCP Cloud Run GPU | Production |

## 🎯 Performance Targets

- **Resolution**: 256p-360p (latency > quality)
- **FPS**: 25-30
- **Latency** (Phase 3): 450-900ms end-to-end
- **Cost**: < $100/month with scale-to-zero

## 🔧 Configuration

Edit `.env` file (copy from `.env.example`):

```bash
MODE=local          # local or production
DEVICE=cpu          # cpu or cuda
LOG_LEVEL=info
DEFAULT_REFERENCE_IMAGE=bruce_neutral.jpg
```

## 📊 Development Status

### ✅ Completed (Phase 1)
- [x] Project structure and Docker setup
- [x] Runtime service with FastAPI
- [x] XTTS-v2 TTS integration
- [x] Basic avatar animation (placeholder)
- [x] Phase 1 pipeline (script → video)
- [x] Evaluator with test scenarios
- [x] Metrics collection framework
- [x] Voice sample extraction

### 🚧 In Progress
- [ ] LivePortrait full integration
- [ ] Voice quality optimization
- [ ] Model download automation

### 📅 Planned (Phase 2)
- [ ] Qwen LLM integration
- [ ] Semi-interactive chat pipeline
- [ ] React web UI
- [ ] Cloud deployment (Terraform)

### 📅 Planned (Phase 3)
- [ ] faster-whisper ASR
- [ ] Real-time streaming
- [ ] WebRTC integration
- [ ] Production optimization

## 📝 Notes

### Model Downloads
On first run, XTTS-v2 models (~2GB) will be downloaded automatically. This may take several minutes.

### Voice Samples
Voice reference samples are extracted from the video files in `assets/videos/`. Ensure videos contain clear speech in each language (EN/ZH/ES).

### LivePortrait
Current implementation uses a simple video generation as a placeholder. Full LivePortrait integration requires:
- Cloning the LivePortrait repository
- Downloading pre-trained models
- GPU for acceptable performance

## 🤝 Contributing

This is a personal project following the specification in `PROJECT_SPEC.md`.

## 📄 License

Private project - All rights reserved.

---

**Last Updated**: November 6, 2025
**Phase**: 1 (MVP)
**Status**: Development
