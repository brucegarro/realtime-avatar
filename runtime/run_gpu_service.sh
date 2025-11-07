#!/bin/bash
# Run GPU acceleration service

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if venv exists
if [ ! -d "venv_gpu" ]; then
    echo "❌ Virtual environment not found. Run ./setup_gpu_service.sh first"
    exit 1
fi

# Activate venv
source venv_gpu/bin/activate

# Check MPS
mps_status=$(python3 -c "import torch; print('MPS' if torch.backends.mps.is_available() else 'CPU')")

echo "🚀 Starting GPU Service..."
echo "   Device: $mps_status"
echo "   Port: 8001"
echo "   Endpoints:"
echo "     - http://localhost:8001/health"
echo "     - http://localhost:8001/tts/generate"
echo ""

# Set environment
export HOST=0.0.0.0
export PORT=8001
export COQUI_TOS_AGREED=1

# Run service
python gpu_service.py
