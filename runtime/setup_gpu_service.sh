#!/bin/bash
# Setup and run GPU acceleration service locally

set -e

echo "🚀 GPU Service Setup"
echo "===================="
echo ""

# Check if we're in the right directory
if [ ! -f "gpu_service.py" ]; then
    echo "❌ Error: Must run from runtime/ directory"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $python_version"

# Check for MPS support
echo ""
echo "Checking GPU capabilities..."
mps_available=$(python3 -c "import torch; print('yes' if torch.backends.mps.is_available() else 'no')" 2>/dev/null || echo "no")

if [ "$mps_available" = "yes" ]; then
    echo "✅ MPS (Apple Silicon GPU) is available!"
    echo "   Your M3 will be used for 5-10x faster inference"
else
    echo "⚠️  MPS not available - will use CPU (slower)"
fi

echo ""
echo "Setting up Python environment..."

# Create venv if it doesn't exist
if [ ! -d "venv_gpu" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv_gpu
fi

# Activate venv
source venv_gpu/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip wheel setuptools > /dev/null

# Install in stages to avoid numpy version conflicts
echo "  • Installing PyTorch..."
pip install torch==2.1.2 torchaudio==2.1.2 > /dev/null

echo "  • Installing TTS (this may take a few minutes)..."
pip install TTS==0.22.0 > /dev/null

echo "  • Installing Transformers..."
pip install transformers==4.35.2 > /dev/null

echo "  • Installing audio libraries..."
pip install soundfile==0.12.1 librosa==0.10.1 > /dev/null

echo "  • Installing API framework..."
pip install fastapi==0.109.0 uvicorn[standard]==0.27.0 pydantic==2.5.3 > /dev/null

echo "  • Installing utilities..."
pip install httpx==0.26.0 python-multipart==0.0.6 aiofiles==23.2.1 > /dev/null

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the GPU service:"
echo "  1. source venv_gpu/bin/activate"
echo "  2. python gpu_service.py"
echo ""
echo "Or use the run script:"
echo "  ./run_gpu_service.sh"
echo ""
