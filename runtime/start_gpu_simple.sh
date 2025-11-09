#!/bin/bash
# Start GPU Service (simplified version without config dependency issues)

set -e

cd /Users/brucegarro/project/realtime-avatar/runtime

# Set environment variables
export PYTORCH_ENABLE_MPS_FALLBACK=1
export PYTHONPATH=/Users/brucegarro/project/realtime-avatar/runtime:$PYTHONPATH

echo "Starting GPU Service on port 8001..."

# Run with venv_gpu python
exec ./venv_gpu/bin/python gpu_service.py
