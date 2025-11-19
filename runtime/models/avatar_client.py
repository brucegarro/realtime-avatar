"""
Avatar Client for GPU Service
Calls external GPU acceleration service for LivePortrait video generation
"""
import logging
import os
import time
import requests
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class AvatarClient:
    """Client for external LivePortrait GPU service"""
    
    def __init__(self, service_url: Optional[str] = None):
        self.service_url = service_url or settings.gpu_service_url
        self._initialized = False
        
    def initialize(self):
        """Check if GPU service is available"""
        if self._initialized:
            return
            
        logger.info(f"Connecting to GPU service at {self.service_url}...")
        start_time = time.time()
        
        try:
            # Check health endpoint
            response = requests.get(
                f"{self.service_url}/health",
                timeout=5
            )
            response.raise_for_status()
            
            health_data = response.json()
            device = health_data.get("device", "unknown")
            avatar_ready = health_data.get("models", {}).get("avatar", False)
            
            if not avatar_ready:
                raise RuntimeError("Avatar model not ready on GPU service")
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Connected to GPU service (device={device}) for avatar generation in {elapsed:.2f}s")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to GPU service: {e}")
            raise RuntimeError(f"GPU service unavailable at {self.service_url}") from e
    
    def is_ready(self) -> bool:
        """Check if service is initialized"""
        return self._initialized
    
    def generate_video(
        self,
        audio_path: str,
        reference_image_path: str,
        output_path: Optional[str] = None,
        enhancer: Optional[str] = None
    ) -> tuple[str, float]:
        """
        Generate talking head video from audio and reference image.
        
        Args:
            audio_path: Path to audio file (WAV)
            reference_image_path: Path to reference face image
            output_path: Output video file path (optional)
            enhancer: Face enhancer to use ('gfpgan' or None)
            
        Returns:
            Tuple of (video_path, generation_time_ms)
        """
        if not self.is_ready():
            self.initialize()
        
        start_time = time.time()
        
        try:
            # Both GPU service and runtime use Docker paths
            # No mapping needed - both containers share /app/assets mount
            logger.info(f"Requesting avatar video: audio={audio_path}, image={reference_image_path}")
            
            # Generate output path if not provided
            if not output_path:
                os.makedirs(settings.output_dir, exist_ok=True)
                output_path = os.path.join(
                    settings.output_dir,
                    f"avatar_output_{int(time.time() * 1000)}.mp4"
                )
            
            # Call GPU service
            payload = {
                "audio_path": audio_path,
                "reference_image": reference_image_path,
                "mode": "sadtalker",
                "enhancer": enhancer
            }
            
            response = requests.post(
                f"{self.service_url}/avatar/generate",
                json=payload,
                timeout=600  # 10 min timeout for video generation
            )
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get("success"):
                raise RuntimeError(f"Avatar generation failed: {result.get('error')}")
            
            # Get the video file from GPU service
            remote_video_path = result.get("video_path")
            
            # Both containers share /tmp/gpu-service-output volume (read-only for runtime)
            # Use the GPU service output path directly instead of copying
            output_path = remote_video_path
            logger.info(f"Using video path from GPU service: {output_path}")
            
            total_time_ms = (time.time() - start_time) * 1000
            
            logger.info(f"Avatar video generated in {total_time_ms:.0f}ms")
            
            return output_path, total_time_ms
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GPU service request failed: {e}")
            raise RuntimeError(f"Failed to communicate with GPU service") from e
        except Exception as e:
            logger.error(f"Avatar generation failed: {e}", exc_info=True)
            raise
    
    def cleanup(self):
        """Cleanup (no-op for HTTP client)"""
        self._initialized = False
        logger.info("Avatar client disconnected")


# Global instance
_avatar_client: Optional[AvatarClient] = None


def get_avatar_client() -> AvatarClient:
    """Get or create global Avatar client instance"""
    global _avatar_client
    if _avatar_client is None:
        _avatar_client = AvatarClient()
    return _avatar_client
