"""
Fish Speech TTS Model Handler
Fast multilingual TTS with zero-shot voice cloning via Gradio API

Fish Speech is ~5-8x faster than XTTS with comparable quality.
Supports: English, Chinese, Japanese, Korean, Spanish, French, German, Arabic

This implementation uses Fish Speech's Gradio WebUI API (run via Docker).
The API server should be started separately or as part of docker-compose.

Usage:
    Set TTS_BACKEND=fish_speech in environment to enable.
    Set FISH_SPEECH_URL to point to the Fish Speech Gradio server.
    Falls back to XTTS if Fish Speech API is unavailable.

API Endpoint: POST /gradio_api/call/partial
Parameters (in order):
    - text: str
    - reference_id: str (empty for uploaded reference)
    - reference_audio: FileData (null if not cloning)
    - reference_text: str (optional transcript)
    - max_new_tokens: int (0 = no limit)
    - chunk_length: int (300 default)
    - top_p: float (0.8)
    - repetition_penalty: float (1.1)
    - temperature: float (0.8)
    - seed: int (0 = random)
    - use_memory_cache: str ("on" or "off")
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
FISH_SPEECH_URL = os.getenv("FISH_SPEECH_URL", "http://localhost:8002")


class FishSpeechModel:
    """
    Fish Speech TTS model wrapper using Gradio API
    
    Provides same interface as XTTSModel for drop-in replacement.
    Communicates with Fish Speech Gradio server for inference.
    """
    
    def __init__(self):
        self.api_url = FISH_SPEECH_URL
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialized = False
        self._api_available = False
        # Cache for uploaded reference audio
        self._speaker_cache = {}
        # HTTP client with longer timeout for TTS
        self._client = httpx.Client(timeout=120.0)
        
    def initialize(self):
        """Check Fish Speech API availability"""
        if self._initialized:
            return
            
        logger.info(f"Checking Fish Speech Gradio API at {self.api_url}...")
        start_time = time.time()
        
        try:
            # Check if Gradio API is available by hitting the root
            response = self._client.get(f"{self.api_url}/", timeout=10.0)
            if response.status_code == 200 and "gradio" in response.text.lower():
                self._api_available = True
                self._initialized = True
                elapsed = time.time() - start_time
                logger.info(f"Fish Speech Gradio API available in {elapsed:.2f}s")
            else:
                raise ConnectionError(f"Fish Speech API returned {response.status_code}")
                
        except httpx.ConnectError as e:
            logger.warning(f"Fish Speech API not available at {self.api_url}: {e}")
            logger.warning("Make sure Fish Speech container is running")
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
    
    def _upload_file_to_gradio(self, file_path: str) -> Optional[dict]:
        """
        Upload a file to Gradio server and get FileData dict.
        
        Args:
            file_path: Path to local audio file
            
        Returns:
            Gradio FileData dict or None
        """
        if not file_path or not os.path.exists(file_path):
            return None
            
        # Check cache
        if file_path in self._speaker_cache:
            return self._speaker_cache[file_path]
        
        try:
            # Upload file to Gradio
            with open(file_path, "rb") as f:
                files = {"files": (os.path.basename(file_path), f, "audio/wav")}
                response = self._client.post(
                    f"{self.api_url}/gradio_api/upload",
                    files=files
                )
            
            if response.status_code == 200:
                result = response.json()
                # Gradio returns list of uploaded file paths
                if result and len(result) > 0:
                    uploaded_path = result[0]
                    file_data = {
                        "path": uploaded_path,
                        "url": f"{self.api_url}/gradio_api/file={uploaded_path}",
                        "orig_name": os.path.basename(file_path),
                        "mime_type": "audio/wav",
                        "is_stream": False,
                        "meta": {"_type": "gradio.FileData"}
                    }
                    self._speaker_cache[file_path] = file_data
                    logger.info(f"Uploaded reference audio to Gradio: {uploaded_path}")
                    return file_data
            
            logger.warning(f"Failed to upload file to Gradio: {response.status_code}")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to upload audio file: {e}")
            return None
    
    def synthesize(
        self,
        text: str,
        language: str = "en",
        speaker_wav: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> Tuple[str, float, float]:
        """
        Synthesize speech from text using Fish Speech Gradio API.
        
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
            
            # Upload reference audio if provided
            reference_file_data = None
            if speaker_wav:
                reference_file_data = self._upload_file_to_gradio(speaker_wav)
            
            logger.info(f"Fish Speech synthesizing: lang={language}, text_len={len(text)}, voice_clone={speaker_wav is not None}")
            
            # Gradio API parameters (in order):
            # text, reference_id, reference_audio, reference_text,
            # max_new_tokens, chunk_length, top_p, repetition_penalty,
            # temperature, seed, use_memory_cache
            payload = {
                "data": [
                    text,           # Input text
                    "",             # Reference ID (empty = use uploaded)
                    reference_file_data,  # Reference audio FileData
                    "",             # Reference text (optional)
                    0,              # max_new_tokens (0 = no limit)
                    300,            # chunk_length
                    0.8,            # top_p
                    1.1,            # repetition_penalty
                    0.8,            # temperature
                    0,              # seed (0 = random)
                    "on"            # use_memory_cache
                ]
            }
            
            # Step 1: Submit the request
            response = self._client.post(
                f"{self.api_url}/gradio_api/call/partial",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"Fish Speech API error: {response.status_code} - {response.text}")
            
            event_id = response.json().get("event_id")
            if not event_id:
                raise RuntimeError("No event_id returned from Fish Speech API")
            
            # Step 2: Poll for result
            result_url = f"{self.api_url}/gradio_api/call/partial/{event_id}"
            max_wait = 120  # seconds
            poll_start = time.time()
            
            while time.time() - poll_start < max_wait:
                result_response = self._client.get(result_url)
                if result_response.status_code == 200:
                    # Parse SSE response
                    text_content = result_response.text
                    if "event: complete" in text_content:
                        # Extract data from SSE format
                        import json
                        for line in text_content.split("\n"):
                            if line.startswith("data: "):
                                data = json.loads(line[6:])
                                if data and len(data) > 0 and data[0]:
                                    audio_info = data[0]
                                    audio_url = audio_info.get("url") or f"{self.api_url}/gradio_api/file={audio_info.get('path')}"
                                    
                                    # Download the audio file
                                    audio_response = self._client.get(audio_url)
                                    if audio_response.status_code == 200:
                                        with open(output_path, "wb") as f:
                                            f.write(audio_response.content)
                                        break
                        break
                    elif "event: error" in text_content:
                        raise RuntimeError(f"Fish Speech error: {text_content}")
                
                time.sleep(0.1)  # Poll every 100ms
            
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
