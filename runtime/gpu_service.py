#!/usr/bin/env python3
"""
GPU Acceleration Service
Runs ML inference tasks on GPU (MPS locally, CUDA remotely)

Supports:
- TTS (XTTS-v2)
- Video Generation (SadTalker)
- Lip Sync - future
- Any GPU-accelerated ML task

Deployment modes:
- Local: Mac M3 with MPS acceleration
- Remote: GCP GPU instance with CUDA
"""
import os
import sys

# Enable MPS fallback for operations not yet implemented (like grid_sampler_3d)
# Most operations still use GPU, only unsupported ones fall back to CPU
os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'

import torch
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
import uvicorn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from models.tts import XTTSModel
from models.sadtalker_model import SadTalkerModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GPU Acceleration Service",
    description="ML inference service for TTS, video generation, and other GPU tasks",
    version="1.0"
)

# Global models
tts_model = None
avatar_model = None  # SadTalker for video generation
# lipsync_model = None  # Future


def detect_device() -> str:
    """Auto-detect best available device"""
    if torch.backends.mps.is_available():
        return "mps"  # Apple Silicon (M1/M2/M3)
    elif torch.cuda.is_available():
        return "cuda"  # NVIDIA GPU (GCP)
    else:
        return "cpu"


class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    speaker_wav: Optional[str] = None


class TTSResponse(BaseModel):
    success: bool
    audio_path: Optional[str] = None
    duration_s: Optional[float] = None
    generation_time_ms: Optional[float] = None
    error: Optional[str] = None


# Future: Video generation endpoint
class VideoRequest(BaseModel):
    audio_path: str
    reference_image: str
    mode: Literal["sadtalker"] = "sadtalker"


class VideoResponse(BaseModel):
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup():
    """Initialize models with GPU acceleration"""
    global tts_model, avatar_model
    
    device = detect_device()
    logger.info(f"🚀 GPU Service starting on device: {device}")
    
    if device == "mps":
        logger.info("✅ Apple Silicon (M3) GPU detected - using MPS acceleration")
    elif device == "cuda":
        logger.info(f"✅ NVIDIA GPU detected - using CUDA (GPU: {torch.cuda.get_device_name(0)})")
    else:
        logger.warning("⚠️  No GPU detected - falling back to CPU (will be slow)")
    
    # Initialize TTS model
    logger.info("Loading XTTS-v2 model...")
    tts_model = XTTSModel()
    tts_model.device = device
    tts_model.initialize()
    logger.info("✅ TTS model ready")
    
    # Initialize SadTalker model
    logger.info("Loading SadTalker model...")
    avatar_model = SadTalkerModel()
    avatar_model.device = device
    avatar_model.initialize()
    logger.info("✅ Avatar model ready")


@app.get("/health")
async def health():
    """Health check with device info"""
    device = detect_device()
    return {
        "status": "healthy" if tts_model and tts_model.is_ready() and avatar_model and avatar_model.is_ready() else "initializing",
        "device": device,
        "capabilities": {
            "mps": torch.backends.mps.is_available(),
            "cuda": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        },
        "models": {
            "tts": tts_model.is_ready() if tts_model else False,
            "avatar": avatar_model.is_ready() if avatar_model else False,
            "lipsync": False
        }
    }


@app.post("/tts/generate", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """Generate audio from text using TTS"""
    if not tts_model or not tts_model.is_ready():
        raise HTTPException(status_code=503, detail="TTS model not ready")
    
    import time
    start_time = time.time()
    
    try:
        logger.info(f"TTS request: '{request.text[:50]}...' (language: {request.language})")
        
        # Generate output path in shared directory
        output_dir = Path("/tmp/gpu-service-output")
        output_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = int(time.time() * 1000)
        audio_path = output_dir / f"tts_{timestamp}.wav"
        
        # Generate audio using TTS model
        output_path, _, audio_duration = tts_model.synthesize(
            text=request.text,
            language=request.language,
            speaker_wav=request.speaker_wav,
            output_path=str(audio_path)
        )
        
        generation_time = (time.time() - start_time) * 1000  # ms
        
        logger.info(f"✅ TTS complete: {audio_duration:.2f}s audio in {generation_time:.0f}ms")
        
        return TTSResponse(
            success=True,
            audio_path=str(output_path),
            duration_s=audio_duration,
            generation_time_ms=generation_time
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        return TTSResponse(success=False, error=str(e))


@app.post("/avatar/generate", response_model=VideoResponse)
async def generate_avatar(request: VideoRequest):
    """Generate talking head video from audio + reference image"""
    if not avatar_model or not avatar_model.is_ready():
        raise HTTPException(status_code=503, detail="Avatar model not ready")
    
    try:
        logger.info(f"Avatar request: audio={request.audio_path}, image={request.reference_image}")
        
        # Generate output path
        output_dir = Path("/tmp/gpu-service-output")
        output_dir.mkdir(exist_ok=True, parents=True)
        
        import time
        timestamp = int(time.time() * 1000)
        output_path = output_dir / f"avatar_{timestamp}.mp4"
        
        # Generate video using SadTalker (to be implemented)
        video_path, generation_time = avatar_model.generate_video(
            audio_path=request.audio_path,
            reference_image_path=request.reference_image,
            output_path=str(output_path)
        )
        
        logger.info(f"✅ Avatar video generated in {generation_time:.0f}ms")
        
        return VideoResponse(
            success=True,
            video_path=video_path
        )
        
    except Exception as e:
        logger.error(f"Avatar generation failed: {e}", exc_info=True)
        return VideoResponse(success=False, error=str(e))


@app.get("/")
async def root():
    """Service info"""
    device = detect_device()
    return {
        "service": "GPU Acceleration Service",
        "version": "1.0",
        "device": device,
        "endpoints": {
            "health": "/health",
            "tts": "/tts/generate",
            "avatar": "/avatar/generate"
        }
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting GPU service on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )
