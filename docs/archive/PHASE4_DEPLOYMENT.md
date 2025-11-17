# Phase 4 Hybrid Deployment - Quick Start Guide

Complete guide for deploying the Phase 4 interactive conversation system.

## Architecture

```
┌─────────────────────┐              ┌──────────────────────────────┐
│   Your Mac          │              │   GCP L4 GPU Instance        │
│   (Local)           │              │   (us-east1-c)               │
│                     │              │                              │
│  ┌───────────────┐  │              │  ┌────────────────────────┐  │
│  │ Web Container │  │   HTTP/80    │  │  Runtime Container     │  │
│  │   (Nginx)     │──┼─────────────▶│  │    (FastAPI)          │  │
│  │ localhost:8080│  │              │  │  - ASR (Whisper)       │  │
│  └───────────────┘  │              │  │  - LLM (Qwen-2.5)      │  │
│                     │              │  │  - TTS (XTTS)          │  │
│                     │              │  │  - Ditto TensorRT      │  │
│                     │              │  │  Port: 8000            │  │
│                     │              │  └────────────────────────┘  │
└─────────────────────┘              └──────────────────────────────┘
                                     2x RTF Performance ⚡
```

## Prerequisites

- ✅ GCP account with Compute Engine enabled
- ✅ Docker Desktop installed on Mac
- ✅ gcloud CLI configured (`gcloud auth login`)
- ✅ Project ID: `realtime-avatar-bg`

## Step 1: Create/Verify GCP L4 Instance

```bash
# Check if instance exists
gcloud compute instances describe realtime-avatar --zone=us-east1-c

# If not exists, create it:
gcloud compute instances create realtime-avatar \
  --project=realtime-avatar-bg \
  --zone=us-east1-c \
  --machine-type=g2-standard-4 \
  --accelerator=type=nvidia-l4,count=1 \
  --maintenance-policy=TERMINATE \
  --boot-disk-size=200GB \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=http-server

# Ensure firewall allows port 8000
gcloud compute firewall-rules create allow-http-8000 \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:8000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=http-server
```

## Step 2: Deploy Backend to GCP

```bash
cd /Users/brucegarro/project/realtime-avatar/scripts/

# Run deployment script
./deploy_gcp_backend.sh
```

This script will:
1. ✅ Verify GCP instance is running
2. ✅ Upload Phase 4 files (conversation_pipeline.py, app.py, models/)
3. ✅ Rebuild runtime container with new code
4. ✅ Restart services
5. ✅ Verify health check

**Expected output:**
```
================================================
✅ Backend Deployed Successfully!
================================================

Backend API: http://34.73.XXX.XXX:8000

Available Endpoints:
  GET  /health
  POST /api/v1/conversation    - Phase 4 (audio → video)
```

## Step 3: Configure Local Web UI

```bash
cd /Users/brucegarro/project/realtime-avatar/web/

# Get GCP instance IP
GCP_IP=$(gcloud compute instances describe realtime-avatar \
  --zone=us-east1-c \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "GCP IP: $GCP_IP"

# Configure web app to connect to GCP backend
./configure_web.sh $GCP_IP
```

This updates `app.js` to point to your GCP backend.

## Step 4: Run Web Container Locally

```bash
cd /Users/brucegarro/project/realtime-avatar/web/

# Build and start web container
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
```

**Expected output:**
```
✔ Container realtime-avatar-web  Started
```

## Step 5: Access Web App

Open your browser to: **http://localhost:8080**

### First Use:
1. Browser will request microphone permission → **Allow**
2. Status indicator shows "Ready" (green dot)
3. Hold microphone button to record
4. Release to send
5. Wait ~35s for processing
6. Avatar video plays automatically

## Verification

### Test Backend Health

```bash
# From your Mac
GCP_IP=$(gcloud compute instances describe realtime-avatar \
  --zone=us-east1-c \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

curl http://$GCP_IP:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "mode": "gpu",
  "device": "cuda",
  "models_loaded": true
}
```

### Test Web UI

```bash
curl http://localhost:8080
# Should return HTML
```

### Monitor Backend Logs

```bash
gcloud compute ssh realtime-avatar --zone=us-east1-c \
  --command='docker compose logs -f runtime'
```

## Expected Performance (L4 GPU)

| Component | Time | Notes |
|-----------|------|-------|
| ASR (Transcription) | 1-2s | Faster-Whisper base model |
| LLM (Response) | 3-5s | Qwen-2.5-7B on CPU |
| TTS (Voice Clone) | 0.70x RTF | XTTS-v2 faster than realtime |
| Video (Lip Sync) | 1.23x RTF | Ditto TensorRT optimization |
| **Full Pipeline** | **~35s** | For 17s audio input |

## Usage Guide

### Push-to-Talk

**Desktop:**
- Hold microphone button to record
- Or hold spacebar

**Mobile:**
- Touch and hold microphone button

### Settings

Click "⚙️ Settings" to configure:
- **Language**: English, 中文, Español
- **Auto-play**: Play videos automatically
- **Save history**: Persist conversation in browser

### Conversation Flow

1. **Record** (1-5 seconds recommended)
2. **Transcription** (~1-2s) → Shows "You: [your text]"
3. **LLM Response** (~3-5s) → Shows "Bruce: [response]"
4. **Video Generation** (~20-30s) → Progress indicator
5. **Playback** → Avatar video with lip sync

## Troubleshooting

### Issue: Web UI shows "Server offline"

```bash
# Check GCP instance is running
gcloud compute instances describe realtime-avatar --zone=us-east1-c

# Start if stopped
gcloud compute instances start realtime-avatar --zone=us-east1-c

# Check backend health
curl http://$GCP_IP:8000/health
```

### Issue: CORS error in browser console

Backend already has CORS enabled. If issue persists:

```bash
# SSH to GCP instance
gcloud compute ssh realtime-avatar --zone=us-east1-c

# Check runtime container logs
docker compose logs runtime | grep -i cors
```

### Issue: Microphone not working

- Grant microphone permission in browser
- Check browser console for errors
- Try different browser (Chrome/Firefox recommended)
- Ensure served from localhost or HTTPS

### Issue: Long generation time

**Expected:** ~35s for 17s audio (this is normal!)

L4 GPU with TensorRT achieves 1.95x RTF:
- Faster than PyTorch (3.79x RTF)
- Near real-time performance
- Best available without streaming

### Issue: Video won't play

```bash
# Check video was generated
gcloud compute ssh realtime-avatar --zone=us-east1-c \
  --command='ls -lh ~/realtime-avatar/outputs/conversations/'

# Check video URL in browser Network tab
# Should be: http://GCP_IP:8000/api/v1/videos/conversation_XXXXX.mp4
```

## Cost Optimization

### Stop Instance When Not Using

```bash
# Stop (saves disk, stops compute billing)
gcloud compute instances stop realtime-avatar --zone=us-east1-c

# Start when needed
gcloud compute instances start realtime-avatar --zone=us-east1-c
```

**Cost:** L4 GPU instance ~$0.60-1.00/hour depending on region

### Auto-Shutdown Script

Create scheduled shutdown:
```bash
# Auto-shutdown at midnight
gcloud compute instances add-metadata realtime-avatar \
  --zone=us-east1-c \
  --metadata=shutdown-script='#!/bin/bash
if [ $(date +%H) -eq 0 ]; then
  sudo shutdown -h now
fi'
```

## Updating Code

### Update Backend (GCP)

```bash
# Make changes locally, then redeploy
cd /Users/brucegarro/project/realtime-avatar/scripts/
./deploy_gcp_backend.sh
```

### Update Web UI (Local)

```bash
cd /Users/brucegarro/project/realtime-avatar/web/

# Make changes to index.html, app.js, styles.css
# Then rebuild
docker compose up -d --build
```

## Useful Commands

```bash
# Get GCP instance IP
gcloud compute instances describe realtime-avatar \
  --zone=us-east1-c \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# SSH to instance
gcloud compute ssh realtime-avatar --zone=us-east1-c

# View backend logs
gcloud compute ssh realtime-avatar --zone=us-east1-c \
  --command='docker compose logs -f runtime'

# View web logs locally
docker compose logs -f web

# Restart everything
gcloud compute ssh realtime-avatar --zone=us-east1-c \
  --command='docker compose restart'

# Check disk usage on GCP
gcloud compute ssh realtime-avatar --zone=us-east1-c \
  --command='df -h'
```

## Next Steps

Once verified working:

1. **Test different languages** (English, Chinese, Spanish)
2. **Test longer/shorter audio inputs**
3. **Monitor costs** in GCP Console
4. **Add authentication** for production use
5. **Implement conversation memory** (session-based)
6. **Deploy web UI to cloud** (Cloud Run, Vercel, etc.)

## Support

- **Backend issues**: Check `docker compose logs runtime` on GCP
- **Web UI issues**: Check browser console + `docker compose logs web` locally
- **Network issues**: Verify firewall rules and CORS configuration
- **Performance issues**: Confirm L4 GPU is being used on GCP instance

---

**Status:** Phase 4 Complete ✅  
**Performance:** 2x RTF (near real-time)  
**Ready for:** Interactive voice conversations with avatar responses
