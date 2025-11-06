#!/bin/bash
# Setup local development environment

set -e

echo "=== Setting up Realtime Avatar Local Development ==="

# Check for required tools
echo "Checking dependencies..."
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || { echo "❌ Docker Compose is required but not installed."; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || { echo "❌ ffmpeg is required but not installed."; exit 1; }
echo "✓ All dependencies found"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file..."
    cp .env.example .env
    echo "✓ .env file created (please edit if needed)"
fi

# Extract voice samples from videos
echo ""
echo "Extracting voice samples..."
./scripts/extract_voice_samples.sh

# Build Docker images
echo ""
echo "Building Docker images..."
./scripts/build_images.sh

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the runtime service:"
echo "  docker compose up runtime"
echo ""
echo "To run the evaluator:"
echo "  docker compose --profile evaluator up evaluator"
echo ""
echo "Or start both:"
echo "  docker compose --profile evaluator up"
