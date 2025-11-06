#!/bin/bash
# Extract voice samples from video files for XTTS-v2 training

set -e

echo "=== Extracting voice samples from videos ==="

ASSETS_DIR="./assets"
VIDEOS_DIR="$ASSETS_DIR/videos"
SAMPLES_DIR="$ASSETS_DIR/voice/reference_samples"

# Create samples directory if it doesn't exist
mkdir -p "$SAMPLES_DIR"

# Extract audio from English video (5-10 seconds)
if [ -f "$VIDEOS_DIR/bruce_english.mp4" ]; then
    echo "Extracting English sample..."
    ffmpeg -y -i "$VIDEOS_DIR/bruce_english.mp4" \
        -ss 00:00:05 -t 00:00:10 \
        -ar 22050 -ac 1 \
        "$SAMPLES_DIR/bruce_en_sample.wav"
    echo "✓ English sample created"
fi

# Extract audio from Mandarin video
if [ -f "$VIDEOS_DIR/bruce_mandarin.mp4" ]; then
    echo "Extracting Mandarin sample..."
    ffmpeg -y -i "$VIDEOS_DIR/bruce_mandarin.mp4" \
        -ss 00:00:05 -t 00:00:10 \
        -ar 22050 -ac 1 \
        "$SAMPLES_DIR/bruce_zh_sample.wav"
    echo "✓ Mandarin sample created"
fi

# Extract audio from Spanish video
if [ -f "$VIDEOS_DIR/bruce_spanish.mp4" ]; then
    echo "Extracting Spanish sample..."
    ffmpeg -y -i "$VIDEOS_DIR/bruce_spanish.mp4" \
        -ss 00:00:05 -t 00:00:10 \
        -ar 22050 -ac 1 \
        "$SAMPLES_DIR/bruce_es_sample.wav"
    echo "✓ Spanish sample created"
fi

echo ""
echo "=== Voice samples extracted ==="
ls -lh "$SAMPLES_DIR"
