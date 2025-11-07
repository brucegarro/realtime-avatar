# GPU Acceleration Service

## Overview

The GPU Service is a standalone ML inference service that handles GPU-accelerated tasks:
- **TTS (XTTS-v2)** - Text-to-speech with voice cloning
- **Video Generation (LivePortrait)** - Coming in Phase 2
- **Lip Sync** - Coming in Phase 2

## Architecture

```
┌─────────────────────────────────────────┐
│  GPU Service (Port 8001)                │
│  ├── Runs on host (local or remote)    │
│  ├── Uses MPS (M3) or CUDA (GCP)      │
│  └── Serves ML inference via HTTP      │
└─────────────────────────────────────────┘
           ↓ HTTP API
┌─────────────────────────────────────────┐
│  Runtime Service (Docker, Port 8000)    │
│  ├── Orchestrates requests             │
│  ├── Handles business logic            │
│  └── Assembles final outputs           │
└─────────────────────────────────────────┘
```

## Deployment Modes

### Local Development (Mac M3)
- GPU Service runs **natively** on macOS with MPS acceleration
- Runtime runs in Docker
- **5-10x faster** than CPU-only Docker

### Remote Development/Production (GCP)
- GPU Service runs on GPU instance (CUDA)
- Runtime runs on Cloud Run
- Same architecture, different hardware

## Quick Start (Local M3)

### 1. Setup GPU Service

```bash
cd runtime
./setup_gpu_service.sh
```

This will:
- Create Python virtual environment
- Install dependencies
- Check MPS availability

### 2. Start GPU Service

```bash
cd runtime
./run_gpu_service.sh
```

Service will start on `http://localhost:8001`

### 3. Start Runtime (Docker)

```bash
# In another terminal
docker compose up runtime
```

Runtime will automatically connect to GPU service on localhost:8001

### 4. Test the System

```bash
# Check GPU service health
curl http://localhost:8001/health

# Check runtime health
curl http://localhost:8000/health

# Generate a video (runtime will call GPU service for TTS)
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from M3 GPU!", "language": "en"}'
```

## API Endpoints

### GPU Service (Port 8001)

#### `GET /health`
Check service health and device info

Response:
```json
{
  "status": "healthy",
  "device": "mps",
  "capabilities": {
    "mps": true,
    "cuda": false
  },
  "models": {
    "tts": true,
    "video": false,
    "lipsync": false
  }
}
```

#### `POST /tts/generate`
Generate audio from text

Request:
```json
{
  "text": "Hello world",
  "language": "en",
  "speaker_wav": null
}
```

Response:
```json
{
  "success": true,
  "audio_path": "/tmp/gpu-service-output/tts_1234567890.wav",
  "duration_s": 2.5,
  "generation_time_ms": 1200
}
```

#### `POST /video/generate` (Future)
Generate talking head video

Request:
```json
{
  "audio_path": "/path/to/audio.wav",
  "reference_image": "/path/to/image.jpg",
  "mode": "liveportrait"
}
```

## Performance

### Expected Speedup (M3 with MPS vs CPU)

| Task | CPU Time | MPS Time | Speedup |
|------|----------|----------|---------|
| TTS (4s audio) | ~120s | ~12-24s | **5-10x** |
| Video Gen (future) | ~60s | ~6-12s | **5-10x** |

### Benchmarking

Run the evaluator to measure performance:

```bash
# With GPU service running
docker compose --profile evaluator run --rm evaluator
```

Compare results in `evaluator/outputs/summary_report_*.json`

## Configuration

### Environment Variables

```bash
# GPU Service
export HOST=0.0.0.0  # Listen on all interfaces
export PORT=8001     # Service port

# Runtime (to use GPU service)
export GPU_SERVICE_URL=http://localhost:8001  # Local
# OR
export GPU_SERVICE_URL=http://gpu-instance-ip:8001  # Remote
```

### Remote GPU Instance (GCP)

To run on a remote GPU instance:

1. **Deploy GPU Service:**
```bash
# On GCP GPU instance
scp -r runtime/ user@gpu-instance:/app/
ssh user@gpu-instance
cd /app/runtime
./setup_gpu_service.sh
./run_gpu_service.sh
```

2. **Update Runtime:**
```bash
# In docker-compose.yml or .env
GPU_SERVICE_URL=http://gpu-instance-internal-ip:8001
```

3. **Deploy Runtime:**
```bash
docker compose up runtime
```

## Development Workflow

### Adding New GPU Tasks

1. **Add model to `gpu_service.py`:**
```python
# Initialize in startup()
lipsync_model = LipSyncModel()
lipsync_model.device = device
lipsync_model.initialize()

# Add endpoint
@app.post("/lipsync/generate")
async def generate_lipsync(request: LipSyncRequest):
    # Implementation
```

2. **Update runtime to call new endpoint:**
```python
# In runtime/models/
response = requests.post(
    f"{GPU_SERVICE_URL}/lipsync/generate",
    json={"video": video_path}
)
```

### Testing Locally

```bash
# Terminal 1: GPU service
cd runtime
./run_gpu_service.sh

# Terminal 2: Runtime
docker compose up runtime

# Terminal 3: Test
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Test", "language": "en"}'
```

## Troubleshooting

### GPU Service Won't Start

**MPS not available:**
```
⚠️  MPS not available - will use CPU (slower)
```
- Check macOS version (requires macOS 12.3+)
- Check PyTorch version (requires 2.0+)
- Try: `python3 -c "import torch; print(torch.backends.mps.is_available())"`

**Dependencies missing:**
```
❌ Error: Module not found
```
- Run: `./setup_gpu_service.sh` again
- Activate venv: `source venv_gpu/bin/activate`

### Runtime Can't Connect to GPU Service

**Connection refused:**
```
Failed to connect to GPU service at http://localhost:8001
```
- Check GPU service is running: `curl http://localhost:8001/health`
- Check firewall settings
- Verify GPU_SERVICE_URL environment variable

### Slow Performance

**Still slow with MPS:**
- Check actual device: `curl http://localhost:8001/health | jq .device`
- Should show `"mps"` not `"cpu"`
- Check logs for device initialization messages

## Future Enhancements

### Phase 2
- [ ] LivePortrait integration for video generation
- [ ] Lip sync refinement
- [ ] Model caching optimization

### Phase 3
- [ ] Real-time streaming support
- [ ] WebRTC integration
- [ ] Multi-GPU support

## File Structure

```
runtime/
├── gpu_service.py              # Main GPU service
├── gpu_service_requirements.txt # Dependencies
├── setup_gpu_service.sh        # Setup script
├── run_gpu_service.sh          # Run script
├── venv_gpu/                   # Virtual environment (created)
└── models/                     # Shared model code
    ├── tts.py
    ├── avatar.py (future)
    └── lipsync.py (future)
```

## Related Documentation

- [PROJECT_SPEC.md](../PROJECT_SPEC.md) - Overall architecture
- [EVALUATION_RESULTS.md](../EVALUATION_RESULTS.md) - Performance benchmarks
- [DEVELOPMENT.md](../DEVELOPMENT.md) - Development guide
