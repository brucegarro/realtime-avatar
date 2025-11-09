"""
Runtime service - Main FastAPI application
Handles Phase 1: Script → Video generation
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging
import os
import uuid
from datetime import datetime

from config import settings, get_settings
from pipelines.phase1_script import Phase1Pipeline

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Realtime Avatar Runtime Service",
    description="Real-time avatar generation API",
    version="0.1.0"
)

# Initialize pipeline (will lazy-load models)
phase1_pipeline: Optional[Phase1Pipeline] = None


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    global phase1_pipeline
    logger.info(f"Starting Realtime Avatar Runtime in {settings.mode} mode on {settings.device}")
    logger.info(f"Video resolution: {settings.video_resolution}, FPS: {settings.video_fps}")
    
    # Create output directory
    os.makedirs(settings.output_dir, exist_ok=True)
    
    # Initialize Phase 1 pipeline
    try:
        phase1_pipeline = Phase1Pipeline()
        phase1_pipeline.initialize()  # Actually load the models!
        logger.info("Phase 1 pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize pipeline: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Shutting down Realtime Avatar Runtime")


# Request/Response models
class ScriptRequest(BaseModel):
    """Request model for script-to-video generation"""
    text: str
    language: str = "en"  # en, zh-cn, es
    reference_image: Optional[str] = None  # Filename in assets/images/
    voice_sample: Optional[str] = None  # Filename in assets/voice/reference_samples/
    enhancer: Optional[str] = None  # Face enhancer: 'gfpgan' or None
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello! I'm Bruce's digital avatar. I can speak English, Chinese, and Spanish.",
                "language": "en",
                "reference_image": "bruce_neutral.jpg",
                "enhancer": "gfpgan"
            }
        }


class GenerationResponse(BaseModel):
    """Response model for generation requests"""
    job_id: str
    status: str
    message: str
    video_url: Optional[str] = None
    metadata: Optional[dict] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    mode: str
    device: str
    models_loaded: bool


# API endpoints
@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "service": "Realtime Avatar Runtime",
        "version": "0.1.0",
        "mode": settings.mode,
        "device": settings.device
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    models_loaded = phase1_pipeline is not None and phase1_pipeline.is_ready()
    
    return HealthResponse(
        status="healthy" if models_loaded else "initializing",
        mode=settings.mode,
        device=settings.device,
        models_loaded=models_loaded
    )


@app.post("/api/v1/generate", response_model=GenerationResponse)
async def generate_video(request: ScriptRequest, background_tasks: BackgroundTasks):
    """
    Generate talking-head video from text script.
    Phase 1: Text → TTS → Avatar Animation → MP4
    """
    if not phase1_pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    
    # Validate language
    if request.language not in ["en", "zh-cn", "es"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported language: {request.language}. Use 'en', 'zh-cn', or 'es'"
        )
    
    # Generate unique job ID
    job_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    logger.info(f"[{job_id}] New generation request: language={request.language}, text_len={len(request.text)}")
    
    try:
        # Run generation pipeline
        start_time = datetime.now()
        
        result = await phase1_pipeline.generate(
            text=request.text,
            language=request.language,
            reference_image=request.reference_image,
            voice_sample=request.voice_sample,
            job_id=job_id,
            enhancer=request.enhancer
        )
        
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        logger.info(f"[{job_id}] Generation completed in {duration_ms:.0f}ms")
        
        # Return response with video path
        return GenerationResponse(
            job_id=job_id,
            status="completed",
            message="Video generated successfully",
            video_url=f"/api/v1/videos/{os.path.basename(result['video_path'])}",
            metadata={
                "duration_ms": duration_ms,
                "tts_ms": result.get("tts_duration_ms", 0),
                "avatar_ms": result.get("avatar_duration_ms", 0),
                "language": request.language,
                "audio_duration_s": result.get("audio_duration_s", 0)
            }
        )
        
    except Exception as e:
        logger.error(f"[{job_id}] Generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.get("/api/v1/videos/{filename}")
async def get_video(filename: str):
    """Serve generated video file"""
    # Check GPU service output directory first (for hybrid mode)
    gpu_output_path = os.path.join("/tmp/gpu-service-output", filename)
    if os.path.exists(gpu_output_path):
        return FileResponse(
            gpu_output_path,
            media_type="video/mp4",
            filename=filename
        )
    
    # Fallback to regular output directory
    video_path = os.path.join(settings.output_dir, filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename
    )


@app.get("/api/v1/assets/images", response_model=dict)
async def list_images():
    """List available reference images"""
    try:
        images = [f for f in os.listdir(settings.images_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        return {"images": images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/assets/voice-samples", response_model=dict)
async def list_voice_samples():
    """List available voice reference samples"""
    try:
        if os.path.exists(settings.voice_samples_dir):
            samples = [f for f in os.listdir(settings.voice_samples_dir) if f.endswith(('.wav', '.mp3'))]
        else:
            samples = []
        return {"samples": samples}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.mode == "local")
    )
