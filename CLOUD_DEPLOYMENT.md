# Cloud Deployment Strategy - Realtime Avatar

## Overview

This document outlines the cloud deployment architecture optimized for realtime video generation using streaming video encoding (Option 4).

## Video Encoding Architecture

### Local Development (macOS M3)
- **Encoder**: `h264_videotoolbox` (Apple Silicon GPU)
- **Performance**: ~0.3s per frame encoding (parallel with rendering)
- **Expected total time**: 15-20s for 2s audio (~37 frames)

### Cloud Production (GCP with NVIDIA GPUs)
- **Encoder**: `h264_nvenc` (NVIDIA NVENC hardware)
- **Dedicated hardware**: Does not compete with CUDA cores
- **Performance**: 5-10x faster than CPU encoding

## GCP Instance Options

### Option 1: T4 GPU (Cost-Effective)
**Specs:**
- GPU: NVIDIA Tesla T4 (16GB VRAM)
- CUDA Cores: 2560
- Tensor Cores: 320
- NVENC: 1x encoder (up to 1080p60)
- Cost: ~$0.35/hour

**Performance Estimates:**
```
TTS (XTTS on T4):       0.3x realtime (600ms for 2s audio)
SadTalker rendering:    0.2s per frame (50% faster than M3)
NVENC encoding:         0.1s per frame (parallel)
Net per frame:          0.2s

For 2s audio (50 frames @ 25fps):
- First frame ready:    0.8s (TTS + first render)
- Full video:           0.8s + (50 × 0.2s) = 10.8s total
- Streaming start:      Client sees video at 0.8s latency

Cost per video:         ~$0.001 (assuming 10s generation)
Throughput:             ~300 videos/hour/instance
```

### Option 2: V100 GPU (High Performance)
**Specs:**
- GPU: NVIDIA Tesla V100 (16GB VRAM)
- CUDA Cores: 5120
- Tensor Cores: 640
- NVENC: 1x encoder
- Cost: ~$2.48/hour

**Performance Estimates:**
```
TTS (XTTS on V100):     0.2x realtime (400ms for 2s audio)
SadTalker rendering:    0.12s per frame (3x faster than M3)
NVENC encoding:         0.08s per frame (parallel)
Net per frame:          0.12s

For 2s audio:
- First frame ready:    0.5s
- Full video:           0.5s + (50 × 0.12s) = 6.5s total
- Streaming start:      0.5s latency

Cost per video:         ~$0.0045
Throughput:             ~500 videos/hour/instance
```

### Option 3: A100 GPU (Premium / True Realtime)
**Specs:**
- GPU: NVIDIA A100 (40GB VRAM)
- CUDA Cores: 6912
- Tensor Cores: 432 (3rd gen)
- NVENC: 1x encoder
- Cost: ~$3.67/hour

**Performance Estimates:**
```
TTS (XTTS on A100):     0.15x realtime (300ms for 2s audio)
SadTalker rendering:    0.08s per frame (5x faster than M3)
NVENC encoding:         0.05s per frame (parallel)
Net per frame:          0.08s

For 2s audio:
- First frame ready:    0.38s
- Full video:           0.38s + (50 × 0.08s) = 4.4s total
- Streaming start:      0.38s latency ⭐ TRUE REALTIME

Cost per video:         ~$0.0045
Throughput:             ~800 videos/hour/instance
```

## Streaming Implementation

### Hardware Detection
```python
def get_hardware_encoder():
    """Auto-detect best video encoder for current hardware"""
    # Check for NVIDIA GPU (GCP)
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True)
        if result.returncode == 0:
            return 'h264_nvenc'  # NVIDIA NVENC
    except:
        pass
    
    # Check for Apple Silicon (Local dev)
    import platform
    if platform.system() == 'Darwin' and platform.processor() == 'arm':
        return 'h264_videotoolbox'  # Apple VideoToolbox
    
    # Fallback to CPU (compatibility)
    return 'libx264'
```

### Streaming Encoder Function
```python
def save_video_streaming(frames, audio_path, output_path, fps=25):
    """
    Universal streaming video encoder
    - Encodes frames as they're generated (parallel with GPU)
    - Uses hardware acceleration (VideoToolbox/NVENC)
    - Works on macOS (dev) and GCP (prod)
    """
    h, w = frames[0].shape[:2]
    encoder = get_hardware_encoder()
    
    # Encoder-specific settings
    encoder_params = {
        'h264_nvenc': ['-preset', 'p4', '-b:v', '2M'],      # NVIDIA: p1-p7 (quality/speed)
        'h264_videotoolbox': ['-b:v', '2M'],                # Apple
        'libx264': ['-preset', 'medium', '-crf', '23']      # CPU fallback
    }
    
    cmd = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        # Video input from stdin (streaming)
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{w}x{h}', '-pix_fmt', 'rgb24', '-r', str(fps),
        '-i', '-',
        # Audio input from file
        '-i', audio_path,
        # Hardware encoder
        '-c:v', encoder, *encoder_params[encoder],
        '-pix_fmt', 'yuv420p',
        # Audio settings
        '-c:a', 'aac', '-b:a', '128k',
        '-shortest',
        output_path
    ]
    
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Stream frames to encoder
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    
    proc.stdin.close()
    proc.wait()
```

## Scalability Architecture

### Horizontal Scaling (Multiple Instances)
```
Load Balancer (GCP Cloud Load Balancing)
    ↓
    ├─ Instance 1 (T4) ─ Handles requests 1, 4, 7...
    ├─ Instance 2 (T4) ─ Handles requests 2, 5, 8...
    └─ Instance 3 (T4) ─ Handles requests 3, 6, 9...

Benefits:
- 3x throughput: 900 videos/hour (3 × 300)
- 3x cost reduction per video: $0.00033 per video
- Fault tolerance: Failure of 1 instance = 66% capacity
```

### Video Segmentation (Long Videos)
```
For videos > 10s, split across instances:

Client request: Generate 30s video
    ↓
Gateway splits into 3 segments:
    ├─ Instance 1: Frames 1-250   (0-10s)  ─┐
    ├─ Instance 2: Frames 251-500 (10-20s) ─┼─ Parallel generation
    └─ Instance 3: Frames 501-750 (20-30s) ─┘
            ↓
    Gateway streams all 3 in order to client
            ↓
    Client receives progressive playback

Result: 30s video in ~12s (vs 36s sequential)
```

## Network Streaming (HTTP)

### Progressive MP4 Delivery
```python
from flask import Response, stream_with_context

def generate_video_stream(frames, audio_path, fps=25):
    """Stream video chunks over HTTP as they're encoded"""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', ...,
        '-i', '-',
        '-i', audio_path,
        '-c:v', 'h264_nvenc',
        '-f', 'mp4',
        '-movflags', 'frag_keyframe+empty_moov',  # Streaming-friendly MP4
        'pipe:1'  # Output to stdout
    ]
    
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    
    # Feed frames in background
    threading.Thread(target=lambda: [proc.stdin.write(f.tobytes()) for f in frames]).start()
    
    # Yield encoded chunks
    while chunk := proc.stdout.read(4096):
        yield chunk

@app.route('/generate/stream')
def stream_endpoint():
    frames = generate_frames_from_sadtalker()
    return Response(
        stream_with_context(generate_video_stream(frames, audio_path)),
        mimetype='video/mp4',
        headers={'X-Content-Duration': f'{len(frames)/25}'}  # Duration hint
    )
```

**Client receives:**
- First chunk: ~0.5-0.8s (can start playback immediately)
- Progressive chunks: Every ~0.2s
- Total latency: Perception of realtime (<1s to first frame)

## Resource Utilization

### Current (Batch Processing)
```
Timeline for 2s video on T4:
[████████████████ GPU Render 10s ████████████]
                                            [██ Idle 1s ██][█ Encode 2s █]
GPU Utilization: 10s / 13s = 77%
```

### With Streaming (Option 4)
```
Timeline for 2s video on T4:
[████████████████ GPU Render 10s ████████████]
[█████████████ NVENC Encode (parallel) 10s ██]
GPU Utilization: 10s / 10s = 100%
Speedup: 30% (13s → 10s)
```

### With Parallelism (3 videos simultaneously)
```
[Video 1 GPU Render ████████████]
                [Video 2 GPU Render ████████████]
                            [Video 3 GPU Render ████████████]
GPU Utilization: 100% continuous
Throughput: 3x
Cost per video: 1/3x
```

## Monitoring & Metrics

### Key Metrics to Track
```python
metrics = {
    'tts_latency_ms': 'Time for TTS generation',
    'first_frame_latency_ms': 'Time to first rendered frame',
    'total_generation_ms': 'Full video generation time',
    'encoder_type': 'h264_nvenc | h264_videotoolbox | libx264',
    'frames_per_second_generated': 'Rendering throughput',
    'gpu_utilization_percent': 'CUDA core usage',
    'nvenc_utilization_percent': 'Hardware encoder usage',
    'memory_used_mb': 'Peak GPU memory',
}
```

### GCP Cloud Monitoring Integration
```python
from google.cloud import monitoring_v3

def log_generation_metrics(duration_ms, encoder_type, gpu_util):
    client = monitoring_v3.MetricServiceClient()
    series = monitoring_v3.TimeSeries()
    series.metric.type = 'custom.googleapis.com/realtime_avatar/generation_duration'
    series.metric.labels['encoder'] = encoder_type
    
    point = monitoring_v3.Point()
    point.value.double_value = duration_ms
    point.interval.end_time.seconds = int(time.time())
    series.points = [point]
    
    client.create_time_series(name=project_path, time_series=[series])
```

## Cost Analysis

### Per-Video Cost Comparison

| Instance Type | Generation Time | Hourly Cost | Cost/Video | Videos/Hour |
|--------------|----------------|-------------|------------|-------------|
| **T4**       | 10.8s          | $0.35       | $0.00105   | 333         |
| **V100**     | 6.5s           | $2.48       | $0.00448   | 554         |
| **A100**     | 4.4s           | $3.67       | $0.00449   | 818         |

### Monthly Cost Estimates (10,000 videos/month)

| Instance Type | Single Instance | 3 Instances (3x throughput) |
|--------------|----------------|----------------------------|
| **T4**       | $10.50         | $31.50                    |
| **V100**     | $44.80         | $134.40                   |
| **A100**     | $44.90         | $134.70                   |

**Recommendation**: Start with T4 for cost, upgrade to A100 for realtime latency requirements.

## Deployment Checklist

- [ ] Install NVIDIA drivers on GCP instance
- [ ] Install CUDA toolkit (11.8+)
- [ ] Install ffmpeg with NVENC support: `apt install ffmpeg`
- [ ] Verify NVENC available: `ffmpeg -encoders | grep nvenc`
- [ ] Update animate.py with streaming encoder
- [ ] Update videoio.py with hardware detection
- [ ] Test with `nvidia-smi` monitoring during generation
- [ ] Set up Cloud Monitoring metrics
- [ ] Configure load balancer for multi-instance
- [ ] Test progressive streaming endpoint
- [ ] Benchmark end-to-end latency
- [ ] Document final performance numbers

## Future Optimizations

1. **Frame Prediction**: Encode predicted frame while GPU renders actual (hide latency)
2. **Variable Quality**: Lower quality for faster processing when queue is long
3. **Early Termination**: Stop generation when user disconnects
4. **Caching**: Cache common phrases/faces for instant delivery
5. **Edge Deployment**: CDN caching for popular content
6. **WebRTC**: Real-time bidirectional streaming for interactive avatars

---

**Last Updated**: November 7, 2025
**Version**: 1.0 (Initial draft for Option 4 implementation)
