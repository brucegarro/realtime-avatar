"""
LivePortrait avatar animation wrapper
Generates talking-head video from audio + reference image
"""
import logging
import os
import time
from typing import Optional
import numpy as np
import cv2

from config import settings

logger = logging.getLogger(__name__)


class LivePortraitModel:
    """
    LivePortrait model wrapper for avatar animation.
    
    Note: This is a placeholder implementation. LivePortrait requires:
    - Installing from GitHub: https://github.com/KwaiVGI/LivePortrait
    - Pre-trained models
    - GPU for real-time performance (CPU mode is slow)
    
    For Phase 1 MVP, we'll implement a simpler approach using face animation techniques.
    """
    
    def __init__(self):
        self.device = settings.device
        self._initialized = False
        self.model = None
        
    def initialize(self):
        """Load LivePortrait model"""
        if self._initialized:
            return
            
        logger.info(f"Loading LivePortrait model on {self.device}...")
        start_time = time.time()
        
        try:
            # TODO: Implement actual LivePortrait initialization
            # For now, we'll use a placeholder that creates simple animated videos
            logger.warning("LivePortrait not fully implemented - using placeholder animation")
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Avatar model loaded in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to load avatar model: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized
    
    def animate(
        self,
        audio_path: str,
        reference_image_path: str,
        output_path: Optional[str] = None
    ) -> tuple[str, float]:
        """
        Generate animated talking-head video from audio and reference image.
        
        Args:
            audio_path: Path to audio file (from TTS)
            reference_image_path: Path to reference image
            output_path: Output video file path
            
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
            
            # TODO: Implement actual LivePortrait animation
            # For MVP, create a simple video with the reference image
            self._create_simple_video(audio_path, reference_image_path, output_path)
            
            duration_ms = (time.time() - start_time) * 1000
            logger.info(f"Avatar animation completed in {duration_ms:.0f}ms")
            
            return output_path, duration_ms
            
        except Exception as e:
            logger.error(f"Avatar animation failed: {e}", exc_info=True)
            raise
    
    def _create_simple_video(
        self,
        audio_path: str,
        image_path: str,
        output_path: str
    ):
        """
        Create a simple video by combining audio with a static/slightly animated image.
        This is a placeholder until LivePortrait is fully integrated.
        """
        import subprocess
        import soundfile as sf
        
        # Get audio duration
        audio_data, sample_rate = sf.read(audio_path)
        audio_duration = len(audio_data) / sample_rate
        
        # Load and resize image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        target_width, target_height = settings.video_resolution
        img_resized = cv2.resize(img, (target_width, target_height))
        
        # Save resized image temporarily
        temp_img_path = os.path.join(settings.output_dir, "temp_frame.jpg")
        cv2.imwrite(temp_img_path, img_resized)
        
        # Use ffmpeg to create video from image and audio
        # Create a video by looping the image for the duration of the audio
        fps = settings.video_fps
        
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file
            '-loop', '1',  # Loop the image
            '-i', temp_img_path,  # Input image
            '-i', audio_path,  # Input audio
            '-c:v', 'libx264',  # Video codec
            '-tune', 'stillimage',  # Optimize for still image
            '-c:a', 'aac',  # Audio codec
            '-b:a', '192k',  # Audio bitrate
            '-pix_fmt', 'yuv420p',  # Pixel format
            '-shortest',  # Stop when shortest input ends
            '-r', str(fps),  # Frame rate
            output_path
        ]
        
        logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            raise RuntimeError(f"Failed to create video: {result.stderr}")
        
        # Clean up temp image
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
        
        logger.info(f"Created simple video: {output_path}, duration: {audio_duration:.2f}s")
    
    def cleanup(self):
        """Cleanup model resources"""
        if self.model:
            del self.model
            self._initialized = False
            logger.info("Avatar model cleaned up")


# Global instance
_avatar_model: Optional[LivePortraitModel] = None


def get_avatar_model() -> LivePortraitModel:
    """Get or create global avatar model instance"""
    global _avatar_model
    if _avatar_model is None:
        _avatar_model = LivePortraitModel()
    return _avatar_model
