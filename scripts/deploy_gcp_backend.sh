#!/bin/bash
# Deploy Phase 4 Backend to GCP L4 GPU Instance
# Usage: ./deploy_gcp_backend.sh

set -e

# Configuration
PROJECT_ID="realtime-avatar-bg"
ZONE="us-east1-c"
INSTANCE_NAME="realtime-avatar-test"

echo "================================================"
echo "Phase 4 Backend Deployment to GCP L4 GPU"
echo "================================================"
echo ""

# Check if instance exists
echo "Checking for instance '$INSTANCE_NAME'..."
if ! gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &>/dev/null; then
    echo "❌ Instance not found!"
    echo ""
    echo "Create instance first with:"
    echo "  gcloud compute instances create $INSTANCE_NAME \\"
    echo "    --project=$PROJECT_ID \\"
    echo "    --zone=$ZONE \\"
    echo "    --machine-type=g2-standard-4 \\"
    echo "    --accelerator=type=nvidia-l4,count=1 \\"
    echo "    --maintenance-policy=TERMINATE \\"
    echo "    --boot-disk-size=200GB \\"
    echo "    --image-family=ubuntu-2204-lts \\"
    echo "    --image-project=ubuntu-os-cloud \\"
    echo "    --tags=http-server"
    exit 1
fi

# Get instance IP
INSTANCE_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
  --zone="$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "✓ Found instance: $INSTANCE_IP"
echo ""

# Check instance status
INSTANCE_STATUS=$(gcloud compute instances describe "$INSTANCE_NAME" \
  --zone="$ZONE" \
  --format='get(status)')

if [ "$INSTANCE_STATUS" != "RUNNING" ]; then
    echo "Instance is $INSTANCE_STATUS. Starting..."
    gcloud compute instances start "$INSTANCE_NAME" --zone="$ZONE"
    echo "Waiting for instance to be ready..."
    sleep 30
fi

echo "Creating directory structure on instance..."
echo ""

# Create directory structure
gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='
  mkdir -p ~/realtime-avatar/runtime/pipelines
  mkdir -p ~/realtime-avatar/runtime/models
  mkdir -p ~/realtime-avatar/runtime/utils
  mkdir -p ~/realtime-avatar/runtime/workers
  mkdir -p ~/realtime-avatar/web
'

echo "Uploading Phase 4 files to instance..."
echo ""

# Upload runtime files
gcloud compute scp \
  --zone="$ZONE" \
  --recurse \
  ../runtime/pipelines/conversation_pipeline.py \
  "$INSTANCE_NAME:~/realtime-avatar/runtime/pipelines/"

gcloud compute scp \
  --zone="$ZONE" \
  ../runtime/app.py \
  "$INSTANCE_NAME:~/realtime-avatar/runtime/"

# Upload model files (excluding __pycache__)
gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='mkdir -p ~/realtime-avatar/runtime/models'
gcloud compute scp \
  --zone="$ZONE" \
  ../runtime/models/*.py \
  "$INSTANCE_NAME:~/realtime-avatar/runtime/models/"

echo "✓ Files uploaded"
echo ""

# Restart services on instance
echo "Restarting runtime service..."
gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='
set -e
cd ~/realtime-avatar

echo "Building updated runtime container..."
docker compose build runtime

echo "Restarting services..."
docker compose down
docker compose up -d

echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "Checking service health..."
docker compose ps
echo ""

# Test health endpoint
curl -f http://localhost:8000/health && echo "" || echo "⚠️  Health check failed"
'

echo ""
echo "================================================"
echo "✅ Backend Deployed Successfully!"
echo "================================================"
echo ""
echo "Backend API: http://$INSTANCE_IP:8000"
echo ""
echo "Available Endpoints:"
echo "  GET  /health"
echo "  POST /api/v1/generate        - Phase 1 (text → video)"
echo "  POST /api/v1/transcribe      - Phase 4 (audio → text)"
echo "  POST /api/v1/chat            - Phase 4 (text → response)"
echo "  POST /api/v1/conversation    - Phase 4 (audio → video)"
echo ""
echo "Test the deployment:"
echo "  curl http://$INSTANCE_IP:8000/health"
echo ""
echo "Configure local web UI:"
echo "  cd web/"
echo "  ./configure_web.sh $INSTANCE_IP"
echo "  docker compose up -d --build"
echo ""
echo "Monitor logs:"
echo "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='docker compose logs -f runtime'"
echo ""
