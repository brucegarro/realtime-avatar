#!/bin/bash
# Test script for streaming conversation endpoint

# Test audio file (you should have one from previous tests)
TEST_AUDIO="/tmp/test_audio.wav"

# Check if test audio exists
if [ ! -f "$TEST_AUDIO" ]; then
    echo "Test audio not found. Creating a simple test audio..."
    # Generate 3 seconds of silence as test audio
    sox -n -r 16000 -c 1 "$TEST_AUDIO" trim 0 3
fi

echo "Testing streaming conversation endpoint..."
echo "Sending request to http://localhost:8000/api/v1/conversation/stream"
echo ""

curl -X POST http://localhost:8000/api/v1/conversation/stream \
  -F "audio=@${TEST_AUDIO}" \
  -F "language=en" \
  -N \
  --no-buffer \
  2>&1 | while IFS= read -r line; do
    echo "$line"
  done
