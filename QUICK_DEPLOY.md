# Quick Deploy Guide

## Hot Reload Setup (Development Mode)

The runtime container now uses **volume mounts** for instant code updates without rebuilding.

### Making Code Changes

**Option 1: Automatic Sync (Recommended)**
```bash
# Edit files locally, then sync to GCP
gcloud compute scp runtime/pipelines/conversation_pipeline.py \
  realtime-avatar-test:~/realtime-avatar/runtime/pipelines/ \
  --zone=us-east1-c

# Restart container (2-3 seconds)
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='cd ~/realtime-avatar && docker compose restart runtime'
```

**Option 2: Sync Entire Directory**
```bash
# Sync all changes at once
gcloud compute scp --recurse runtime/ \
  realtime-avatar-test:~/realtime-avatar/ \
  --zone=us-east1-c

# Restart
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='cd ~/realtime-avatar && docker compose restart runtime'
```

### What Requires a Rebuild?

✅ **No Rebuild Needed** (just restart):
- Python code changes (`.py` files)
- Config files
- Templates/static files

❌ **Rebuild Required**:
- Dockerfile changes
- `requirements.txt` changes
- System package installations

### Rebuild Command
```bash
# Only needed when dependencies change
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='cd ~/realtime-avatar && docker compose up -d --build runtime'
```

## Testing the Conversation Endpoint

### Browser Test
1. Open http://localhost:8080
2. Click microphone button
3. Speak for 2-5 seconds
4. Click again to send
5. Wait 20-40s for response

### Monitor Logs
```bash
# Watch runtime logs in real-time
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='docker logs -f realtime-avatar-runtime'

# Watch GPU service logs
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='docker logs -f realtime-avatar-gpu'
```

## Common Issues

### 500 Error After Code Change
```bash
# Check logs for the error
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='docker logs realtime-avatar-runtime 2>&1 | tail -50'

# Restart if needed
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='cd ~/realtime-avatar && docker compose restart runtime'
```

### Code Not Updating
```bash
# Verify file was synced
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='ls -la ~/realtime-avatar/runtime/pipelines/'

# Force restart
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='cd ~/realtime-avatar && docker compose down && docker compose up -d'
```

## Cost Saving

```bash
# Stop instance when not testing ($0.80/hour saved)
gcloud compute instances stop realtime-avatar-test --zone=us-east1-c

# Start when needed
gcloud compute instances start realtime-avatar-test --zone=us-east1-c

# Wait for startup, then start services
sleep 60
gcloud compute ssh realtime-avatar-test --zone=us-east1-c \
  --command='cd ~/realtime-avatar && docker compose up -d'
```

## Performance

- **Before**: 10-15 minute rebuild for every code change
- **After**: 2-3 second restart for code changes
- **Speedup**: ~200-300x faster iteration! 🚀
