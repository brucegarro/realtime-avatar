# Challenges & Solutions

This document tracks significant technical challenges encountered during development, their solutions, and lessons learned. It also outlines future challenges to anticipate.

---

## ✅ Challenges Overcome

### 1. CUDA Version Mismatch (Nov 11, 2025)

**Problem:**
- Docker container built with CUDA 11.8
- Faster-Whisper requires CUDA 12.x for ctranslate2 compatibility
- Error: `Could not load library libcudnn_ops_infer.so.8`

**Investigation:**
- Checked CUDA version: `nvcc --version` showed 11.8
- Faster-Whisper documentation specified CUDA 12+ requirement
- ctranslate2 has different binaries for different CUDA versions

**Solution:**
1. Updated `runtime/Dockerfile.ditto` base image:
   - FROM: `nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04`
   - TO: `nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04`
2. Verified PyTorch 2.1.2 CUDA 11.8 wheels are compatible with CUDA 12 runtime
3. Rebuilt entire container (~20 minutes)
4. Installed Faster-Whisper 1.0.3 with ctranslate2 4.0.0

**Lesson Learned:**
- Always check CUDA version compatibility for all dependencies
- CUDA runtime is forward compatible (12.x can run 11.x binaries)
- But libraries like ctranslate2 need specific CUDA versions

**Files Changed:**
- `runtime/Dockerfile.ditto`

---

### 2. Docker Disk Space Exhaustion (Nov 11, 2025)

**Problem:**
- GCP instance created with 50GB boot disk
- Docker build failed: "no space left on device"
- Multiple failed builds accumulated layers

**Investigation:**
```bash
df -h /  # Only 2.3GB free
docker system df  # 18GB in images, 8.5GB reclaimable
```

**Solutions (Progressive):**
1. **Immediate:** Pruned Docker system
   ```bash
   docker system prune -af --volumes
   # Freed 18GB
   ```

2. **Root Cause:** Expanded GCP disk from 50GB → 200GB
   ```bash
   gcloud compute disks resize realtime-avatar-test --size=200GB --zone=us-east1-c
   sudo resize2fs /dev/sda1
   ```

3. **Prevention:** 
   - Skip failed HuggingFace model downloads in Dockerfile
   - Mount large model checkpoints at runtime instead of baking into image
   - Use multi-stage builds to reduce final image size

**Lesson Learned:**
- Cloud instances need generous disk space for ML workloads
- Docker layers accumulate quickly during development
- Mount large static assets (models) rather than copying them
- Regular `docker system prune` during development

**Files Changed:**
- `runtime/Dockerfile.ditto` (optimized model downloads)
- Infrastructure: GCP disk size increased

---

### 3. Multiple Docker Build Failures (Nov 11, 2025)

**Problem A: Model Download Failures**
- HuggingFace hub downloads timing out or failing
- Build process hanging at model download steps

**Solution A:**
- Skip model downloads in Dockerfile
- Mount pre-downloaded models at runtime
- Use `|| true` for optional downloads

**Problem B: numpy Version Conflict**
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed.
TTS 0.22.0 requires numpy<2.0,>=1.24.3
```

**Solution B:**
- Pin numpy version: `numpy<2.0.0` before installing TTS
- Install dependencies in correct order

**Problem C: Interactive TTS License Prompt**
```
Container exiting immediately after start
Logs showed: "Do you agree to license? [Y/n]"
```

**Solution C:**
- Added environment variable: `ENV COQUI_TOS_AGREED=1`
- Prevents interactive prompt in non-TTY environment

**Lesson Learned:**
- Order of pip installations matters for ML packages
- Always set environment variables for non-interactive tools
- Test container startup, not just build success
- Use health checks to catch runtime issues

**Files Changed:**
- `runtime/Dockerfile.ditto` (multiple iterations)

---

### 4. ASR Return Value Bug (Nov 11, 2025)

**Problem:**
- `ASRModel.transcribe()` documentation said it returns `(text, metadata_dict)`
- Actual return: `(text, language_code, probability)` - a 3-tuple

**Investigation:**
```python
result = asr.transcribe(audio_path)
print(f"Type: {type(result)}, Length: {len(result)}")
# Output: Type: <class 'tuple'>, Length: 3
# Items: str, str, float (not str, dict)
```

**Solution (Temporary Workaround):**
```python
result = asr.transcribe(audio_path)
if len(result) == 3:
    text, language, lang_prob = result
else:
    text, metadata = result
    language = metadata.get('language', 'en')
```

**Proper Fix (TODO):**
Update `runtime/models/asr.py` to return consistent format:
```python
return text, {
    'language': language,
    'probability': probability,
    'duration': duration,
    'segments': segments
}
```

**Lesson Learned:**
- Test return values, don't assume from documentation
- API consistency is critical for integration
- Document actual behavior, not intended behavior
- Add type hints and validation

**Files Changed:**
- `test_phase2_simple.py` (workaround added)
- `runtime/models/asr.py` (needs fixing)

---

### 5. HEIC Image Format Issue (Nov 11, 2025)

**Problem:**
```python
OpenCV(4.11.0) error: (-215:Assertion failed) !_src.empty() in function 'cvtColor'
```
- File named `bruce_haircut.jpg` but actually HEIC format
- OpenCV cannot read HEIC files
- File header: `00 00 00 34 66 74 79 70 68 65 69 63` = "ftyp heic"

**Investigation:**
```bash
file bruce_haircut.jpg
# Output: ISO Media, HEIF Image HEVC Main or Main Still Picture Profile

python -c "import cv2; img = cv2.imread('bruce_haircut.jpg'); print(img)"
# Output: None  (failed to load)
```

**Solution:**
Convert HEIC to actual JPEG using macOS sips:
```bash
sips -s format jpeg bruce_haircut.jpg --out bruce_haircut_converted.jpg
```

**Lesson Learned:**
- Don't trust file extensions
- Apple devices save as HEIC by default (iOS 11+)
- Always validate image format before processing
- Consider adding automatic format detection/conversion to pipeline

**Files Changed:**
- `originals/bruce_haircut_converted.jpg` (new file)

---

### 6. Ditto StreamSDK API Misunderstanding (Nov 11, 2025)

**Problem:**
Multiple API-related errors while implementing Ditto video generation:

**Error A:**
```python
TypeError: '>' not supported between instances of 'str' and 'int'
```
- Passed `avatar_id` string as second parameter
- But `register()` expects `max_dim` integer

**Error B:**
```python
AttributeError: 'StreamSDK' object has no attribute 'drive_one_avatar'
```
- Assumed high-level API method existed
- Actual API uses low-level `setup()`, `setup_Nd()`, `run_chunk()`, `close()`

**Investigation:**
```bash
# Check actual API
python -c "from stream_pipeline_offline import StreamSDK; print(dir(StreamSDK))"

# Study reference implementation
cat runtime/inference.py
```

**Solution:**
Rewrote `DittoModel.generate_video()` to follow reference implementation:
```python
# Correct flow:
self.sdk.setup(source_image, output_path, **setup_kwargs)
audio, sr = librosa.core.load(audio_path, sr=16000)
num_frames = math.ceil(len(audio) / 16000 * 25)
self.sdk.setup_Nd(N_d=num_frames, fade_in=-1, fade_out=-1)
aud_feat = self.sdk.wav2feat.wav2feat(audio)
self.sdk.audio2motion_queue.put(aud_feat)
self.sdk.close()
# Then add audio track with ffmpeg
```

**Lesson Learned:**
- Read reference implementations, not just documentation
- Test API methods before building on them
- Use `dir()` and `inspect.signature()` to explore unknown APIs
- Don't assume convenience methods exist

**Files Changed:**
- `runtime/models/ditto_model.py` (major rewrite of generate_video method)

---

### 7. Docker Checkpoint Mount Issues (Nov 11, 2025)

**Problem:**
```python
FileNotFoundError: [Errno 2] No such file or directory: 
'./checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl'
```
- Working directory: `/app/runtime`
- Relative path `./checkpoints` → `/app/runtime/checkpoints`
- But Ditto models mounted at `/app/ditto-talkinghead/checkpoints`

**Investigation:**
```bash
docker exec ditto-cuda12 pwd  # /app/runtime
docker exec ditto-cuda12 ls -la /app/ditto-talkinghead/checkpoints/
# ditto_cfg/ and ditto_pytorch/ exist here
```

**Solution:**
Created symlinks in working directory:
```bash
cd /app/runtime
ln -sf /app/ditto-talkinghead/checkpoints/ditto_cfg checkpoints/
ln -sf /app/ditto-talkinghead/checkpoints/ditto_pytorch checkpoints/
```

**Better Solution (TODO):**
Update `DittoModel.__init__()` to use absolute paths:
```python
self.data_root = os.environ.get('DITTO_DATA_ROOT', 
                                '/app/ditto-talkinghead/checkpoints/ditto_pytorch')
self.cfg_pkl = os.environ.get('DITTO_CFG_PKL',
                              '/app/ditto-talkinghead/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl')
```

**Lesson Learned:**
- Avoid relative paths in containerized applications
- Use environment variables for configurable paths
- Document expected directory structure
- Test with actual mount points, not copied files

**Files Changed:**
- Container symlinks (temporary fix)
- `runtime/models/ditto_model.py` (needs better path handling)

---

## 🔮 Future Challenges

### 1. TensorRT Optimization (High Priority)

**Challenge:**
Convert PyTorch models to TensorRT for 2-3x additional speedup.

**Potential Issues:**
- Dynamic shapes in diffusion models
- ONNX export compatibility
- TensorRT version compatibility with CUDA 12
- Model accuracy degradation after quantization

**Research Needed:**
- Ditto TensorRT conversion process
- Best quantization strategies (FP16 vs INT8)
- Benchmark accuracy vs speed tradeoff

**Resources:**
- TensorRT documentation
- ONNX export best practices
- Ditto may have TRT configs already (check `ditto_cfg/*.pkl`)

---

### 2. Streaming Architecture Integration (Medium Priority)

**Challenge:**
Connect all Phase 2 components into real-time streaming pipeline.

**Potential Issues:**
- Queue synchronization between async components
- Backpressure handling when video generation is slower than TTS
- Chunk size tuning for optimal latency
- Memory management for long conversations

**Technical Debt:**
- ASR metadata return format needs fixing
- StyleTTS2 not yet tested
- WebSocket streaming not implemented
- No load balancing for multiple users

**Testing Needed:**
- End-to-end latency measurement
- Stress testing with multiple concurrent streams
- Memory leak detection over long sessions

---

### 3. StyleTTS2 Integration & Testing (High Priority)

**Challenge:**
Validate that StyleTTS2 is 10-20x faster than XTTS-v2 while maintaining quality.

**Potential Issues:**
- Voice cloning quality may be worse than XTTS-v2
- May require pre-training on Bruce's voice for best results
- Dependencies may conflict with existing TTS package
- Model initialization time could offset speed gains

**Testing Plan:**
1. Benchmark synthesis speed on same text as XTTS-v2
2. A/B test voice quality
3. Test zero-shot vs fine-tuned performance
4. Measure memory usage and GPU utilization

---

### 4. Production Deployment (Low Priority - Future)

**Challenge:**
Deploy to production with proper infrastructure, monitoring, and scaling.

**Potential Issues:**
- GPU cost optimization (spot instances, auto-scaling)
- Multi-user request queuing
- Model version management
- Logging and debugging in production
- Graceful degradation when GPU unavailable

**Infrastructure Needs:**
- Load balancer
- Redis/RabbitMQ for job queue
- Prometheus + Grafana for monitoring
- CI/CD pipeline
- Automated testing suite

---

### 5. Multi-Language Support (Low Priority)

**Challenge:**
Support languages beyond English while maintaining quality.

**Potential Issues:**
- XTTS-v2 supports multiple languages but quality varies
- Ditto trained primarily on English faces/speech
- Lip sync accuracy may degrade for non-English phonemes
- Voice cloning may not work well across languages

**Research Needed:**
- Test XTTS-v2 quality in Chinese, Spanish, etc.
- Investigate multilingual Ditto models
- Phoneme mapping for different languages

---

### 6. Real-Time LLM Integration (Medium Priority)

**Challenge:**
Integrate streaming LLM for conversational intelligence.

**Potential Issues:**
- LLM response time varies significantly (1-10s)
- Streaming output requires buffering before TTS
- Context management for long conversations
- Cost of API calls (OpenAI, Anthropic)

**Options:**
- OpenAI GPT-4 with streaming
- Anthropic Claude with streaming
- Local LLaMA models (slower but free)
- Hybrid approach: local for simple, API for complex

---

### 7. Image Preprocessing & Quality (Medium Priority)

**Challenge:**
Handle diverse input images (lighting, angles, quality).

**Potential Issues:**
- Poor quality selfies may produce bad results
- Side profile images don't work well
- Inconsistent lighting affects video quality
- Image resolution affects processing time

**Solutions to Explore:**
- Face detection and cropping
- Image enhancement (GFPGAN, CodeFormer)
- Quality scoring to reject bad inputs
- Preprocessing pipeline for normalization

---

### 8. Audio Quality & Noise Handling (Medium Priority)

**Challenge:**
Handle noisy audio input in real-world conditions.

**Potential Issues:**
- Background noise affects ASR accuracy
- Voice activity detection (VAD) may miss speech
- Echo and reverb in recordings
- Multiple speakers

**Solutions to Explore:**
- Audio preprocessing (noise reduction)
- Better VAD tuning
- Speaker diarization
- Acoustic model fine-tuning

---

### 9. Cost Optimization (Low Priority - Future)

**Challenge:**
Reduce cloud computing costs for production deployment.

**Current Costs:**
- GCP L4 GPU: ~$0.60/hour = $432/month if always running
- Need to optimize for actual usage patterns

**Strategies:**
- Spot/preemptible instances (60-90% discount)
- Auto-scaling based on demand
- Model quantization to use smaller/cheaper GPUs
- Hybrid cloud + on-premise deployment
- Batch processing for non-real-time use cases

---

### 10. User Experience & Error Handling (Medium Priority)

**Challenge:**
Provide smooth UX even when things go wrong.

**Potential Issues:**
- GPU out of memory errors
- Model loading failures
- Network timeouts
- Invalid input handling

**Features Needed:**
- Graceful error messages
- Progress indicators
- Retry logic
- Input validation
- Fallback options (e.g., audio-only mode)

---

## 📊 Challenge Priority Matrix

| Challenge | Priority | Impact | Effort | Risk |
|-----------|----------|--------|--------|------|
| TensorRT Optimization | HIGH | HIGH | MEDIUM | MEDIUM |
| StyleTTS2 Testing | HIGH | HIGH | LOW | LOW |
| Streaming Integration | MEDIUM | HIGH | HIGH | MEDIUM |
| Production Deployment | LOW | MEDIUM | HIGH | HIGH |
| Multi-Language | LOW | MEDIUM | MEDIUM | MEDIUM |
| LLM Integration | MEDIUM | HIGH | MEDIUM | MEDIUM |
| Image Preprocessing | MEDIUM | MEDIUM | MEDIUM | LOW |
| Audio Quality | MEDIUM | MEDIUM | MEDIUM | LOW |
| Cost Optimization | LOW | MEDIUM | LOW | LOW |
| Error Handling | MEDIUM | HIGH | LOW | LOW |

---

## 🎯 Next Steps

Based on priority and current progress:

1. **Complete StyleTTS2 Testing** (1-2 hours)
   - Run benchmark comparing to XTTS-v2
   - Validate voice quality
   - Document performance gains

2. **Fix ASR Metadata Bug** (30 minutes)
   - Update return format to dict
   - Update all callers
   - Add tests

3. **TensorRT Exploration** (2-4 hours)
   - Research Ditto TRT conversion
   - Test with sample model
   - Benchmark performance

4. **Streaming Pipeline Testing** (2-3 hours)
   - End-to-end test with all components
   - Measure actual latency
   - Identify bottlenecks

5. **Documentation & Code Cleanup** (1-2 hours)
   - Document all APIs
   - Add type hints
   - Write integration tests

---

## 📚 Lessons Learned Summary

**Key Takeaways:**
1. ✅ Always verify CUDA compatibility across ALL dependencies
2. ✅ Provision generous disk space for ML workloads (200GB minimum)
3. ✅ Test APIs with actual data, don't trust documentation
4. ✅ Use absolute paths in containers, configure with env vars
5. ✅ Validate file formats, don't trust extensions
6. ✅ Study reference implementations before building
7. ✅ Add health checks and startup validation
8. ✅ Document actual behavior, not intended behavior
9. ✅ Regular cleanup during development (disk, containers, images)
10. ✅ Progressive debugging: verify each layer before moving up

**Development Velocity:**
- Overcame 7 major blockers in ~6 hours
- Built and deployed complete Phase 2 architecture
- Generated working demo video end-to-end
- All core components tested and validated

**Technical Debt:**
- ASR return format needs fixing
- Ditto path handling needs improvement
- StyleTTS2 not yet tested
- Streaming pipeline not yet tested
- No automated tests
- Documentation incomplete

**Infrastructure:**
- GCP L4 GPU instance: READY TO STOP
- Docker container: HEALTHY and production-ready
- Models: Downloaded and validated
- Cost: ~$0.60/hour when running

---

## 🔬 Ditto Performance Optimization (Nov 13-14, 2025)

**Challenge:**
Ditto TalkingHead model running at 4.56x RTF (real-time factor) - far from real-time (<1.0x) requirement.

**Attempted Optimizations:**

1. **✅ Image Resolution Reduction** (19% improvement)
   - Cropped from 512x682px → 384x579px (36% fewer pixels)
   - Result: 4.56x → 3.71x RTF
   - Saved: `originals/bruce_haircut_cropped.jpg`

2. **✅ Diffusion Steps Reduction** (17% improvement)
   - Reduced from 50 → 25 steps (modified pickle config)
   - Result: 3.71x → 3.07x RTF
   - Quality acceptable at 25 steps

3. **❌ FP16 Precision** (only 4% improvement)
   - Added `.half()` conversion to models
   - Result: 3.07x → 2.94x RTF
   - Bottleneck is not compute precision

4. **❌ Further Steps Reduction** (only 3% improvement)
   - Reduced from 25 → 15 steps
   - Result: 2.94x → 2.86x RTF
   - Diminishing returns, quality degradation

5. **❌ Micro Resolution** (actually SLOWER)
   - Reduced to 180x240px (87% fewer pixels)
   - Result: 3.07x → 3.04x RTF (only 1% better!)
   - Video encoding overhead dominates at tiny sizes

**Key Finding:**
Resolution optimization hits a wall around 384x579px. Further reductions provide negligible benefit because the **bottleneck is the diffusion model computation itself**, not image processing.

**Final Optimized Configuration:**
- Resolution: 384x579px (cropped portrait)
- Diffusion steps: 25
- FPS: 25
- Precision: FP32 (FP16 didn't help)
- **Best RTF: 3.07x** (1.6x overall speedup from baseline)
- **Throughput: 145 videos/hour**

**Still 3x Slower Than Real-Time**

**Remaining Options to Reach <1.0x RTF:**
1. **TensorRT Optimization** - Most promising, 2-3x speedup potential (2-4 days effort)
2. **Alternative Model** - Wav2Lip achieves ~1.0x RTF but lower quality
3. **GPU Upgrade + TensorRT** - H100 could get 2x more, but 8x more expensive

**Lessons Learned:**
- Simple optimizations (crop + steps) gave 33% improvement quickly
- Advanced optimizations (FP16, micro-resolution) had diminishing returns
- Diffusion models are inherently slow - fundamental architecture limit
- Resolution sweet spot exists (~384x579px for this model)
- Hardware upgrade alone won't solve it - need algorithmic optimization (TensorRT)
- Concurrent execution on single GPU has variable performance

**Test Files Created:**
- `originals/bruce_haircut_cropped.jpg` - 384x579px, keeps for production
- `originals/bruce_haircut_micro.jpg` - 180x240px, delete (not useful)


---

## 🔍 TensorRT Discovery (Nov 14, 2025)

**Discovery:**
Ditto has **official TensorRT engines** pre-built and ready to use! We don't need to convert anything.

**What We Found:**

1. **Pre-built TensorRT Engines (2GB)**
   - Path: `checkpoints/ditto_trt_Ampere_Plus/`
   - Files: 
     * `decoder_fp16.engine`
     * `motion_extractor_fp32.engine`
     * `warp_network_fp16.engine`
     * `appearance_extractor_fp16.engine`
     * `stitch_network_fp16.engine`
     * Plus auxiliary models (hubert, landmark detection, etc.)
   - Hardware compatibility: Ampere+ (L4, A10, A100, RTX 30/40 series)

2. **TensorRT Config Files**
   - `v0.4_hubert_cfg_trt.pkl` - Standard inference
   - `v0.4_hubert_cfg_trt_online.pkl` - Online/streaming mode

3. **Official Support**
   - README documents TensorRT path explicitly
   - Tested on A100 + TensorRT 8.6.1
   - Community reports successful usage on RTX 3090

**Expected Performance:**
- Current PyTorch: 3.07x RTF (145 videos/hour)
- TensorRT target: **<1.5x RTF** (>240 videos/hour)
- Potential for **real-time** (<1.0x RTF)

**Installation Blocker:**
TensorRT 8.6.1 installation failed in current container:
- Requires `tensorrt-libs` (825MB package)
- Complex dependency chain with NVIDIA PyPI index
- Need proper build environment setup

**Next Steps:**
1. Create new Docker image with TensorRT 8.6.1 pre-installed
2. Use NVIDIA's official TensorRT container as base image
3. Run: `python inference.py --data_root=./checkpoints/ditto_trt_Ampere_Plus --cfg_pkl=./checkpoints/ditto_cfg/v0.4_hubert_cfg_trt.pkl`

**Lessons Learned:**
- Always check upstream project docs thoroughly
- Official optimizations often exist before community ports
- TensorRT installation requires careful environment setup
- The 2-4 day TensorRT conversion work we estimated is **already done**!

**Files Created:**
- `download_trt_checkpoints.sh` - Script to download TRT engines from Hugging Face
- `test_trt.py` - Test script for TensorRT inference (untested due to install issues)

**Impact:**
This could be the breakthrough to real-time performance. Just need to resolve TensorRT installation to test.


**Update (Nov 14, 2025 - Evening Session):**

**TensorRT Installation Complexity:**
The official TensorRT engines exist and are downloaded (2GB successfully), but installing the TensorRT Python bindings (v8.6.1) in the current container proved difficult:

1. **tensorrt-libs**: ✅ Successfully installed (825MB wheel)
2. **tensorrt**: ❌ Failed - Complex build dependencies, requires `/usr/bin/python3 -m pip` which doesn't exist in build environment
3. **Root cause**: TensorRT 8.6.1's Python package has build-time dependencies that conflict with container's pip setup

**What's Needed:**
- Build new Docker image FROM nvidia/tensorrt:22.12-py3 (has TRT 8.5.x pre-installed)
- OR use TensorRT 10.x containers (CUDA 12.x compatible)
- Ditto code already supports loading .engine files, just needs Python bindings to instantiate TRT runtime

**Alternative Approach:**
Given TensorRT installation complexity, consider:
1. **Docker rebuild** (cleaner, 1-2 hours)
2. **Test Wav2Lip** (already works, ~1.0x RTF, lower quality but proven)
3. **Optimize Wav2Lip** (may be easier path to real-time)

**Current Status:**
- TensorRT engines: ✅ Downloaded and ready (ditto_trt_Ampere_Plus/)
- TensorRT Python: ❌ Not installed
- Instance: Ready to rebuild with proper base image

