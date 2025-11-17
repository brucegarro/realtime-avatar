# Realtime Avatar - Deployment Guide

Complete deployment guide for the interactive conversation avatar system.

**Last Updated:** November 16, 2025  
**Status:** Phase 4 Complete | Deployment Ready

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Deploy (Recommended)](#quick-deploy)
3. [Manual Deployment](#manual-deployment)
4. [Local Development](#local-development)
5. [Testing & Validation](#testing--validation)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Components

```
┌──────────────────────┐              ┌───────────────────────────────┐
│   Local Machine      │              │   GCP L4 GPU Instance         │
│                      │              │   (g2-standard-4)             │
│  ┌────────────────┐  │              │                               │
│  │  Web UI        │  │   HTTPS      │  ┌─────────────────────────┐  │
│  │  (Nginx)       │──┼─────────────▶│  │  FastAPI Runtime        │  │
│  │  Port: 8080    │  │              │  │  Port: 8000             │  │
│  └────────────────┘  │              │  │  - Conversation API     │  │
│  - Voice recording   │              │  │  - ASR (Whisper large)  │  │
│  - Video playback    │              │  │  - LLM (Qwen-2.5)       │  │
│  - Push-to-talk      │              │  │  - TTS (XTTS-v2)        │  │
│                      │              │  │  - Video (Ditto TRT)    │  │
└──────────────────────┘              │  └─────────────────────────┘  │
                                      │                               │
                                      │  ┌─────────────────────────┐  │
                                      │  │  GPU Service            │  │
                                      │  │  Port: 8001             │  │
                                      │  │  - TTS generation       │  │
                                      │  │  - Video synthesis      │  │
                                      │  │  - TensorRT inference   │  │
                                      │  └─────────────────────────┘  │
                                      └───────────────────────────────┘
                                      Performance: ~35-40s per turn
```

### Technology Stack

**Backend (GCP L4 GPU):**
- Docker containers with NVIDIA runtime
- FastAPI for REST APIs
- Whisper large-v3 for ASR
- Qwen-2.5-7B for conversation
- XTTS-v2 for voice synthesis
- Ditto + TensorRT for video (2x RTF)

**Frontend (Local):**
- Nginx static file server
- Vanilla JavaScript (no frameworks)
- MediaRecorder API for audio capture
- HTML5 video playback

**Infrastructure:**
- GCP Compute Engine (g2-standard-4)
- NVIDIA L4 GPU (24GB VRAM)
- 100GB+ disk for models
- Ubuntu 22.04 LTS

---

## Quick Deploy

One command deployment using automated script:

### Step 1: Prepare GCP Instance

```bash
# Create fresh instance with 100GB disk
gcloud compute instances create realtime-avatar-test \
  --project=realtime-avatar-bg \
  --zone=us-east1-c \
  --machine-type=g2-standard-4 \
  --accelerator=type=nvidia-l4,count=1 \
  --maintenance-policy=TERMINATE \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-balanced \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --scopes=cloud-platform \
  --tags=http-server \
  --metadata=enable-oslogin=FALSE

# Wait 30 seconds for boot
sleep 30
```

### Step 2: Run Deployment Script

```bash
# From project root
./deploy_phase4_hybrid.sh
```

This script will:
1. ✅ Upload Phase 4 files to GCP
2. ✅ Install Docker + NVIDIA drivers
3. ✅ Build containers (runtime + GPU service)
4. ✅ Start services
5. ✅ Configure web UI with backend IP
6. ✅ Start local web container

**Estimated Time:** 20-30 minutes (first deployment)

### Step 3: Access Web UI

```bash
# Open in browser
open http://localhost:8080
```

**That's it!** The system is ready to use.

---

## Manual Deployment

For step-by-step control or troubleshooting:

### 1. Create GCP Instance

```bash
gcloud compute instances create realtime-avatar-test \
  --project=realtime-avatar-bg \
  --zone=us-east1-c \
  --machine-type=g2-standard-4 \
  --accelerator=type=nvidia-l4,count=1 \
  --maintenance-policy=TERMINATE \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-balanced \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --scopes=cloud-platform \
  --tags=http-server \
  --metadata=enable-oslogin=FALSE

# Get instance IP
INSTANCE_IP=$(gcloud compute instances describe realtime-avatar-test \
  --zone=us-east1-c --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "Instance IP: $INSTANCE_IP"
```

### 2. Install Docker & NVIDIA Tools

```bash
# SSH to instance
gcloud compute ssh realtime-avatar-test --zone=us-east1-c

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# Install NVIDIA drivers
sudo apt-get update
sudo apt-get install -y nvidia-driver-550

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Reboot to load NVIDIA drivers
sudo reboot
```

### 3. Upload Project Files

```bash
# From local machine, create directory structure
gcloud compute ssh realtime-avatar-test --zone=us-east1-c --command='
  mkdir -p ~/realtime-avatar/runtime/{pipelines,models,utils,workers}
  mkdir -p ~/realtime-avatar/web
'

# Upload Phase 4 files
cd /path/to/realtime-avatar

gcloud compute scp --zone=us-east1-c --recurse \
  runtime/pipelines/conversation_pipeline.py \
  realtime-avatar-test:~/realtime-avatar/runtime/pipelines/

gcloud compute scp --zone=us-east1-c \
  runtime/app.py \
  realtime-avatar-test:~/realtime-avatar/runtime/

gcloud compute scp --zone=us-east1-c --recurse \
  runtime/models/*.py \
  realtime-avatar-test:~/realtime-avatar/runtime/models/

gcloud compute scp --zone=us-east1-c --recurse \
  runtime/utils/*.py \
  realtime-avatar-test:~/realtime-avatar/runtime/utils/

gcloud compute scp --zone=us-east1-c --recurse \
  runtime/workers/*.py \
  realtime-avatar-test:~/realtime-avatar/runtime/workers/

gcloud compute scp --zone=us-east1-c \
  docker-compose.yml runtime/Dockerfile runtime/Dockerfile.ditto \
  runtime/config.py runtime/requirements.txt runtime/gpu_service.py \
  realtime-avatar-test:~/realtime-avatar/runtime/
```

### 4. Build & Start Containers

```bash
# SSH to instance
gcloud compute ssh realtime-avatar-test --zone=us-east1-c

cd ~/realtime-avatar/runtime

# Build containers (takes ~15 minutes)
docker compose build

# Start services
docker compose up -d

# Verify running
docker compose ps

# Check logs
docker compose logs -f
```

### 5. Configure Web UI

```bash
# On local machine
cd web

# Configure backend IP
./configure_web.sh $INSTANCE_IP

# Start web container
docker compose up -d

# Check status
docker compose ps
```

### 6. Test Deployment

```bash
# Health check
curl http://$INSTANCE_IP:8000/health

# Test transcription
curl -X POST http://$INSTANCE_IP:8000/api/v1/transcribe \
  -F "audio=@test_audio.wav"

# Open web UI
open http://localhost:8080
```

---

## Local Development

For local testing without GCP:

### Setup GPU Service (M3 Mac)

```bash
cd runtime

# Setup and start GPU service
./setup_gpu_service.sh
./run_gpu_service.sh &

# Verify GPU service
curl http://localhost:8001/health
```

### Start Runtime API

```bash
# Option 1: Docker
docker compose up runtime

# Option 2: Direct Python
python3 -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Start Web UI

```bash
cd web

# Configure for localhost
./configure_web.sh localhost

# Start nginx
docker compose up -d
```

### Test Local Setup

```bash
# Open browser
open http://localhost:8080

# Or test API directly
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "language": "en"}'
```

---

## Testing & Validation

### Health Checks

```bash
# Backend health
curl http://$INSTANCE_IP:8000/health
# Expected: {"status": "healthy", "models": {"asr": true, "llm": true, ...}}

# GPU service health
curl http://$INSTANCE_IP:8001/health
# Expected: {"status": "healthy", "gpu": "available"}

# Web UI
curl http://localhost:8080
# Expected: HTML content
```

### API Testing

**1. Transcription Test:**
```bash
# Record a short audio clip
# test_audio.wav (3-5 seconds, 16kHz, mono)

curl -X POST http://$INSTANCE_IP:8000/api/v1/transcribe \
  -F "audio=@test_audio.wav"

# Expected response:
# {"text": "transcribed text here", "language": "en"}
```

**2. Chat Test:**
```bash
curl -X POST http://$INSTANCE_IP:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'

# Expected response:
# {"response": "I'm doing well, thank you! How can I help you today?"}
```

**3. Full Conversation Test:**
```bash
# This tests the full pipeline: ASR → LLM → TTS → Video
curl -X POST http://$INSTANCE_IP:8000/api/v1/conversation \
  -F "audio=@test_audio.wav" \
  --output response_video.mp4

# Expected: video file with avatar response (~35-40s generation time)
```

### Performance Validation

Expected performance on L4 GPU:

| Component | Target RTF | Expected Time (17s audio) |
|-----------|------------|---------------------------|
| ASR (Whisper) | - | ~2s |
| LLM (Qwen) | - | ~5s |
| TTS (XTTS) | 0.70x | ~12s |
| Video (Ditto TRT) | 1.23x | ~21s |
| **Total Pipeline** | - | **~35-40s** |

### Web UI Testing

1. **Open**: http://localhost:8080
2. **Click** "Start Recording"
3. **Speak**: "Hello, tell me about yourself"
4. **Click** "Stop Recording"
5. **Wait**: ~35-40 seconds
6. **Verify**: Video plays with lip-synced avatar

---

## Troubleshooting

### Common Issues

#### 1. SSH Connection Fails

```bash
# Regenerate SSH keys
rm -rf ~/.ssh/google_compute_*
gcloud compute config-ssh
gcloud compute ssh realtime-avatar-test --zone=us-east1-c
```

#### 2. Docker Not Found

```bash
# Reinstall Docker
gcloud compute ssh realtime-avatar-test --zone=us-east1-c
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
logout
# SSH back in
```

#### 3. NVIDIA Driver Issues

```bash
# Check driver
nvidia-smi

# If fails, reinstall
sudo apt-get purge nvidia-*
sudo apt-get install -y nvidia-driver-550
sudo reboot
```

#### 4. Container Build Fails (Disk Space)

```bash
# Check disk usage
df -h

# Clean Docker
docker system prune -af
docker volume prune -f

# If still insufficient, resize disk
gcloud compute disks resize realtime-avatar-test \
  --size=150GB --zone=us-east1-c

# Resize filesystem
sudo growpart /dev/sda 1
sudo resize2fs /dev/sda1
```

#### 5. Model Download Fails

```bash
# Check internet connectivity
ping 8.8.8.8

# Check disk space
df -h /

# Restart container to retry download
docker compose restart gpu-service
docker compose logs -f gpu-service
```

#### 6. Web UI Can't Connect to Backend

```bash
# Check backend IP in web/app.js
grep API_BASE_URL web/app.js

# Should show: const API_BASE_URL = 'http://INSTANCE_IP:8000';

# Reconfigure
cd web
./configure_web.sh $INSTANCE_IP
docker compose restart
```

#### 7. Performance Lower Than Expected

```bash
# Check GPU utilization
nvidia-smi

# Check CPU/memory
htop

# Check container logs
docker compose logs gpu-service | tail -100

# Verify TensorRT is being used
docker compose logs gpu-service | grep -i tensorrt
# Should see: "Using TensorRT for video generation"
```

### Debug Commands

```bash
# View all logs
docker compose logs -f

# Exec into container
docker exec -it realtime-avatar-runtime bash

# Check GPU inside container
docker exec -it realtime-avatar-gpu nvidia-smi

# Monitor resource usage
docker stats

# Check network connectivity
docker compose exec runtime curl http://gpu-service:8001/health
```

### Getting Help

**Check Documentation:**
- `PROJECT_STATUS.md` - Current phase and achievements
- `PERFORMANCE.md` - Benchmark results
- `SETUP.md` - Detailed setup instructions

**Review Logs:**
```bash
# Application logs
docker compose logs runtime
docker compose logs gpu-service

# System logs
journalctl -u docker -f
dmesg | grep -i nvidia
```

**Common Log Patterns:**

- ✅ `"Model loaded successfully"` - Good
- ❌ `"CUDA out of memory"` - Reduce batch size
- ❌ `"No space left on device"` - Increase disk
- ❌ `"Connection refused"` - Check service ports

---

## Cost Optimization

### Stop Instance When Not in Use

```bash
# Stop instance (saves compute costs)
gcloud compute instances stop realtime-avatar-test --zone=us-east1-c

# Start when needed
gcloud compute instances start realtime-avatar-test --zone=us-east1-c
```

### Estimated Costs (GCP)

- **Running:** ~$0.80/hour (g2-standard-4 with L4)
- **Stopped:** ~$16/month (100GB disk storage only)
- **Monthly (24/7):** ~$600/month
- **Monthly (8hrs/day):** ~$200/month

### Recommendations

- Stop instance outside business hours
- Use preemptible instances for testing (50-80% cheaper)
- Consider Cloud Run GPU for auto-scaling (coming soon)

---

## Next Steps

**Completed:**
- ✅ Phase 4 conversation pipeline
- ✅ Web UI with voice input
- ✅ TensorRT video acceleration
- ✅ Hybrid deployment model

**Future Enhancements:**
- 🔜 Cloud Run GPU deployment
- 🔜 WebSocket streaming
- 🔜 Multi-user support
- 🔜 Voice activity detection
- 🔜 Custom avatar training

**Performance Targets:**
- Current: ~35-40s per turn
- Goal: <20s per turn (future optimization)

---

## Quick Reference

### Instance Details
- **Name:** realtime-avatar-test
- **Zone:** us-east1-c
- **Machine:** g2-standard-4
- **GPU:** NVIDIA L4 (24GB)
- **Disk:** 100GB balanced PD

### Ports
- **8000:** FastAPI runtime (external)
- **8001:** GPU service (internal)
- **8080:** Web UI (local)

### Key Files
- `deploy_phase4_hybrid.sh` - One-command deployment
- `docker-compose.yml` - Service orchestration
- `runtime/app.py` - Main API server
- `runtime/pipelines/conversation_pipeline.py` - Conversation logic
- `web/index.html` - Web UI
- `web/app.js` - Frontend logic

### Quick Commands
```bash
# Deploy everything
./deploy_phase4_hybrid.sh

# Check status
gcloud compute instances list
docker compose ps

# View logs
docker compose logs -f

# Stop instance
gcloud compute instances stop realtime-avatar-test --zone=us-east1-c

# Restart services
docker compose restart
```

---

**Last Updated:** November 16, 2025  
**Version:** Phase 4.0  
**Status:** Production Ready ✅
