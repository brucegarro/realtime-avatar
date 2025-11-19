"""
TTS Client for GPU Service
Calls external GPU acceleration service instead of running TTS in Docker
"""
import logging
import os
import time
import requests
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class XTTSClient:
    """Client for external XTTS GPU service"""
    
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
            tts_ready = health_data.get("models", {}).get("tts", False)
            
            if not tts_ready:
                raise RuntimeError("TTS model not ready on GPU service")
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Connected to GPU service (device={device}) in {elapsed:.2f}s")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to GPU service: {e}")
            raise RuntimeError(f"GPU service unavailable at {self.service_url}") from e
    
    def is_ready(self) -> bool:
        """Check if service is initialized"""
        return self._initialized
    
    def synthesize(
        self,
        text: str,
        language: str = "en",
        speaker_wav: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> tuple[str, float, float]:
        """
        Synthesize speech from text using GPU service.
        
        Args:
            text: Text to synthesize
            language: Language code (en, zh-cn, es, etc.)
            speaker_wav: Path to reference speaker audio (for voice cloning)
            output_path: Output audio file path
            
        Returns:
            Tuple of (output_path, generation_time_ms, audio_duration_s)
        """
        if not self.is_ready():
            self.initialize()
        
        start_time = time.time()
        
        try:
            # Map language codes
            lang_map = {
                "en": "en",
                "zh": "zh-cn",
                "zh-cn": "zh-cn",
                "es": "es"
            }
            lang_code = lang_map.get(language, "en")
            
            # If no speaker wav provided, try to find default reference
            if not speaker_wav:
                # Look for language-specific reference sample
                ref_samples_dir = settings.voice_samples_dir
                if os.path.exists(ref_samples_dir):
                    # Try to find language-specific sample
                    possible_files = [
                        f"bruce_{lang_code.split('-')[0]}_sample.wav",
                        f"bruce_{lang_code}_sample.wav",
                        "bruce_en_sample.wav"  # Fallback to English
                    ]
                    for filename in possible_files:
                        candidate = os.path.join(ref_samples_dir, filename)
                        if os.path.exists(candidate):
                            speaker_wav = candidate
                            logger.info(f"Using reference sample: {filename}")
                            break
            
            # Both containers share the same /app/assets mount, so keep the Docker path
            if speaker_wav:
                logger.info(f"Using speaker_wav path: {speaker_wav}")
            
            # Generate output path if not provided
            if not output_path:
                os.makedirs(settings.output_dir, exist_ok=True)
                output_path = os.path.join(
                    settings.output_dir,
                    f"tts_output_{int(time.time() * 1000)}.wav"
                )
            
            logger.info(f"Requesting TTS: lang={lang_code}, text_len={len(text)}")
            
            # Call GPU service
            payload = {
                "text": text,
                "language": lang_code,
                "speaker_wav": speaker_wav,
                "output_path": output_path
            }
            
            response = requests.post(
                f"{self.service_url}/tts/generate",
                json=payload,
                timeout=300  # 5 min timeout for long texts
            )
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get("success"):
                raise RuntimeError(f"TTS generation failed: {result.get('error')}")
            
            # Get the audio file from GPU service
            remote_audio_path = result.get("audio_path")
            generation_time_ms = result.get("generation_time_ms", 0)
            audio_duration_s = result.get("duration_s", 0)
            
            # Both containers share the gpu-output volume, so we can use the path directly
            # No need to copy since the file is already accessible
            output_path = remote_audio_path
            logger.info(f"Using audio path from GPU service: {output_path}")
            
            total_time_ms = (time.time() - start_time) * 1000
            
            logger.info(f"TTS completed in {total_time_ms:.0f}ms (generation: {generation_time_ms:.0f}ms), audio: {audio_duration_s:.2f}s")
            
            return output_path, total_time_ms, audio_duration_s
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GPU service request failed: {e}")
            raise RuntimeError(f"Failed to communicate with GPU service") from e
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            raise
    
    def cleanup(self):
        """Cleanup (no-op for HTTP client)"""
        self._initialized = False
        logger.info("TTS client disconnected")


# Global instance
_xtts_client: Optional[XTTSClient] = None


def get_xtts_client() -> XTTSClient:
    """Get or create global XTTS client instance"""
    global _xtts_client
    if _xtts_client is None:
        _xtts_client = XTTSClient()
    return _xtts_client
