# Getting Started with Realtime Avatar

## 🎉 Project Scaffolded Successfully!

Your Realtime Avatar project is now ready for development. Here's what has been created:

### ✅ What's Ready

1. **Runtime Service** (`runtime/`)
   - FastAPI application with health check and generation endpoints
   - XTTS-v2 TTS model wrapper for multilingual voice cloning
   - LivePortrait avatar animation wrapper (placeholder implementation)
   - Phase 1 pipeline: Script → TTS → Avatar → Video
   - Docker configuration for local CPU development

2. **Evaluator** (`evaluator/`)
   - Test scenarios for Phase 1 (EN/ZH/ES short & medium)
   - Language switching tests
   - Metrics collection: latency, voice quality, language, lip sync
   - Automated test runner with JSON output

3. **Assets** (`assets/`)
   - ✅ Reference images: `bruce_neutral.jpg`, `bruce_smiling.jpg`
   - ✅ Reference videos: English, Mandarin, Spanish, Expressive Motion
   - 📁 Voice samples directory (to be extracted)

4. **Infrastructure**
   - Docker Compose setup for local development
   - Utility scripts for setup and building
   - Configuration templates

## 🚀 Next Steps

### 1. Extract Voice Samples (Required!)
Before first run, extract audio samples from your videos:

```bash
./scripts/extract_voice_samples.sh
```

This creates WAV files in `assets/voice/reference_samples/` for XTTS-v2 voice cloning.

### 2. Build Docker Images
```bash
./scripts/build_images.sh
```

Or use the full setup script:
```bash
./scripts/setup_local.sh
```

### 3. Start the Runtime Service
```bash
docker compose up runtime
```

**First run will take 10-15 minutes** to download XTTS-v2 models (~2GB).

Watch logs for:
```
INFO - XTTS-v2 model loaded in X.XXs
INFO - Phase 1 pipeline ready in X.XXs
```

### 4. Test the API
Once runtime is healthy, test it:

```bash
# Health check
curl http://localhost:8000/health

# Generate a video
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! I am Bruce'\''s digital avatar.",
    "language": "en",
    "reference_image": "bruce_neutral.jpg"
  }'
```

### 5. Run the Evaluator
In another terminal:

```bash
docker compose --profile evaluator up evaluator
```

This runs all test scenarios and saves results to `evaluator/outputs/`.

## 📊 Expected First Run Timeline

1. **Setup** (~5 min)
   - Extract voice samples: ~1 min
   - Build Docker images: ~3-5 min

2. **First Runtime Start** (~10-15 min)
   - Download XTTS-v2 models: ~5-10 min
   - Model initialization: ~2-3 min
   - Container startup: ~1 min

3. **First Generation** (~30-60 sec for short text)
   - TTS synthesis: ~5-15 sec
   - Avatar rendering: ~20-40 sec
   - Total: ~30-60 sec (CPU mode)

4. **Evaluator Run** (~10-20 min for all scenarios)
   - 6 Phase 1 tests
   - 3 Language switching tests
   - ~1-2 min per test

## 🔧 Troubleshooting

### Models Not Downloading
If XTTS-v2 models fail to download:
- Check internet connection
- Models cache to `/root/.cache/tts_models` (Docker volume)
- Try restarting the container

### Out of Memory
If you see OOM errors:
- XTTS-v2 requires ~4-6GB RAM in CPU mode
- Increase Docker memory limit (Docker Desktop → Resources)
- Or reduce batch size in config

### Slow Generation
CPU mode is intentionally slower:
- Short text (1-2s audio): ~30-60 sec generation
- Medium text (5-8s audio): ~2-3 min generation
- This is normal for Phase 1 MVP
- GPU mode will be ~10x faster

### FFmpeg Errors
If you see ffmpeg errors:
```bash
# Test ffmpeg in container
docker compose exec runtime ffmpeg -version
```

## 🎯 Development Workflow

### Normal Development Cycle

1. **Start runtime in background**:
```bash
docker compose up -d runtime
```

2. **Watch logs**:
```bash
docker compose logs -f runtime
```

3. **Make code changes** in `runtime/` (auto-reload enabled)

4. **Test changes**:
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Test message", "language": "en"}'
```

5. **Run evaluator to verify**:
```bash
docker compose --profile evaluator up evaluator
```

### Stop Services
```bash
docker compose down
```

### Clean Rebuild
```bash
docker compose down -v  # Remove volumes
./scripts/build_images.sh
docker compose up runtime
```

## 📝 What's Missing (To Do)

### Phase 1 Completion
1. **LivePortrait Integration**
   - Current: Simple static image → video placeholder
   - Todo: Full LivePortrait model integration
   - Requires: Clone repo, download models, test on CPU

2. **Voice Sample Optimization**
   - Experiment with different audio clip lengths (5s, 10s, 15s)
   - Try different parts of the videos (emotional, clear speech)
   - A/B test voice similarity

3. **Model Download Automation**
   - Pre-download models during Docker build
   - Or create setup script to cache models

4. **Performance Optimization**
   - Profile TTS and avatar rendering
   - Identify bottlenecks
   - Consider model quantization

### Phase 2 (Future)
- Qwen LLM integration for conversational responses
- React web UI
- Semi-interactive chat pipeline
- Terraform for GCP deployment

### Phase 3 (Future)
- faster-whisper ASR
- Real-time streaming
- WebRTC integration

## 📚 Key Files to Know

| File | Purpose |
|------|---------|
| `runtime/app.py` | Main FastAPI application |
| `runtime/models/tts.py` | XTTS-v2 voice cloning |
| `runtime/models/avatar.py` | LivePortrait animation |
| `runtime/pipelines/phase1_script.py` | Script → video pipeline |
| `runtime/config.py` | Configuration management |
| `evaluator/run_evaluator.py` | Test runner |
| `docker-compose.yml` | Service orchestration |
| `.env` | Local configuration |

## 🆘 Getting Help

1. Check logs: `docker compose logs runtime`
2. Review error messages in evaluator outputs
3. Test components individually (TTS, avatar separately)
4. Refer to PROJECT_SPEC.md for architecture details

## 🎉 You're All Set!

Run the setup script and start developing:

```bash
./scripts/setup_local.sh
docker compose up runtime
```

Then in another terminal:
```bash
docker compose --profile evaluator up evaluator
```

Check `evaluator/outputs/` for test results!

---

**Happy coding! 🚀**
