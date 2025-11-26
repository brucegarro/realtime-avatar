"""
Runtime service - Main FastAPI application
Handles Phase 1: Script → Video generation
Handles Phase 4: Interactive conversation with voice input
Handles Phase 5: Streaming conversation with progressive video chunks
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
import os
import uuid
import time
from datetime import datetime
import shutil
import ffmpeg
import json
import asyncio

from config import settings, get_settings
from pipelines.phase1_script import Phase1Pipeline
from pipelines.conversation_pipeline import ConversationPipeline
from pipelines.streaming_conversation import StreamingConversationPipeline# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Realtime Avatar Runtime Service",
    description="Real-time avatar generation API with conversation support",
    version="0.2.0"
)

# Add CORS middleware for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pipelines (will lazy-load models)
phase1_pipeline: Optional[Phase1Pipeline] = None
conversation_pipeline: Optional[ConversationPipeline] = None
streaming_pipeline: Optional[StreamingConversationPipeline] = None

# Global SSE sequence counter for debugging event ordering
sse_sequence_counter = 0
sse_sequence_lock = asyncio.Lock()


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    global phase1_pipeline, conversation_pipeline, streaming_pipeline
    logger.info(f"Starting Realtime Avatar Runtime in {settings.mode} mode on {settings.device}")
    logger.info(f"Video resolution: {settings.video_resolution}, FPS: {settings.video_fps}")
    
    # Create output directories
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs("outputs/conversations", exist_ok=True)
    os.makedirs("/tmp/audio_uploads", exist_ok=True)
    
    # Initialize Phase 1 pipeline (lazy load - will initialize on first request)
    try:
        phase1_pipeline = Phase1Pipeline()
        # Don't force initialization at startup - models will load on first request
        logger.info("Phase 1 pipeline created (models will load on first request)")
    except Exception as e:
        logger.error(f"Failed to create Phase 1 pipeline: {e}")
        raise
    
    # Initialize Phase 4 conversation pipeline
    try:
        conversation_pipeline = ConversationPipeline(
            reference_image="bruce_haircut_small.jpg",  # Just filename, Phase1Pipeline will resolve the path
            reference_audio="bruce_en_sample.wav",  # Just filename, Phase1Pipeline will resolve the path
            output_dir="outputs/conversations",
            device=settings.device,
            use_tensorrt=True,
        )
        conversation_pipeline.initialize()
        logger.info("Phase 4 conversation pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize conversation pipeline: {e}")
        logger.warning("Conversation features will be unavailable")
    
    # Initialize Phase 5 streaming pipeline
    try:
        streaming_pipeline = StreamingConversationPipeline(
            reference_image="bruce_haircut_small.jpg",
            reference_audio="bruce_en_sample.wav",
            output_dir="outputs/conversations",
            device=settings.device,
            use_tensorrt=True,
            max_parallel_chunks=2,  # Process 2 chunks in parallel
        )
        streaming_pipeline.initialize()
        logger.info("Phase 5 streaming conversation pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize streaming pipeline: {e}")
        logger.warning("Streaming conversation features will be unavailable")


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


# Phase 4: Conversation models
class TranscribeResponse(BaseModel):
    """Response model for audio transcription"""
    text: str
    language: str
    duration: float
    transcribe_time: float


class ChatRequest(BaseModel):
    """Request model for LLM chat"""
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    max_tokens: int = 150


class ChatResponse(BaseModel):
    """Response model for LLM chat"""
    response: str
    llm_time: float


class ConversationResponse(BaseModel):
    """Response model for full conversation pipeline"""
    job_id: str
    user_text: str
    response_text: str
    video_url: str
    total_time: float
    metadata: dict


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
@app.head("/api/v1/videos/{filename}")
async def get_video(filename: str):
    """Serve generated video file with CORS headers and detailed timing logs"""
    request_start = time.time()
    logger.info(f"[VIDEO] === REQUEST START === {filename} at t={request_start:.3f}")
    
    # Check GPU service output directory first (for hybrid mode)
    gpu_output_path = os.path.join("/tmp/gpu-service-output", filename)
    if os.path.exists(gpu_output_path):
        video_path = gpu_output_path
        logger.info(f"[VIDEO] Found in GPU output: {gpu_output_path}")
    else:
        # Fallback to regular output directory
        video_path = os.path.join(settings.output_dir, filename)
        if not os.path.exists(video_path):
            logger.error(f"[VIDEO] File not found: {filename} (checked GPU output and {settings.output_dir})")
            raise HTTPException(status_code=404, detail="Video not found")
        logger.info(f"[VIDEO] Found in output dir: {video_path}")
    
    # Get file metadata
    file_stat = os.stat(video_path)
    file_size = file_stat.st_size
    file_mtime = file_stat.st_mtime
    file_age = request_start - file_mtime
    
    logger.info(f"[VIDEO] File metadata: size={file_size} bytes, age={file_age:.3f}s, mtime={file_mtime:.3f}")
    logger.info(f"[VIDEO] Time to file check: {(time.time() - request_start)*1000:.1f}ms")
    
    # Async generator to stream file in chunks (doesn't block event loop!)
    async def file_stream():
        chunk_size = 65536  # 64KB chunks
        bytes_sent = 0
        first_chunk_time = None
        chunk_count = 0
        
        # Use asyncio.to_thread to avoid blocking on file I/O
        def read_chunk(f, size):
            return f.read(size)
        
        stream_start = time.time()
        logger.info(f"[VIDEO] Starting file stream at t={stream_start:.3f}")
        
        with open(video_path, "rb") as f:
            while True:
                chunk_read_start = time.time()
                chunk = await asyncio.to_thread(read_chunk, f, chunk_size)
                if not chunk:
                    break
                
                chunk_count += 1
                bytes_sent += len(chunk)
                
                # Log first chunk (TTFB)
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    ttfb = (first_chunk_time - request_start) * 1000
                    logger.info(f"[VIDEO] TTFB (first chunk): {ttfb:.1f}ms, chunk_size={len(chunk)}")
                
                yield chunk
        
        elapsed = time.time() - request_start
        throughput_mbps = (bytes_sent * 8 / 1024 / 1024) / elapsed if elapsed > 0 else 0
        logger.info(f"[VIDEO] === COMPLETE === {filename}: {bytes_sent}/{file_size} bytes in {elapsed:.3f}s ({throughput_mbps:.1f} Mbps, {chunk_count} chunks)")
    
    return StreamingResponse(
        file_stream(),
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
            "Content-Length": str(file_size),
        }
    )
    
    return StreamingResponse(
        file_stream(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(file_size),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache"
        }
    )


@app.get("/api/v1/assets/images", response_model=dict)
async def list_images():
    """List available reference images"""
    try:
        images = [f for f in os.listdir(settings.images_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        return {"images": images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/avatars", response_model=dict)
async def list_avatars():
    try:
        config_path = os.path.join(settings.assets_dir, "avatars.json")
        if not os.path.exists(config_path):
            return {"avatars": []}
        with open(config_path, "r") as f:
            data = json.load(f)
        return {"avatars": data.get("avatars", [])}
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


# Phase 4: Conversation endpoints
@app.post("/api/v1/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(audio: UploadFile = File(...), language: str = "en"):
    """
    Transcribe audio to text using ASR (Faster-Whisper).
    Phase 4: Voice input support
    """
    if not conversation_pipeline:
        raise HTTPException(status_code=503, detail="Conversation pipeline not initialized")
    
    # Save uploaded audio to temp file (preserve original extension to avoid ffmpeg decode issues)
    orig_ext = os.path.splitext(audio.filename or '')[1].lower() or '.webm'
    safe_ext = orig_ext if orig_ext in ['.wav', '.webm', '.mp3', '.m4a'] else '.webm'
    temp_path = f"/tmp/audio_uploads/{uuid.uuid4().hex}{safe_ext}"
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

        wav_path = f"/tmp/audio_uploads/{uuid.uuid4().hex}.wav"
        (
            ffmpeg
            .input(temp_path)
            .output(wav_path, ar=16000, ac=1, format='wav')
            .overwrite_output()
            .run(quiet=True)
        )

        result = conversation_pipeline.transcribe(wav_path, language=language)
        
        return TranscribeResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"],
            transcribe_time=result["transcribe_time"],
        )
        
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Generate conversational response using LLM (Qwen-2.5).
    Phase 4: Text chat without avatar generation
    """
    if not conversation_pipeline:
        raise HTTPException(status_code=503, detail="Conversation pipeline not initialized")
    
    try:
        result = conversation_pipeline.generate_response(
            user_message=request.message,
            conversation_history=request.conversation_history,
            max_tokens=request.max_tokens,
        )
        
        return ChatResponse(
            response=result["response"],
            llm_time=result["llm_time"],
        )
        
    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.post("/api/v1/conversation", response_model=ConversationResponse)
async def process_conversation(
    audio: UploadFile = File(...),
    language: str = "en",
    conversation_history: Optional[str] = None,
    reference_image: Optional[str] = Form(None),
    voice_sample: Optional[str] = Form(None),
    avatar_id: Optional[str] = Form(None),
):
    """
    Full conversation pipeline: Audio → ASR → LLM → TTS → Video.
    Phase 4: Interactive voice conversation with avatar response
    """
    if not conversation_pipeline:
        raise HTTPException(status_code=503, detail="Conversation pipeline not initialized")
    
    # Save uploaded audio (preserve original extension)
    job_id = f"conversation_{uuid.uuid4().hex[:8]}"
    os.makedirs("/tmp/audio_uploads", exist_ok=True)
    orig_ext = os.path.splitext(audio.filename or '')[1].lower() or '.webm'
    safe_ext = orig_ext if orig_ext in ['.wav', '.webm', '.mp3', '.m4a'] else '.webm'
    temp_path = f"/tmp/audio_uploads/{job_id}{safe_ext}"
    
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

        wav_path = f"/tmp/audio_uploads/{uuid.uuid4().hex}.wav"
        (
            ffmpeg
            .input(temp_path)
            .output(wav_path, ar=16000, ac=1, format='wav')
            .overwrite_output()
            .run(quiet=True)
        )
        
        # Parse conversation history if provided
        history = None
        if conversation_history:
            import json
            try:
                history = json.loads(conversation_history)
            except json.JSONDecodeError:
                logger.warning("Invalid conversation history JSON, ignoring")
        
        # Process full conversation
        # Resolve avatar overrides
        system_prompt_override = None
        if avatar_id:
            try:
                config_path = os.path.join(settings.assets_dir, "avatars.json")
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        avatars = json.load(f).get("avatars", [])
                    for a in avatars:
                        if a.get("id") == avatar_id:
                            reference_image = reference_image or a.get("reference_image")
                            voice_sample = voice_sample or a.get("voice_sample")
                            system_prompt_override = a.get("system_prompt")
                            break
            except Exception:
                pass

        result = await conversation_pipeline.process_conversation(
            audio_path=wav_path,
            conversation_history=history,
            output_name=job_id,
            language=language,
            reference_image=reference_image,
            voice_sample=voice_sample,
            system_prompt=system_prompt_override,
        )
        
        # Get video URL
        video_filename = os.path.basename(result["avatar_video"]["video_path"])
        video_url = f"/api/v1/videos/{video_filename}"
        
        return ConversationResponse(
            job_id=job_id,
            user_text=result["user_text"],
            response_text=result["response_text"],
            video_url=video_url,
            total_time=result["total_time"],
            metadata={
                "transcribe_time": result["transcription"]["transcribe_time"],
                "llm_time": result["llm_response"]["llm_time"],
                "generation_time": result["avatar_video"]["total_generation_time"],
                "language": language,
                "reference_image": result["avatar_video"].get("reference_image"),
                "voice_sample": voice_sample,
            },
        )
        
    except Exception as e:
        logger.error(f"[{job_id}] Conversation processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversation failed: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass


@app.post("/api/v1/conversation/stream")
async def process_conversation_stream(
    audio: UploadFile = File(...),
    language: str = "en",
    conversation_history: Optional[str] = None,
    reference_image: Optional[str] = Form(None),
    voice_sample: Optional[str] = Form(None),
    avatar_id: Optional[str] = Form(None),
):
    """
    Streaming conversation pipeline: Audio → ASR → LLM → TTS + Video chunks.
    Phase 5: Progressive video generation with reduced time-to-first-frame.
    
    Returns Server-Sent Events (SSE) stream with chunks as they're generated.
    """
    if not streaming_pipeline:
        raise HTTPException(status_code=503, detail="Streaming pipeline not initialized")
    
    # Save uploaded audio BEFORE creating generator
    job_id = f"stream_{uuid.uuid4().hex[:8]}"
    orig_ext = os.path.splitext(audio.filename or '')[1].lower() or '.webm'
    safe_ext = orig_ext if orig_ext in ['.wav', '.webm', '.mp3', '.m4a'] else '.webm'
    temp_path = f"/tmp/audio_uploads/{job_id}{safe_ext}"
    os.makedirs("/tmp/audio_uploads", exist_ok=True)
    
    # Save audio synchronously before yielding
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)
    
    # Parse conversation history if provided
    history = None
    if conversation_history:
        try:
            history = json.loads(conversation_history)
        except json.JSONDecodeError:
            logger.warning("Invalid conversation history JSON, ignoring")
    
    async def event_generator():
        """Generate SSE events for each chunk"""
        global sse_sequence_counter
        try:
            # Process conversation with streaming
            # Resolve avatar overrides
            system_prompt_override = None
            if avatar_id:
                try:
                    config_path = os.path.join(settings.assets_dir, "avatars.json")
                    if os.path.exists(config_path):
                        with open(config_path, "r") as f:
                            avatars = json.load(f).get("avatars", [])
                        for a in avatars:
                            if a.get("id") == avatar_id:
                                reference_image = reference_image or a.get("reference_image")
                                voice_sample = voice_sample or a.get("voice_sample")
                                system_prompt_override = a.get("system_prompt")
                                break
                except Exception:
                    pass

            async for event in streaming_pipeline.process_conversation_streaming(
                audio_path=temp_path,
                conversation_history=history,
                job_id=job_id,
                language=language,
                reference_image=reference_image,
                voice_sample=voice_sample,
                system_prompt=system_prompt_override,
            ):
                # Format as SSE event
                event_type = event["type"]
                event_data = event["data"]
                
                # Add sequence number for debugging event ordering
                async with sse_sequence_lock:
                    sse_sequence_counter += 1
                    event_seq = sse_sequence_counter
                event_data["seq"] = event_seq
                event_data["server_timestamp"] = time.time()
                
                # Add video URL for video chunks
                if event_type == "video_chunk":
                    chunk_index = event_data.get("chunk_index", "?")
                    chunk_time = event_data.get("chunk_time", 0)
                    video_path = event_data.get("video_path")
                    logger.info(f"[SSE] seq={event_seq} Chunk {chunk_index} ready to send (generated in {chunk_time:.2f}s)")
                    
                    if video_path:
                        # Quick file existence check (max 1s wait)
                        # GPU service may need a moment to flush file to disk
                        wait_start = time.time()
                        max_wait = 1.0
                        while not os.path.exists(video_path) and (time.time() - wait_start) < max_wait:
                            await asyncio.sleep(0.05)
                        
                        if not os.path.exists(video_path):
                            logger.error(f"[PERF] Chunk {chunk_index} file not found after {max_wait}s: {video_path}")
                            continue
                        
                        wait_time = time.time() - wait_start
                        if wait_time > 0.1:
                            logger.warning(f"[PERF] Chunk {chunk_index} file check took {wait_time:.2f}s")
                        
                        video_filename = os.path.basename(video_path)
                        event_data["video_url"] = f"/api/v1/videos/{video_filename}"
                        file_size = os.path.getsize(video_path)
                        file_age = time.time() - os.path.getmtime(video_path)
                        logger.info(f"[SSE] seq={event_seq} Chunk {chunk_index} sending: {video_filename} (size={file_size}, age={file_age:.3f}s)")
                
                # Send SSE event with explicit flush
                send_time = time.time()
                logger.info(f"[SSE] seq={event_seq} Yielding {event_type} event (chunk {event_data.get('chunk_index', '?')}) at t={send_time:.3f}")
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event_data)}\n\n"
                
                # Force immediate transmission by yielding control
                # This ensures SSE events are sent immediately, not buffered
                await asyncio.sleep(0)
                
                if event_type == "video_chunk":
                    chunk_index = event_data.get("chunk_index", "?")
                    flush_time = time.time() - send_time
                    logger.info(f"[SSE] seq={event_seq} Chunk {chunk_index} flushed in {flush_time*1000:.1f}ms, continuing")
                
        except Exception as e:
            logger.error(f"[{job_id}] Streaming conversation failed: {e}", exc_info=True)
            error_event = {
                "error": str(e),
                "job_id": job_id,
            }
            yield f"event: error\n"
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.mode == "local")
    )
