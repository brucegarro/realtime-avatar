#!/usr/bin/env python3
"""
GPU Acceleration Service
Runs ML inference tasks on GPU (MPS locally, CUDA remotely)

Supports:
- TTS (Fish Speech or XTTS-v2, configurable via TTS_BACKEND env var)
- Video Generation (SadTalker, LivePortrait, Ditto)
- Lip Sync - future
- Any GPU-accelerated ML task

Deployment modes:
- Local: Mac M3 with MPS acceleration
- Remote: GCP GPU instance with CUDA

TTS Backend Selection:
- TTS_BACKEND=fish_speech (default): Fast inference, good multilingual
- TTS_BACKEND=xtts: Original backend, proven stable
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

# TTS Backend selection - Fish Speech (fast) or XTTS (stable)
TTS_BACKEND = os.getenv("TTS_BACKEND", "xtts")  # fish_speech or xtts

if TTS_BACKEND == "fish_speech":
    try:
        from models.tts_fish import FishSpeechModel as TTSModel
        logger_msg = "Using Fish Speech TTS backend (fast, multilingual via API)"
    except ImportError:
        from models.tts import XTTSModel as TTSModel
        TTS_BACKEND = "xtts"  # Fallback
        logger_msg = "Fish Speech not available, falling back to XTTS"
else:
    from models.tts import XTTSModel as TTSModel
    logger_msg = "Using XTTS TTS backend (stable, proven)"

# Conditionally import avatar models based on backend config
AVATAR_BACKEND = os.getenv("AVATAR_BACKEND", "auto")  # auto, sadtalker, liveportrait, ditto

# Only import models we'll actually use
if AVATAR_BACKEND in ("auto", "sadtalker"):
    from models.sadtalker_model import SadTalkerModel
else:
    SadTalkerModel = None

if AVATAR_BACKEND in ("auto", "liveportrait"):
    from models.liveportrait_model import LivePortraitModel
else:
    LivePortraitModel = None

if AVATAR_BACKEND == "ditto":
    from models.ditto_model import DittoModel
else:
    DittoModel = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log TTS backend selection
logger.info(logger_msg)

app = FastAPI(
    title="GPU Acceleration Service",
    description="ML inference service for TTS, video generation, and other GPU tasks",
    version="1.0"
)

# Global models
tts_model = None
tts_backend_name = TTS_BACKEND  # Track which TTS backend is loaded
avatar_model = None  # SadTalker or LivePortrait
avatar_backend_name = None  # Track which backend is loaded
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
    mode: Literal["sadtalker", "liveportrait", "auto"] = "auto"
    enhancer: Optional[str] = None  # 'gfpgan' or None


class VideoResponse(BaseModel):
    success: bool
    video_path: Optional[str] = None
    backend: Optional[str] = None  # Which backend was used
    error: Optional[str] = None


def select_avatar_backend(device: str, preference: str = "auto") -> str:
    """
    Select optimal avatar backend based on device and preference
    
    Strategy:
    - CUDA + ditto: Use Ditto (audio-driven, real-time capable)
    - CUDA + auto: Prefer LivePortrait (faster, better quality)  
    - MPS: Use SadTalker (more compatible)
    - CPU: Use SadTalker (fallback)
    """
    if preference == "ditto":
        return "ditto"
    elif preference != "auto":
        return preference
    
    if device == "cuda":
        logger.info("CUDA detected: selecting LivePortrait for optimal performance")
        return "liveportrait"
    else:
        logger.info(f"Device {device}: selecting SadTalker for compatibility")
        return "sadtalker"


@app.on_event("startup")
async def startup():
    """Initialize models with GPU acceleration"""
    global tts_model, avatar_model, avatar_backend_name
    
    device = detect_device()
    logger.info(f"🚀 GPU Service starting on device: {device}")
    
    if device == "mps":
        logger.info("✅ Apple Silicon (M3) GPU detected - using MPS acceleration")
    elif device == "cuda":
        logger.info(f"✅ NVIDIA GPU detected - using CUDA (GPU: {torch.cuda.get_device_name(0)})")
    else:
        logger.warning("⚠️  No GPU detected - falling back to CPU (will be slow)")
    
    # Initialize TTS model (Fish Speech or XTTS based on TTS_BACKEND)
    logger.info(f"Loading TTS model ({tts_backend_name})...")
    tts_model = TTSModel()
    tts_model.device = device
    tts_model.initialize()
    logger.info(f"✅ TTS model ready ({tts_backend_name})")
    
    # Select and initialize avatar backend
    avatar_backend_name = select_avatar_backend(device, AVATAR_BACKEND)
    logger.info(f"Loading avatar backend: {avatar_backend_name}")
    
    if avatar_backend_name == "ditto":
        if DittoModel is None:
            raise RuntimeError("Ditto backend requested but not available")
        avatar_model = DittoModel()
        avatar_model.device = device
        # Initialize Ditto (will auto-detect TensorRT or PyTorch checkpoints)
        avatar_model.initialize()
        logger.info("✅ Ditto model initialized")
    elif avatar_backend_name == "liveportrait":
        if LivePortraitModel is None:
            raise RuntimeError("LivePortrait backend requested but not available")
        try:
            avatar_model = LivePortraitModel()
            avatar_model.device = device
            avatar_model.initialize()
            logger.info("✅ LivePortrait model ready")
        except Exception as e:
            logger.error(f"Failed to load LivePortrait: {e}")
            if SadTalkerModel is not None:
                logger.info("Falling back to SadTalker...")
                avatar_backend_name = "sadtalker"
                avatar_model = SadTalkerModel()
                avatar_model.device = device
                avatar_model.initialize()
                logger.info("✅ SadTalker model ready (fallback)")
            else:
                raise RuntimeError("LivePortrait failed and SadTalker not available")
    else:
        if SadTalkerModel is None:
            raise RuntimeError("SadTalker backend requested but not available")
        avatar_model = SadTalkerModel()
        avatar_model.device = device
        avatar_model.initialize()
        logger.info("✅ SadTalker model ready")


@app.get("/health")
async def health():
    """Health check with device info"""
    device = detect_device()
    return {
        "status": "healthy" if tts_model and tts_model.is_ready() and avatar_model and avatar_model.is_ready() else "initializing",
        "device": device,
        "tts_backend": tts_backend_name,
        "avatar_backend": avatar_backend_name,
        "capabilities": {
            "mps": torch.backends.mps.is_available(),
            "cuda": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        },
        "models": {
            "tts": tts_model.is_ready() if tts_model else False,
            "tts_backend": tts_backend_name,
            "avatar": avatar_model.is_ready() if avatar_model else False,
            "avatar_backend": avatar_backend_name,
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
        logger.info(f"Avatar request: audio={request.audio_path}, image={request.reference_image}, backend={avatar_backend_name}")
        
        # Generate output path
        output_dir = Path("/tmp/gpu-service-output")
        output_dir.mkdir(exist_ok=True, parents=True)
        
        import time
        timestamp = int(time.time() * 1000)
        output_path = output_dir / f"avatar_{avatar_backend_name}_{timestamp}.mp4"
        
        # Generate video using selected backend (SadTalker or LivePortrait)
        video_path, generation_time = avatar_model.generate_video(
            audio_path=request.audio_path,
            reference_image_path=request.reference_image,
            output_path=str(output_path),
            enhancer=request.enhancer
        )
        
        logger.info(f"✅ Avatar video generated in {generation_time:.0f}ms using {avatar_backend_name}")
        
        return VideoResponse(
            success=True,
            video_path=video_path,
            backend=avatar_backend_name
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
