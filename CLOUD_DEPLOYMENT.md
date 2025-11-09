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

## Scale-to-Zero Architecture (Cost Optimization)

### The Cold Start Problem

**Traditional Always-On Approach:**
- Keep min=1 GPU instance running
- Cost: T4 @ $0.35/hr × 24hr × 30 days = **$252/month idle**
- Response time: ~1-2 seconds
- ❌ Expensive for sporadic usage

**Cold Start Anatomy (scale from 0→1):**
```
1. VM provisioning:        30-60 seconds
2. Docker image pull:      60-90 seconds (if not cached)
3. Model loading to VRAM:  30-60 seconds
   - XTTS model:          ~15s
   - SadTalker models:    ~30s
   - GFPGAN (optional):   ~10s

Total cold start: 2-4 minutes (unoptimized)
```

### Cold Start Optimization Strategies

#### Strategy 1: Pre-baked Machine Image (30-45 second cold start) ⭐
```
Create custom GCP machine image:
- Docker pre-installed and configured
- Container images pre-pulled to local cache
- Models pre-downloaded to instance image
- Startup script auto-starts GPU service

Cold start breakdown:
1. VM boot from custom image:  30-40s
2. Docker container start:     5-10s
3. Model loading (cached):     10-15s

Total: 45-65 seconds
```

**Implementation:**
1. Launch T4 instance, set up everything
2. Create machine image: `gcloud compute images create realtime-avatar-base`
3. Use in instance template for MIG
4. Result: 60-70% faster cold starts

#### Strategy 2: Persistent Disk with Models (saves 20-30s)
```
- Attach 50GB SSD persistent disk
- Pre-load all models: XTTS, SadTalker, GFPGAN, checkpoints
- Mount at boot: /mnt/models
- Symlink to expected locations

Cold start savings: 20-30 seconds
One-time setup, reuse across instances
```

#### Strategy 3: Container-Optimized OS + Cached Images (saves 30-60s)
```
- Use GCP Container-Optimized OS
- Pre-pull Docker images to instance template
- Configure Docker with local cache
- Enable image streaming (Cloud Build)

Cold start savings: 30-60 seconds
```

### Recommended Architecture: Spot VM Warm Pool

**Hybrid approach balancing cost and response time:**

```
┌─────────────────────────────────────────────────┐
│  Cloud Run (Orchestrator)                       │
│  - Always on, cheap ($0.40/million requests)    │
│  - Routes to GPU instances                      │
│  - Manages queue + webhooks                     │
└──────────────┬──────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────┐
│  Spot T4 Instance (Warm Pool)                   │
│  - Cost: $0.10/hr (70% cheaper than standard)   │
│  - Idle timeout: 10 minutes                     │
│  - Auto-restart if preempted                    │
│  - Response: 1-2 seconds when warm              │
└──────────────┬──────────────────────────────────┘
               ↓ (if spot preempted)
┌──────────────┴──────────────────────────────────┐
│  Managed Instance Group (Standard T4s)          │
│  - min=0, max=5                                 │
│  - Cold start: 45 seconds (optimized)           │
│  - Scales based on queue depth                  │
│  - Fallback when spot unavailable               │
└─────────────────────────────────────────────────┘
```

**Cost Analysis:**
| Approach | Monthly Cost | Response Time | Best For |
|----------|-------------|---------------|----------|
| Always-on Standard T4 | $252 | 1-2s | High traffic production |
| Always-on Spot T4 | $72 | 1-2s | Medium traffic |
| Spot with 10min timeout | $10-30 | 1-2s warm, 45s cold | Sporadic usage ⭐ |
| Pure scale-to-zero (MIG) | $5-20 | 45s cold | Very low traffic |

### Auto-Scaling Configuration

**Managed Instance Group Setup:**
```yaml
# instance-template-config.yaml
instance_template:
  name: realtime-avatar-gpu
  machine_type: n1-standard-4
  accelerators:
    - type: nvidia-tesla-t4
      count: 1
  
  # Use pre-baked image
  source_image: realtime-avatar-base-v1
  
  # Startup script
  metadata:
    startup-script: |
      #!/bin/bash
      docker start gpu-service || docker run -d ...
      
autoscaler:
  min_replicas: 0  # Scale to zero
  max_replicas: 5
  
  # Scale up policy
  scale_up:
    - metric: pubsub.googleapis.com/subscription/num_undelivered_messages
      target: 5  # Spin up instance if >5 messages in queue
      
  # Scale down policy  
  scale_down:
    cooldown_period: 600  # 10 minutes idle before shutdown
    - metric: custom.googleapis.com/gpu_utilization
      target: 10  # Shutdown if <10% utilized for 10min
```

**Cloud Scheduler for Business Hours Warmup:**
```yaml
# Keep warm during business hours only
- name: warmup-morning
  schedule: "0 9 * * 1-5"  # 9am Mon-Fri
  target: pubsub
  message: '{"action": "warmup"}'

- name: cooldown-evening  
  schedule: "0 18 * * 1-5"  # 6pm Mon-Fri
  target: compute
  action: stop_instance
```

**Result:**
- 9am-6pm weekdays: 1-2 second response (warm)
- Nights/weekends: 45 second cold start (rare)
- Monthly cost: ~$15-25 instead of $252

### Async Processing Pattern

**For acceptable UX with cold starts:**

```python
# Cloud Run orchestrator endpoint
@app.route('/generate', methods=['POST'])
def generate_video_async():
    """Async video generation with webhook notification"""
    
    # Create job ID
    job_id = str(uuid.uuid4())
    
    # Publish to Pub/Sub queue
    publisher.publish(
        topic='video-generation-queue',
        data=json.dumps({
            'job_id': job_id,
            'audio_text': request.json['text'],
            'image_path': request.json['image'],
            'webhook_url': request.json.get('webhook_url'),
            'enhancer': request.json.get('enhancer')  # 'gfpgan' or None
        }).encode()
    )
    
    # Return job ID immediately
    return jsonify({
        'job_id': job_id,
        'status': 'queued',
        'estimated_time_seconds': 45,  # If cold, 10 if warm
        'status_url': f'/status/{job_id}'
    }), 202

# GPU instance polls queue
def process_queue():
    """GPU instance worker"""
    subscription = subscriber.subscribe(subscription_path)
    
    for message in subscription:
        job = json.loads(message.data)
        
        # Generate video
        result = generate_video(
            text=job['audio_text'],
            image=job['image_path'],
            enhancer=job['enhancer']
        )
        
        # Store result
        storage_client.upload(result, f"results/{job['job_id']}.mp4")
        
        # Notify webhook
        if job.get('webhook_url'):
            requests.post(job['webhook_url'], json={
                'job_id': job['job_id'],
                'status': 'completed',
                'video_url': f"gs://bucket/results/{job['job_id']}.mp4"
            })
        
        message.ack()
```

**User Experience:**
1. Client submits request → Gets job_id in 100ms
2. Client polls `/status/{job_id}` or waits for webhook
3. GPU spins up (if cold): 45 seconds
4. Video generates: 10-15 seconds
5. Client receives completion notification
6. Total: 55-60 seconds worst case, 10-15 if warm

### GFPGAN Performance on Cloud GPUs

**Current local performance (M3 MPS):**
- GFPGAN runs on CPU only (no MPS support)
- Processing time: ~1.44s per frame
- Total overhead: 5-10x slower (240s vs 35s for 5.6s video)

**Expected cloud performance (CUDA):**
```
T4 GPU with CUDA:
- GFPGAN on GPU: ~0.15-0.2s per frame
- Speedup: 7-10x faster than M3 CPU
- Total overhead: 10-20s for 5.6s video (vs 240s on M3)

V100 GPU:
- GFPGAN on GPU: ~0.08-0.1s per frame  
- Speedup: 15-20x faster than M3 CPU
- Total overhead: 5-10s for 5.6s video

Recommendation:
- Offer GFPGAN as optional "quality" mode
- Standard mode: Fast (10-15s)
- Quality mode: +10-20s for enhanced faces
- User can choose speed vs quality
```

### Monitoring & Alerting

**Key metrics for scale-to-zero:**
```python
# Track cold start performance
metrics_to_monitor = {
    'cold_start_duration_seconds': 'Time from scale-up to ready',
    'instance_idle_time_seconds': 'Time since last request',
    'queue_depth': 'Unprocessed jobs in Pub/Sub',
    'spot_preemption_count': 'How often spot VMs interrupted',
    'cost_per_day': 'Daily spend tracking',
    'requests_while_cold': 'Users experiencing cold start'
}

# Alerting rules
alerts = [
    {
        'name': 'High Cold Start Rate',
        'condition': 'cold_start_rate > 0.5',  # >50% requests hit cold start
        'action': 'Increase min_replicas to 1'
    },
    {
        'name': 'Budget Exceeded',
        'condition': 'daily_cost > $5',
        'action': 'Email alert + reduce max_replicas'
    },
    {
        'name': 'Queue Backing Up',
        'condition': 'queue_depth > 20',
        'action': 'Force scale up to max_replicas'
    }
]
```

### Cost Optimization Best Practices

1. **Right-size instances**: Don't use A100 if T4 meets requirements
2. **Committed use discounts**: If baseline >8 hours/day, commit for 30% savings
3. **Regional selection**: us-central1 is cheapest for GPUs
4. **Preemptible for batch**: Use spot VMs for non-urgent training jobs
5. **Storage lifecycle**: Auto-delete generated videos after 7 days
6. **Egress optimization**: Serve videos from Cloud CDN (cheaper bandwidth)

### Migration Checklist (Scale-to-Zero Setup)

- [ ] Create pre-baked machine image with models
- [ ] Set up Cloud Run orchestrator service
- [ ] Configure Pub/Sub queue for async jobs
- [ ] Create instance template with autoscaling (min=0)
- [ ] Test cold start time (target: <60s)
- [ ] Implement health check warming
- [ ] Add Cloud Scheduler for business hours
- [ ] Set up cost monitoring and budget alerts
- [ ] Test spot VM preemption handling
- [ ] Document webhook/polling flow for clients
- [ ] Load test: 0→5 instances scaling
- [ ] Verify scale-down after idle timeout

## Future Optimizations

1. **Frame Prediction**: Encode predicted frame while GPU renders actual (hide latency)
2. **Variable Quality**: Lower quality for faster processing when queue is long
3. **Early Termination**: Stop generation when user disconnects
4. **Caching**: Cache common phrases/faces for instant delivery
5. **Edge Deployment**: CDN caching for popular content
6. **WebRTC**: Real-time bidirectional streaming for interactive avatars
7. **Serverless GPU**: Monitor Cloud Run GPU preview for true serverless
8. **Third-party platforms**: Evaluate RunPod/Modal for easier scale-to-zero

---

**Last Updated**: November 9, 2025
**Version**: 2.0 (Added scale-to-zero architecture and cold start optimization)
