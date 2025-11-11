# Benchmark Results - November 11, 2025

## Session Summary

Testing concurrent video generation performance with Ditto TalkingHead model on GCP L4 GPU.

## Infrastructure

- **Instance**: realtime-avatar-test (g2-standard-4)
- **GPU**: NVIDIA L4 (24GB VRAM)
- **Zone**: us-east1-c
- **Container**: ditto-cuda12 (CUDA 12.1)

## Sequential Baseline Results ✅

Successfully established baseline performance with direct benchmark:

### Overall Performance
- **RTF (Real-Time Factor)**: 6.13x realtime
- **Goal**: <1.0x realtime (6x optimization gap)
- **Throughput**: 86.6 videos/hour (2,080/day)
- **Average Processing Time**: 41.5s per video

### Component Breakdown

#### TTS (XTTS-v2 Voice Cloning)
- **RTF**: 0.76-0.88x realtime ✅
- **Status**: Already faster than realtime
- **Performance**: Excellent - not the bottleneck

#### Ditto (Video Generation)
- **RTF**: 5.07-5.58x realtime ⚠️
- **Status**: Major bottleneck (5-6x slower than target)
- **Processing Time**: 25-50s per 4-10s audio clip

### Test Configuration
- **Test Videos**: 3 short phrases (4-10s audio each)
- **Total Runtime**: ~2 minutes
- **Voice Reference**: bruce_expressive_motion_21s.mp3
- **Image Reference**: bruce_haircut.jpg

## Concurrent Worker Tests ⚠️

### Implementation Complete
- Created `ConcurrentVideoGenerator` class (437 lines)
- ThreadPoolExecutor with job queue
- Shared TTS/ASR models, per-worker Ditto instances
- Support for 1-8 workers
- Memory monitoring and CUDA stream management

### Benchmark Status
The concurrent benchmark was created but **did not complete successfully**:
- Hung during initialization phase
- Issue appears to be related to model loading in multi-worker context
- Sequential baseline works perfectly, concurrent needs debugging

### Memory Projections (Theoretical)
Based on model sizes:
- **Shared models**: 3.4GB (TTS + ASR)
- **Per worker**: 3.3GB (Ditto + buffers)
- **2 workers**: ~10GB (42% VRAM) - RTF: 3.07x
- **3 workers**: ~13.3GB (56% VRAM) - RTF: 2.04x
- **5 workers**: ~20GB (83% VRAM) - RTF: 1.23x
- **7 workers**: ~26.5GB (110% VRAM) - RTF: 0.88x (likely OOM)

## Key Findings

### ✅ Successful
1. Sequential pipeline working perfectly
2. TTS voice cloning fast and accurate
3. RTF metric provides clear optimization target
4. Ditto bottleneck clearly identified
5. Concurrent architecture implemented

### ⚠️ Issues Identified
1. Concurrent worker initialization hangs
2. 6x performance gap to reach realtime goal
3. Ditto model is primary bottleneck

### 🔧 Technical Fixes Applied
1. **TTS speaker parameter**: Must use `speaker=None` with `speaker_wav`
2. **Return value unpacking**: TTS returns 3 values: (path, duration_ms, audio_duration_s)
3. **Audio file paths**: Located correct reference files
4. **Checkpoint symlinks**: Required for Ditto model loading

## Recommendations

### Immediate Next Steps
1. **Debug concurrent initialization**: Fix model loading in multi-worker context
2. **Test smaller worker counts**: Try 2-3 workers before scaling to 8
3. **Profile Ditto bottleneck**: Understand why video gen is 5-6x slower

### Optimization Paths
1. **Ditto Optimization** (highest impact):
   - Model quantization (FP16/INT8)
   - Lower resolution inference
   - Alternative faster models (LivePortrait, SadTalker)
   
2. **Concurrent Scaling** (medium impact):
   - Once debugged, 3-5 workers could reach 2-3x RTF
   - Won't reach <1.0x alone but helps throughput
   
3. **Infrastructure** (lower impact):
   - Multi-GPU setup
   - Larger GPU (A100, H100)
   - Batching optimization

## Conclusion

**Sequential baseline established**: Clear 6x optimization gap identified with Ditto as bottleneck. TTS is already optimal. Concurrent architecture built but needs debugging before scaling tests. Next session should focus on either fixing concurrent implementation or optimizing Ditto directly.

**Cost**: ~$5 for today's session (8 hours @ $0.60/hr)
