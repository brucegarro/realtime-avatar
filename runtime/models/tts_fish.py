"""
Fish Speech TTS Model Handler
Fast multilingual TTS with zero-shot voice cloning via HTTP API

Fish Speech is ~5-8x faster than XTTS with comparable quality.
Supports: English, Chinese, Japanese, Korean, Spanish, French, German, Arabic

This implementation uses Fish Speech's HTTP API server (run via Docker or CLI).
The API server should be started separately or as part of docker-compose.

Usage:
    Set TTS_BACKEND=fish_speech in environment to enable.
    Set FISH_SPEECH_API_URL to point to the Fish Speech API server.
    Falls back to XTTS if Fish Speech API is unavailable.
"""
import os
import time
import torch
import logging
import tempfile
import base64
import httpx
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Fish Speech API URL - can run as separate container or use hosted API
FISH_SPEECH_API_URL = os.getenv("FISH_SPEECH_API_URL", "http://localhost:8002")


class FishSpeechModel:
    """
    Fish Speech TTS model wrapper using HTTP API
    
    Provides same interface as XTTSModel for drop-in replacement.
    Communicates with Fish Speech API server for inference.
    """
    
    def __init__(self):
        self.api_url = FISH_SPEECH_API_URL
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialized = False
        self._api_available = False
        # Cache for reference audio (base64 encoded)
        self._speaker_cache = {}
        # HTTP client with longer timeout for TTS
        self._client = httpx.Client(timeout=60.0)
        
    def initialize(self):
        """Check Fish Speech API availability"""
        if self._initialized:
            return
            
        logger.info(f"Checking Fish Speech API at {self.api_url}...")
        start_time = time.time()
        
        try:
            # Check if API is available
            response = self._client.get(f"{self.api_url}/v1/health", timeout=5.0)
            if response.status_code == 200:
                self._api_available = True
                self._initialized = True
                elapsed = time.time() - start_time
                logger.info(f"Fish Speech API available in {elapsed:.2f}s")
            else:
                raise ConnectionError(f"Fish Speech API returned {response.status_code}")
                
        except httpx.ConnectError:
            # API not available - try alternate health endpoint
            try:
                response = self._client.get(f"{self.api_url}/health", timeout=5.0)
                if response.status_code == 200:
                    self._api_available = True
                    self._initialized = True
                    logger.info("Fish Speech API available (alternate endpoint)")
                else:
                    raise
            except Exception:
                logger.warning(f"Fish Speech API not available at {self.api_url}")
                logger.warning("Make sure Fish Speech server is running")
                # Still mark as initialized but not available
                self._initialized = True
                self._api_available = False
                
        except Exception as e:
            logger.error(f"Failed to connect to Fish Speech API: {e}")
            self._initialized = True
            self._api_available = False
    
    def is_ready(self) -> bool:
        """Check if model/API is initialized and available"""
        if not self._initialized:
            self.initialize()
        return self._api_available
    
    def _encode_audio_file(self, audio_path: str) -> Optional[str]:
        """
        Encode audio file to base64 for API request.
        Caches results to avoid re-encoding same files.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Base64 encoded audio string
        """
        if not audio_path or not os.path.exists(audio_path):
            return None
            
        # Check cache
        if audio_path in self._speaker_cache:
            return self._speaker_cache[audio_path]
        
        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            encoded = base64.b64encode(audio_bytes).decode("utf-8")
            self._speaker_cache[audio_path] = encoded
            logger.info(f"Encoded reference audio: {os.path.basename(audio_path)} ({len(audio_bytes)} bytes)")
            return encoded
            
        except Exception as e:
            logger.warning(f"Failed to encode audio file: {e}")
            return None
    
    def synthesize(
        self,
        text: str,
        language: str = "en",
        speaker_wav: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Tuple[str, float, float]:
        """
        Synthesize speech from text using Fish Speech API.
        
        Args:
            text: Text to synthesize
            language: Language code (en, zh, es, etc.)
            speaker_wav: Path to reference speaker audio (for voice cloning)
            output_path: Output audio file path
            
        Returns:
            Tuple of (output_path, generation_time_ms, audio_duration_s)
        """
        if not self.is_ready():
            raise RuntimeError("Fish Speech API not available. Check if server is running.")
        
        start_time = time.time()
        
        try:
            # Generate output path if not provided
            if not output_path:
                output_dir = os.getenv("OUTPUT_DIR", "/tmp/gpu-service-output")
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(
                    output_dir,
                    f"tts_fish_{int(time.time() * 1000)}.wav"
                )
            
            # Prepare request payload
            # Fish Speech API uses OpenAI-compatible format
            payload = {
                "input": text,
                "voice": "default",  # Will be overridden by reference audio
            }
            
            # Add reference audio for voice cloning
            if speaker_wav:
                reference_audio = self._encode_audio_file(speaker_wav)
                if reference_audio:
                    payload["reference_audio"] = reference_audio
            
            logger.info(f"Fish Speech synthesizing: lang={language}, text_len={len(text)}, voice_clone={speaker_wav is not None}")
            
            # Call Fish Speech API
            # Try OpenAI-compatible endpoint first
            api_endpoint = f"{self.api_url}/v1/audio/speech"
            
            response = self._client.post(
                api_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                # Try alternate endpoint format
                api_endpoint = f"{self.api_url}/tts"
                response = self._client.post(
                    api_endpoint,
                    json={
                        "text": text,
                        "speaker_wav": speaker_wav,  # Some APIs accept path directly
                        "language": language
                    }
                )
            
            if response.status_code != 200:
                raise RuntimeError(f"Fish Speech API error: {response.status_code} - {response.text}")
            
            # Save audio response
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            generation_time_ms = (time.time() - start_time) * 1000
            
            # Calculate audio duration
            try:
                import soundfile as sf
                audio_data, sample_rate = sf.read(output_path)
                audio_duration_s = len(audio_data) / sample_rate
            except Exception:
                # Estimate duration if soundfile fails
                audio_duration_s = len(text) * 0.08  # ~80ms per character estimate
            
            rtf = (generation_time_ms / 1000) / audio_duration_s if audio_duration_s > 0 else 0
            logger.info(f"Fish Speech TTS completed in {generation_time_ms:.0f}ms, audio: {audio_duration_s:.2f}s, RTF: {rtf:.2f}x")
            
            return output_path, generation_time_ms, audio_duration_s
            
        except Exception as e:
            logger.error(f"Fish Speech synthesis failed: {e}", exc_info=True)
            raise
    
    def cleanup(self):
        """Cleanup resources"""
        self._client.close()
        self._initialized = False
        self._api_available = False
        self._speaker_cache.clear()
        logger.info("Fish Speech client cleaned up")


# Global instance
_fish_speech_model: Optional[FishSpeechModel] = None


def get_fish_speech_model() -> FishSpeechModel:
    """Get or create global Fish Speech model instance"""
    global _fish_speech_model
    if _fish_speech_model is None:
        _fish_speech_model = FishSpeechModel()
    return _fish_speech_model
