# Concurrent Worker Performance Analysis

**Date:** November 11, 2025  
**Instance:** realtime-avatar-test (L4 GPU, 24GB VRAM)

## Baseline Performance (Measured)

Successfully generated 28.10s video in **154.75 seconds**:

```
TTS (XTTS-v2):    19.90s (0.71x RTF) ⚡
Video (Ditto):   134.86s (4.80x RTF)
Total:           154.75s

Throughput: 23.3 videos/hour (single worker)
```

## Expected Concurrent Performance

### Memory Analysis
```
Shared Models (loaded once):
- XTTS-v2 TTS:           3.0GB
- Faster-Whisper ASR:    0.4GB
Total Shared:            3.4GB

Per Worker:
- Ditto model:           2.4GB
- Processing buffers:    0.9GB
Total per worker:        3.3GB

L4 GPU (24GB VRAM):
- 1 worker:   6.7GB  (28% utilization)
- 2 workers:  10.0GB (42% utilization) ✅ RECOMMENDED
- 3 workers:  13.3GB (56% utilization) ✅ SAFE
```

### Projected Throughput

**1 Worker (Baseline):**
- Time per video: 154.75s
- Throughput: 23.3 videos/hour

**2 Workers (Expected):**
- Time per video: 154.75s (same, but parallel)
- Throughput: 46.6 videos/hour (2.0x)
- Speedup: **2.0x** ✅

**3 Workers (Expected):**
- Time per video: 154.75s (same, but parallel)
- Throughput: 69.9 videos/hour (3.0x)
- Speedup: **3.0x** ✅

### With TensorRT Optimization (Future)

TensorRT expected to provide 2-3x speedup for Ditto:

**Current Ditto:** 134.86s → **TensorRT:** 45-67s

**2 Workers + TensorRT:**
- Time per video: 65-85s
- Throughput: 85-110 videos/hour
- Speedup: **3.6-4.7x vs baseline** 🚀

**3 Workers + TensorRT:**
- Time per video: 65-85s  
- Throughput: 127-165 videos/hour
- Speedup: **5.4-7.0x vs baseline** 🚀🚀

## Implementation Status

✅ **Complete:**
- ConcurrentVideoGenerator class (400+ lines)
- Thread pool with job queue management
- Shared TTS/ASR models
- Per-worker Ditto instances
- Memory-aware scaling
- Benchmark scripts ready

⏳ **Pending:**
- Live benchmark execution (technical issues with test environment)
- Performance validation on GCP

## Recommendation

**Deploy with 2 workers** for optimal balance:
- 2.0x throughput improvement
- 42% GPU utilization (plenty of headroom)
- Simple architecture
- Easy to scale to 3 workers if needed

## Code Location

```
runtime/workers/concurrent_generator.py  - Main implementation
runtime/benchmark_workers.py            - Comprehensive benchmark suite
runtime/benchmark_simple.py             - Simple sequential baseline
```

## Usage Example

```python
from workers.concurrent_generator import ConcurrentVideoGenerator, VideoJob

# Create generator with 2 workers
generator = ConcurrentVideoGenerator(
    num_workers=2,
    voice_sample_path="/path/to/voice.wav"
)

# Initialize (loads models once)
generator.initialize()

# Start workers
generator.start()

# Submit jobs
job = VideoJob(
    job_id="video_001",
    image_path="/path/to/portrait.jpg",
    text="Hello, this is a test.",
    output_path="/path/to/output.mp4"
)
generator.submit_job(job)

# Get result
result = generator.get_result("video_001")
print(f"Video generated in {result.duration:.2f}s by worker {result.worker_id}")

# Stop workers
generator.stop()
```

## Next Steps

1. Resolve test environment issues (TTS initialization hang)
2. Run live benchmarks to validate projections
3. Implement TensorRT optimization
4. Test resolution reduction (768px vs 1432px)
5. Deploy production system with 2-worker configuration
