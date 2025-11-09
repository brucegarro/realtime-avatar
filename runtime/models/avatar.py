"""
LivePortrait avatar animation wrapper
Generates talking-head video from audio + reference image using GPU service
"""
import logging
import os
import time
from typing import Optional

from config import settings
from models.avatar_client import get_avatar_client

logger = logging.getLogger(__name__)


class LivePortraitModel:
    """
    LivePortrait model wrapper for avatar animation.
    Uses GPU service for actual generation (runs on M3 with MPS acceleration).
    """
    
    def __init__(self):
        self.device = settings.device
        self._initialized = False
        self.client = None
        
    def initialize(self):
        """Initialize connection to GPU service"""
        if self._initialized:
            return
            
        logger.info(f"Initializing avatar client (GPU service)...")
        start_time = time.time()
        
        try:
            # Get GPU service client
            self.client = get_avatar_client()
            self.client.initialize()
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Avatar client initialized in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to initialize avatar client: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized and self.client and self.client.is_ready()
    
    def animate(
        self,
        audio_path: str,
        reference_image_path: str,
        output_path: Optional[str] = None,
        enhancer: Optional[str] = None
    ) -> tuple[str, float]:
        """
        Generate animated talking-head video from audio and reference image.
        
        Args:
            audio_path: Path to audio file (from TTS)
            reference_image_path: Path to reference image
            output_path: Output video file path
            enhancer: Face enhancer to use ('gfpgan' or None)
            
        Returns:
            Tuple of (output_path, duration_ms)
        """
        if not self.is_ready():
            self.initialize()
        
        start_time = time.time()
        
        try:
            # Generate output path if not provided
            if not output_path:
                os.makedirs(settings.output_dir, exist_ok=True)
                output_path = os.path.join(
                    settings.output_dir,
                    f"avatar_video_{int(time.time() * 1000)}.mp4"
                )
            
            logger.info(f"Animating avatar: audio={audio_path}, image={reference_image_path}")
            
            # Call GPU service to generate video
            video_path, _ = self.client.generate_video(
                audio_path=audio_path,
                reference_image_path=reference_image_path,
                output_path=output_path,
                enhancer=enhancer
            )
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Avatar animation completed in {duration_ms:.0f}ms")
            
            return video_path, duration_ms
            
        except Exception as e:
            logger.error(f"Avatar animation failed: {e}", exc_info=True)
            raise
    
    def cleanup(self):
        """Cleanup client resources"""
        if self.client:
            self.client.cleanup()
            self._initialized = False
            logger.info("Avatar client cleaned up")


# Global instance
_avatar_model: Optional[LivePortraitModel] = None


def get_avatar_model() -> LivePortraitModel:
    """Get or create global avatar model instance"""
    global _avatar_model
    if _avatar_model is None:
        _avatar_model = LivePortraitModel()
    return _avatar_model
