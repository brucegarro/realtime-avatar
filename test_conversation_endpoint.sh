#!/bin/bash
# Automated test for conversation endpoint
# Usage: ./test_conversation_endpoint.sh

set -e

ZONE="us-east1-c"
INSTANCE="realtime-avatar-test"
AUDIO_FILE="runtime/assets/voice/reference_samples/bruce_en_sample.wav"

echo "🧪 Testing Conversation Endpoint"
echo "================================"
echo ""

# Check if instance is running
echo "📡 Checking GCP instance..."
STATUS=$(gcloud compute instances describe $INSTANCE --zone=$ZONE --format="get(status)")
if [ "$STATUS" != "RUNNING" ]; then
  echo "❌ Instance is not running (status: $STATUS)"
  exit 1
fi
echo "✅ Instance is running"
echo ""

# Check if services are up
echo "🐳 Checking Docker services..."
gcloud compute ssh $INSTANCE --zone=$ZONE --command='cd ~/realtime-avatar && docker compose ps --format json' 2>/dev/null | grep -q "running" || {
  echo "❌ Services are not running"
  exit 1
}
echo "✅ Services are running"
echo ""

# Test health endpoint
echo "💊 Testing health endpoint..."
HEALTH=$(gcloud compute ssh $INSTANCE --zone=$ZONE --command='curl -s http://localhost:8000/health' 2>/dev/null)
if echo "$HEALTH" | grep -q "status"; then
  echo "✅ Health check passed"
else
  echo "❌ Health check failed"
  echo "$HEALTH"
  exit 1
fi
echo ""

# Test conversation endpoint
echo "🎤 Testing conversation endpoint..."
echo "   Using audio file: $AUDIO_FILE"
echo ""

RESPONSE=$(gcloud compute ssh $INSTANCE --zone=$ZONE --command="
curl -X POST http://localhost:8000/api/v1/conversation \\
  -F 'audio=@/root/realtime-avatar/$AUDIO_FILE' \\
  -F 'language=en' \\
  -s \\
  -w '\\nHTTP_CODE:%{http_code}' \\
  --max-time 90
" 2>&1)

# Extract HTTP code
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
RESPONSE_BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "📊 Response:"
echo "   HTTP Status: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ TEST PASSED!"
  echo ""
  echo "Response preview:"
  echo "$RESPONSE_BODY" | head -20
else
  echo "❌ TEST FAILED!"
  echo ""
  echo "Error response:"
  echo "$RESPONSE_BODY"
  echo ""
  echo "🔍 Checking logs for errors..."
  gcloud compute ssh $INSTANCE --zone=$ZONE --command='docker logs realtime-avatar-runtime 2>&1 | tail -30'
  exit 1
fi
