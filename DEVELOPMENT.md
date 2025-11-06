# Development Guide

## 🛠️ Development Setup (Complete!)

Your environment is ready! All checks passed:
- ✅ Docker and Docker Compose installed
- ✅ FFmpeg available
- ✅ Project structure created
- ✅ Assets organized (images + videos)
- ✅ Voice samples extracted (EN/ZH/ES)

## 📦 Building the Project

### Quick Start (Recommended)
```bash
# Build and start everything
./scripts/build_images.sh
docker compose up runtime

# In another terminal, run evaluator
docker compose --profile evaluator up evaluator
```

### Manual Build
```bash
# Build runtime image
docker build -t realtime-avatar-runtime:latest ./runtime

# Build evaluator image  
docker build -t realtime-avatar-evaluator:latest ./evaluator

# Start services
docker compose up
```

## 🧪 Testing the Runtime

### 1. Start Runtime Service
```bash
docker compose up runtime
```

**Expected output:**
```
runtime  | INFO - Starting Realtime Avatar Runtime in local mode on cpu
runtime  | INFO - Loading XTTS-v2 model on cpu...
runtime  | INFO - XTTS-v2 model loaded in X.XXs
runtime  | INFO - Avatar model loaded in X.XXs
runtime  | INFO - Phase 1 pipeline ready in X.XXs
runtime  | INFO - Uvicorn running on http://0.0.0.0:8000
```

**First run:** XTTS-v2 models (~2GB) will download automatically. This takes 5-10 minutes.

### 2. Test Health Endpoint
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "mode": "local",
  "device": "cpu",
  "models_loaded": true
}
```

### 3. Generate Your First Video
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! I am Bruce'\''s digital avatar speaking in English.",
    "language": "en",
    "reference_image": "bruce_neutral.jpg"
  }'
```

Expected response:
```json
{
  "job_id": "20251106_120000_abc12345",
  "status": "completed",
  "message": "Video generated successfully",
  "video_url": "/api/v1/videos/20251106_120000_abc12345_video.mp4",
  "metadata": {
    "duration_ms": 12500,
    "tts_ms": 8200,
    "avatar_ms": 4300,
    "language": "en",
    "audio_duration_s": 3.2
  }
}
```

### 4. Download Generated Video
```bash
# Using the video_url from response
curl http://localhost:8000/api/v1/videos/20251106_120000_abc12345_video.mp4 \
  -o my_first_avatar.mp4

# Open the video
open my_first_avatar.mp4  # macOS
```

### 5. Test Other Languages

**Chinese:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好！我是布鲁斯的数字化身，用中文说话。",
    "language": "zh-cn",
    "reference_image": "bruce_smiling.jpg"
  }'
```

**Spanish:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "¡Hola! Soy el avatar digital de Bruce hablando en español.",
    "language": "es",
    "reference_image": "bruce_neutral.jpg"
  }'
```

## 🔬 Running the Evaluator

### Run All Tests
```bash
docker compose --profile evaluator up evaluator
```

This runs:
- 6 Phase 1 tests (EN/ZH/ES short & medium)
- 3 Language switching tests

### Expected Timeline
- Total: ~10-20 minutes
- Per test: ~1-2 minutes (CPU mode)

### View Results
```bash
# List all results
ls -lh evaluator/outputs/

# View latest summary
cat evaluator/outputs/summary_report_*.json | jq .

# View specific test result
cat evaluator/outputs/20251106_*.json | jq .
```

### Example Output
```json
{
  "scenario_id": "en_short",
  "status": "success",
  "metrics": {
    "tts_ms": 5200,
    "avatar_render_ms": 18400,
    "total_generation_ms": 23600,
    "audio_duration_s": 2.3,
    "language_correctness_1_1": 1,
    "speaker_similarity": 0.78
  }
}
```

## 🔧 Development Workflow

### Hot Reload Development
The runtime service supports hot reload in local mode:

1. **Start runtime with reload**:
```bash
docker compose up runtime
# Automatically restarts on code changes in runtime/
```

2. **Edit code** in `runtime/` directory

3. **Test immediately** - changes apply automatically

### Debugging

**View logs:**
```bash
# Follow runtime logs
docker compose logs -f runtime

# Follow evaluator logs
docker compose logs -f evaluator

# All logs
docker compose logs -f
```

**Enter container:**
```bash
# Runtime container
docker compose exec runtime bash

# Check Python environment
docker compose exec runtime python --version
docker compose exec runtime pip list
```

**Test individual components:**
```bash
# Test TTS only
docker compose exec runtime python -c "
from models.tts import get_xtts_model
model = get_xtts_model()
model.initialize()
print('TTS ready!')
"

# Test avatar only
docker compose exec runtime python -c "
from models.avatar import get_avatar_model
model = get_avatar_model()
model.initialize()
print('Avatar ready!')
"
```

## 📊 Performance Expectations (CPU Mode)

### Generation Times
| Text Length | Audio Duration | Generation Time |
|-------------|---------------|-----------------|
| Short (1-2s) | ~2s | ~30-60s |
| Medium (5-8s) | ~7s | ~2-3 min |
| Long (10-15s) | ~12s | ~4-6 min |

### Breakdown
- **TTS**: 20-40% of total time
- **Avatar**: 60-80% of total time
- **Overhead**: ~5%

### GPU Mode (Future)
Expected ~10x speedup:
- Short: ~3-6s
- Medium: ~12-18s
- Long: ~25-40s

## 🐛 Troubleshooting

### Models Not Downloading
**Problem:** XTTS-v2 download fails or stalls

**Solution:**
```bash
# Check internet connection
# Restart with verbose logging
docker compose down
docker compose up runtime | grep -i download

# Manual model download (inside container)
docker compose exec runtime python -c "
from TTS.api import TTS
tts = TTS('tts_models/multilingual/multi-dataset/xtts_v2')
print('Downloaded!')
"
```

### Out of Memory
**Problem:** Container crashes with OOM

**Solution:**
```bash
# Increase Docker memory limit
# Docker Desktop → Preferences → Resources → Memory
# Increase to at least 8GB

# Or reduce batch size in config.py
```

### Slow Generation
**Problem:** Generation takes very long

**Expected:** CPU mode IS slow (30-60s for short text)

**Improvements:**
1. Use smaller XTTS model (if available)
2. Reduce video resolution in config.py
3. Skip evaluator and test individual requests
4. Wait for GPU deployment (10x faster)

### FFmpeg Errors
**Problem:** Video generation fails with ffmpeg error

**Solution:**
```bash
# Check ffmpeg in container
docker compose exec runtime ffmpeg -version

# Check video codec support
docker compose exec runtime ffmpeg -codecs | grep h264

# Try different codec in models/avatar.py
# Change 'libx264' to 'mpeg4'
```

### Port Already in Use
**Problem:** Port 8000 already in use

**Solution:**
```bash
# Check what's using port 8000
lsof -i :8000

# Kill the process or change port in docker-compose.yml
# Edit docker-compose.yml: "8001:8000"
```

## 📝 Next Development Tasks

### Priority 1: Core Functionality
- [ ] Test TTS with all 3 languages
- [ ] Verify voice similarity is acceptable
- [ ] Experiment with different voice samples
- [ ] Tune avatar video quality

### Priority 2: LivePortrait Integration
- [ ] Clone LivePortrait repository
- [ ] Download pre-trained models
- [ ] Test on sample image + audio
- [ ] Integrate into avatar.py
- [ ] Compare with current placeholder

### Priority 3: Optimization
- [ ] Profile TTS generation time
- [ ] Profile avatar rendering time
- [ ] Identify bottlenecks
- [ ] Consider model quantization
- [ ] Cache frequently used generations

### Priority 4: Features
- [ ] Add video duration estimation
- [ ] Add progress callbacks
- [ ] Support batch generation
- [ ] Add video preview endpoint
- [ ] Improve error messages

## 🚀 Moving to Phase 2

Once Phase 1 is stable:

1. **LLM Integration**
   - Add Qwen-2.5 model
   - Create conversational prompts
   - Test response generation

2. **Web UI**
   - Build React interface
   - Add chat-style interaction
   - Display avatar videos

3. **Cloud Deployment**
   - Set up GCP Cloud Run
   - Configure GPU runtime
   - Deploy with Terraform

## 📚 Useful Commands

```bash
# Stop all services
docker compose down

# Clean restart
docker compose down -v
docker compose up --build

# View resource usage
docker stats

# Clean up old containers
docker system prune -a

# Backup outputs
tar -czf outputs_backup.tar.gz evaluator/outputs/

# Export environment
docker compose config > docker-compose-resolved.yml
```

## 🎯 Success Criteria

Your Phase 1 MVP is ready when:
- ✅ TTS generates clear audio in all 3 languages
- ✅ Voice sounds similar to reference samples
- ✅ Avatar video syncs reasonably with audio
- ✅ Generation completes without errors
- ✅ Evaluator runs successfully
- ✅ All metrics are within acceptable ranges

Current status: **Ready to test! 🎉**
