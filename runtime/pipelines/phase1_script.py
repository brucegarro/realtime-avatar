"""
Phase 1 Pipeline: Script → Video
Orchestrates TTS and Avatar Animation
"""
import logging
import os
import time
from typing import Optional

from models.tts import get_xtts_model
from models.tts_client import get_xtts_client
from models.avatar import get_avatar_model
from config import settings

logger = logging.getLogger(__name__)


class Phase1Pipeline:
    """
    Phase 1 pipeline: Text script → TTS → Avatar animation → Video
    """
    
    def __init__(self):
        # Use external GPU service if enabled, otherwise local TTS
        if settings.use_external_gpu_service:
            logger.info("Using external GPU service for TTS")
            self.tts_model = get_xtts_client()
        else:
            logger.info("Using local TTS model")
            self.tts_model = get_xtts_model()
        
        self.avatar_model = get_avatar_model()
        self._ready = False
    
    def initialize(self):
        """Initialize all models in the pipeline"""
        if self._ready:
            return
        
        logger.info("Initializing Phase 1 pipeline...")
        start_time = time.time()
        
        # Initialize TTS model
        self.tts_model.initialize()
        
        # Initialize avatar model
        self.avatar_model.initialize()
        
        self._ready = True
        elapsed = time.time() - start_time
        logger.info(f"Phase 1 pipeline ready in {elapsed:.2f}s")
    
    def is_ready(self) -> bool:
        """Check if pipeline is ready"""
        return self._ready and self.tts_model.is_ready() and self.avatar_model.is_ready()
    
    async def generate(
        self,
        text: str,
        language: str = "en",
        reference_image: Optional[str] = None,
        voice_sample: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> dict:
        """
        Generate talking-head video from text.
        
        Args:
            text: Text script to speak
            language: Language code (en, zh-cn, es)
            reference_image: Reference image filename (in assets/images/)
            voice_sample: Voice reference filename (in assets/voice/reference_samples/)
            job_id: Unique job identifier
            
        Returns:
            Dictionary with generation results and metrics
        """
        if not self.is_ready():
            self.initialize()
        
        job_id = job_id or f"job_{int(time.time() * 1000)}"
        logger.info(f"[{job_id}] Starting Phase 1 generation")
        
        try:
            # Step 1: Text → Speech (TTS)
            logger.info(f"[{job_id}] Step 1: TTS synthesis")
            
            # Resolve voice sample path
            voice_sample_path = None
            if voice_sample:
                voice_sample_path = os.path.join(settings.voice_samples_dir, voice_sample)
                if not os.path.exists(voice_sample_path):
                    logger.warning(f"Voice sample not found: {voice_sample_path}")
                    voice_sample_path = None
            
            audio_path, tts_duration_ms, audio_duration_s = self.tts_model.synthesize(
                text=text,
                language=language,
                speaker_wav=voice_sample_path,
                output_path=os.path.join("/tmp/gpu-service-output", f"{job_id}_audio.wav")
            )
            
            logger.info(f"[{job_id}] TTS completed: {tts_duration_ms:.0f}ms, audio: {audio_duration_s:.2f}s")
            
            # Step 2: Audio + Image → Animated Video
            logger.info(f"[{job_id}] Step 2: Avatar animation")
            
            # Resolve reference image path
            if not reference_image:
                reference_image = settings.default_reference_image
            
            image_path = os.path.join(settings.images_dir, reference_image)
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Reference image not found: {image_path}")
            
            video_path, avatar_duration_ms = self.avatar_model.animate(
                audio_path=audio_path,
                reference_image_path=image_path,
                output_path=os.path.join("/tmp/gpu-service-output", f"{job_id}_video.mp4")
            )
            
            logger.info(f"[{job_id}] Avatar animation completed: {avatar_duration_ms:.0f}ms")
            
            # Return results
            total_duration_ms = tts_duration_ms + avatar_duration_ms
            
            return {
                "job_id": job_id,
                "video_path": video_path,
                "audio_path": audio_path,
                "tts_duration_ms": tts_duration_ms,
                "avatar_duration_ms": avatar_duration_ms,
                "total_duration_ms": total_duration_ms,
                "audio_duration_s": audio_duration_s,
                "language": language,
                "reference_image": reference_image
            }
            
        except Exception as e:
            logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
            raise
    
    def cleanup(self):
        """Cleanup pipeline resources"""
        self.tts_model.cleanup()
        self.avatar_model.cleanup()
        self._ready = False
        logger.info("Phase 1 pipeline cleaned up")
