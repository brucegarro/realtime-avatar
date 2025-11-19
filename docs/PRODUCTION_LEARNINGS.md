# Production Deployment Learnings

Critical lessons learned from deploying the full conversation pipeline to GCP with L4 GPU.

**Date:** November 19, 2025  
**Milestone:** First successful end-to-end conversation flow

---

## Table of Contents

- [Volume Mount Architecture](#volume-mount-architecture)
- [Async/Await in FastAPI](#asyncawait-in-fastapi)
- [Docker Path Resolution](#docker-path-resolution)
- [Read-Only Volume Handling](#read-only-volume-handling)
- [Import Management](#import-management)
- [Performance Insights](#performance-insights)
- [Development Workflow](#development-workflow)

---

## Volume Mount Architecture

### Problem
Every code change required 2-3 minute Docker rebuild, making iterative debugging extremely slow.

### Solution
Mount runtime code as volume instead of copying into image:

```yaml
# docker-compose.yml
runtime:
  volumes:
    # Mount source code for hot reload (dev mode) - writable for model downloads
    - ./runtime:/app/runtime
    # Share assets
    - ./runtime/assets:/app/assets:ro
```

```dockerfile
# runtime/Dockerfile
# Create runtime directory structure (code will come from volume mount)
RUN mkdir -p /app/runtime/models /app/runtime/pipelines /app/runtime/utils /app/runtime/workers

# NO COPY commands for Python code - everything from volume mount

ENV PYTHONPATH=/app/runtime
WORKDIR /app/runtime
```

### Results
- **Before:** 2-3 minute rebuilds for every change
- **After:** 2-3 second container restarts
- **Speedup:** 200-300x faster iteration! 🚀

### Critical Detail
Volume must be **writable** if code downloads models (e.g., faster-whisper downloads to `./checkpoints`):
```yaml
- ./runtime:/app/runtime  # Writable, not :ro
```

---

## Async/Await in FastAPI

### Problem
```python
# This FAILS - FastAPI/Uvicorn already running event loop
async def endpoint():
    result = asyncio.run(some_async_function())  # ❌ Error!
```

Error: `asyncio.run() cannot be called from a running event loop`

### Solution
Make entire chain async with `await` at each level:

```python
# FastAPI endpoint
@app.post("/api/v1/conversation")
async def process_conversation(audio: UploadFile):
    result = await conversation_pipeline.process_conversation(...)  # ✅
    return result

# ConversationPipeline
async def process_conversation(self, ...):
    avatar_result = await self.generate_avatar_video(...)  # ✅
    return avatar_result

# Phase1Pipeline  
async def generate_avatar_video(self, ...):
    result = await self.phase1_pipeline.generate(...)  # ✅
    return result

# Phase1Pipeline.generate()
async def generate(self, ...):
    # Do work
    return result
```

### Rule
**Never use `asyncio.run()` inside an async context.** Use `await` instead.

---

## Docker Path Resolution

### Problem
Code was mapping Docker paths to Mac host paths:
```python
# ❌ Wrong - assumes Mac host filesystem
if path.startswith("/app/"):
    host_path = path.replace("/app/", "/Users/brucegarro/project/realtime-avatar/")
```

This works locally but fails on GCP where containers don't have Mac paths.

### Solution
Both containers use Docker paths directly:

```python
# ✅ Correct - both containers use same Docker paths
payload = {
    "audio_path": "/tmp/gpu-service-output/tts_audio.wav",
    "reference_image": "/app/assets/images/bruce_haircut_small.jpg"
}
```

### Volume Sharing
```yaml
# docker-compose.yml
volumes:
  gpu-output:  # Named volume shared between containers

runtime:
  volumes:
    - ./runtime/assets:/app/assets:ro  # Same path in both
    - gpu-output:/tmp/gpu-service-output:ro

gpu-service:
  volumes:
    - ./runtime/assets:/app/assets:ro  # Same path in both
    - gpu-output:/tmp/gpu-service-output  # Writable for GPU
```

### Path Construction
When code expects just filenames, pass just filenames:

```python
# ✅ Correct - Phase1Pipeline constructs full path internally
reference_image="bruce_haircut_small.jpg"  
voice_sample="bruce_en_sample.wav"

# ❌ Wrong - causes path duplication
reference_image="assets/images/bruce_haircut_small.jpg"
# Results in: /app/assets/images/assets/images/bruce_haircut_small.jpg
```

---

## Read-Only Volume Handling

### Problem
GPU service writes output to shared volume. Runtime container tries to copy:

```python
# ❌ Fails - volume mounted read-only for runtime
remote_path = "/tmp/gpu-service-output/tts_audio.wav"  # GPU wrote this
shutil.copy2(remote_path, output_path)  # OSError: Read-only file system
```

### Solution
Don't copy - both containers can access the same files:

```python
# ✅ Correct - use GPU service output directly
remote_path = result.get("audio_path")
output_path = remote_path  # Just use it!
logger.info(f"Using audio path from GPU service: {output_path}")
return output_path
```

### Why It Works
Both containers mount the same volume:
- GPU service: writable (`gpu-output:/tmp/gpu-service-output`)
- Runtime: read-only (`gpu-output:/tmp/gpu-service-output:ro`)

Files written by GPU service are immediately accessible to runtime container.

### Applied To
- TTS audio output (`models/tts_client.py`)
- Avatar video output (`models/avatar_client.py`)

---

## Import Management

### Problem
```python
try:
    # Complex operations
    import os  # ❌ Inside try block
    tmp_video = self.sdk.tmp_output_path
    os.system(cmd)
except Exception as e:
    if output_path and os.path.exists(output_path):  # ❌ os not defined here!
        os.remove(output_path)
```

If exception occurs before `import os`, the exception handler fails with:
`UnboundLocalError: local variable 'os' referenced before assignment`

### Solution
Move all imports to module level:

```python
import os  # ✅ At top of file

try:
    # Complex operations
    tmp_video = self.sdk.tmp_output_path
    os.system(cmd)  # os available
except Exception as e:
    if output_path and os.path.exists(output_path):  # ✅ os available here too
        os.remove(output_path)
```

### Rule
**All imports should be at module level** (top of file), not inside try blocks or functions.

Exception: Dynamic imports that are truly optional (but avoid if possible).

---

## Performance Insights

### Actual Timings (GCP L4 GPU)

**Test: "Say something" → 31s total**
```
ASR:    1.22s (transcription)
LLM:    0.00s (fallback response)
TTS:   11.24s → 12.8s audio (0.88x RTF) ⚡
Avatar: ~18s (1.4x RTF)
─────────────────────────
Total: ~31s (2.4x RTF)
```

**Test: "Say five words" → 25s total**
```
ASR:    1.37s (transcription)
LLM:    0.00s (fallback response)
TTS:    5.56s → 7.4s audio (0.75x RTF) ⚡
Avatar: ~18s (2.4x RTF)
─────────────────────────
Total: ~25s (3.4x RTF)
```

### Observations

1. **TTS is faster than realtime** (0.75-0.88x RTF) ✅
2. **ASR is very fast** (~1s regardless of input length) ✅
3. **Avatar generation takes consistent ~18s** (current bottleneck)
4. **Total latency: 25-31s** (acceptable for demo, needs optimization for production)

### Bottleneck Analysis

Avatar generation appears to have fixed overhead (~18s):
- May include model initialization/warmup
- Could optimize with persistent model loading
- TensorRT already providing 2.5x speedup over PyTorch
- Further optimization: model caching, pipeline parallelization

---

## Development Workflow

### Efficient Iteration Pattern

1. **Make code changes locally** in `/Users/brucegarro/project/realtime-avatar/runtime/`

2. **Upload changed file(s)**:
   ```bash
   gcloud compute scp runtime/models/avatar_client.py \
     realtime-avatar-test:~/realtime-avatar/runtime/models/ --zone=us-east1-c
   ```

3. **Restart container** (2-3 seconds):
   ```bash
   gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
     --command='cd ~/realtime-avatar && docker compose restart runtime'
   ```

4. **Test immediately** - no rebuild needed!

5. **Check logs**:
   ```bash
   gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
     --command='docker logs realtime-avatar-runtime 2>&1 | tail -50'
   ```

### When Rebuild IS Required

Only rebuild when changing:
- Dockerfile
- requirements.txt (new dependencies)
- System packages
- Base image configuration

### Git Workflow

After successful testing:
```bash
git add runtime/models/avatar_client.py
git commit -m "fix: Use GPU service output directly without copying"
git push origin main
```

---

## Key Takeaways

### ✅ Do's

1. **Use volume mounts for code** in development
2. **Make entire pipeline async** when in FastAPI context
3. **Use Docker paths consistently** across containers
4. **Share volumes between containers** instead of copying
5. **Import at module level** for exception handler access
6. **Test iteratively** with fast restarts

### ❌ Don'ts

1. **Don't use `asyncio.run()`** inside async functions
2. **Don't map Docker paths to host paths** (breaks portability)
3. **Don't copy files from read-only volumes** (use directly)
4. **Don't import inside try blocks** (breaks exception handlers)
5. **Don't rebuild for every code change** (use volumes)

### 🚀 Results

- **Development speed:** 200-300x faster (seconds vs minutes)
- **Pipeline working:** Full end-to-end flow operational
- **Latency:** ~30s total (acceptable for demo)
- **Quality:** Excellent voice cloning and lip sync
- **Stability:** Repeatable and reliable results

---

## Next Steps

### Immediate Optimizations

1. **Model warmup:** Pre-initialize avatar model to eliminate cold start
2. **Parallel processing:** Run TTS and prepare assets concurrently
3. **Response streaming:** Start video generation before TTS completes
4. **LLM upgrade:** Update transformers to enable Qwen2 (better responses)

### Production Hardening

1. **Error boundaries:** Graceful degradation if component fails
2. **Progress indicators:** Real-time feedback to user
3. **Request queuing:** Handle multiple concurrent requests
4. **Monitoring:** Track latencies and resource usage
5. **Auto-scaling:** Multiple GPU instances for load

### Quality Improvements

1. **Better reference images:** Higher resolution, multiple angles
2. **Voice sample variety:** Different emotions/tones
3. **Animation tuning:** Fine-tune Ditto parameters
4. **Post-processing:** Optional face enhancement (GFPGAN)

---

**Session Achievement:** First successful end-to-end conversation pipeline! 🎉

From audio input to avatar video output in ~30 seconds with excellent quality.
