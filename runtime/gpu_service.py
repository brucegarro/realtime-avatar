#!/usr/bin/env python3
"""
GPU Acceleration Service
Runs ML inference tasks on GPU (MPS locally, CUDA remotely)

Supports:
- TTS (XTTS-v2)
- Video Generation (LivePortrait) - future
- Lip Sync - future
- Any GPU-accelerated ML task

Deployment modes:
- Local: Mac M3 with MPS acceleration
- Remote: GCP GPU instance with CUDA
"""
import os
import sys
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GPU Acceleration Service",
    description="ML inference service for TTS, video generation, and other GPU tasks",
    version="1.0"
)

# Global models
tts_model = None
# video_model = None  # Future: LivePortrait
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
    mode: Literal["static", "liveportrait"] = "static"


class VideoResponse(BaseModel):
    success: bool
    video_path: Optional[str] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup():
    """Initialize models with GPU acceleration"""
    global tts_model
    
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
    
    # Future: Initialize other models
    # logger.info("Loading LivePortrait model...")
    # video_model = LivePortraitModel()
    # video_model.device = device
    # video_model.initialize()
    # logger.info("✅ Video model ready")


@app.get("/health")
async def health():
    """Health check with device info"""
    device = detect_device()
    return {
        "status": "healthy" if tts_model and tts_model.is_ready() else "initializing",
        "device": device,
        "capabilities": {
            "mps": torch.backends.mps.is_available(),
            "cuda": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        },
        "models": {
            "tts": tts_model.is_ready() if tts_model else False,
            "video": False,  # Future: video_model.is_ready() if video_model else False
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
        
        # Generate audio
        audio_data, sample_rate = tts_model.synthesize(
            text=request.text,
            language=request.language,
            speaker_wav=request.speaker_wav
        )
        
        # Save to shared output directory
        output_dir = Path("/tmp/gpu-service-output")
        output_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = int(time.time() * 1000)
        audio_path = output_dir / f"tts_{timestamp}.wav"
        
        import soundfile as sf
        sf.write(str(audio_path), audio_data, sample_rate)
        
        duration = len(audio_data) / sample_rate
        generation_time = (time.time() - start_time) * 1000  # ms
        
        logger.info(f"✅ TTS complete: {duration:.2f}s audio in {generation_time:.0f}ms")
        
        return TTSResponse(
            success=True,
            audio_path=str(audio_path),
            duration_s=duration,
            generation_time_ms=generation_time
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        return TTSResponse(success=False, error=str(e))


# Future: Video generation endpoint
@app.post("/video/generate", response_model=VideoResponse)
async def generate_video(request: VideoRequest):
    """Generate talking head video (future implementation)"""
    # Stub for now
    return VideoResponse(
        success=False,
        error="Video generation not yet implemented - coming in Phase 2"
    )


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
            "video": "/video/generate (stub)"
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
