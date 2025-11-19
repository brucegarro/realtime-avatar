FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    pkg-config \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip wheel setuptools

# Install packages one by one to see what succeeds
# Core web framework
RUN pip install --no-cache-dir fastapi==0.109.0 uvicorn[standard]==0.27.0 pydantic==2.5.3 pydantic-settings==2.1.0

# Core ML/Audio
RUN pip install --no-cache-dir torch==2.1.2 torchaudio==2.1.2 'numpy<2.0.0'

# TTS - install without deps to avoid sudachipy (needs Rust)
RUN pip install --no-cache-dir --no-deps TTS==0.22.0 && \
    pip install --no-cache-dir \
    'cython>=0.29.30' \
    'scipy>=1.11.4' \
    'scikit-learn>=1.3.0' \
    'numba>=0.57.0' \
    'inflect>=5.6.0' \
    'tqdm>=4.64.1' \
    'anyascii>=0.3.0' \
    'pyyaml>=6.0' \
    'fsspec>=2023.6.0' \
    'aiohttp>=3.8.1' \
    'packaging>=23.1' \
    'flask>=2.0.1' \
    'pysbd>=0.3.4' \
    'pandas<2.0,>=1.4' \
    'matplotlib>=3.7.0' \
    'umap-learn>=0.5.1' \
    'trainer>=0.0.32' \
    'coqpit>=0.0.16' \
    'jieba' \
    'pypinyin' \
    'hangul_romanize' \
    'jamo' \
    'nltk' \
    'g2pkk>=0.1.1' \
    'bangla' \
    'bnnumerizer' \
    'bnunicodenormalizer' \
    'einops>=0.6.0' \
    'transformers==4.35.2' \
    'encodec>=0.1.1' \
    'unidecode>=1.3.2' \
    'num2words' \
    'gruut[de,es,fr]==2.2.3' \
    'spacy>=3'

# Audio/Video processing
RUN pip install --no-cache-dir opencv-python==4.9.0.80 pillow==10.2.0 imageio==2.33.1 imageio-ffmpeg==0.4.9
RUN pip install --no-cache-dir scipy==1.11.4 scikit-image==0.22.0
RUN pip install --no-cache-dir ffmpeg-python==0.2.0 pydub==0.25.1 librosa==0.10.1 soundfile==0.12.1

# Utilities
RUN pip install --no-cache-dir langdetect==1.0.9 python-multipart==0.0.6 aiofiles==23.2.1 httpx==0.26.0

# ASR - Faster-Whisper for Phase 4 conversation
# Using ctranslate2 >= 4.6.0 which should have executable stack issue fixed
RUN pip install --no-cache-dir faster-whisper==1.0.3 ctranslate2>=4.6.0

# Create runtime directory structure (code will come from volume mount)
RUN mkdir -p /app/runtime/models /app/runtime/pipelines /app/runtime/utils /app/runtime/workers

# Create cache directories
RUN mkdir -p /root/.cache/tts_models /root/.cache/liveportrait /tmp/rt-avatar-output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MODE=local
ENV DEVICE=cpu
ENV PYTHONPATH=/app/runtime

WORKDIR /app/runtime

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
