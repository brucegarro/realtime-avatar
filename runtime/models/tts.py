"""
Text-to-Speech Model Handler
Manages XTTS-v2 multilingual TTS with voice cloning
"""
import os
import time
import torch
import logging
from typing import Optional, Tuple
from pathlib import Path

# Monkey patch for PyTorch 2.6+ compatibility with XTTS
# PyTorch 2.6 changed torch.load() default to weights_only=True for security
# XTTS needs weights_only=False to load custom classes
import torch.serialization
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

from TTS.api import TTS
from config import settings

logger = logging.getLogger(__name__)


class XTTSModel:
    """XTTS-v2 TTS model wrapper"""
    
    def __init__(self):
        self.model: Optional[TTS] = None
        self.device = settings.device
        self._initialized = False
        
    def initialize(self):
        """Load XTTS-v2 model"""
        if self._initialized:
            return
            
        logger.info(f"Loading XTTS-v2 model on {self.device}...")
        start_time = time.time()
        
        try:
            # Initialize TTS with XTTS-v2 model
            # Note: Will download model on first run
            self.model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False,
                gpu=(self.device == "cuda")
            )
            
            if self.device == "cuda":
                self.model.to(self.device)
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"XTTS-v2 model loaded in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to load XTTS-v2 model: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized and self.model is not None
    
    def synthesize(
        self,
        text: str,
        language: str = "en",
        speaker_wav: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> tuple[str, float]:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            language: Language code (en, zh-cn, es, etc.)
            speaker_wav: Path to reference speaker audio (for voice cloning)
            output_path: Output audio file path
            
        Returns:
            Tuple of (output_path, duration_ms)
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
            
            # Generate output path if not provided
            if not output_path:
                os.makedirs(settings.output_dir, exist_ok=True)
                output_path = os.path.join(
                    settings.output_dir,
                    f"tts_output_{int(time.time() * 1000)}.wav"
                )
            
            logger.info(f"Synthesizing: lang={lang_code}, text_len={len(text)}, speaker_wav={speaker_wav}")
            
            # Synthesize with XTTS-v2
            # When using speaker_wav for voice cloning, XTTS checks for speaker param first
            # We must explicitly pass speaker=None when using speaker_wav
            if speaker_wav and os.path.exists(speaker_wav):
                self.model.tts_to_file(
                    text=text,
                    file_path=output_path,
                    speaker=None,
                    speaker_wav=speaker_wav,
                    language=lang_code,
                    split_sentences=True
                )
            else:
                # No voice cloning - would need a speaker name
                raise ValueError("speaker_wav is required for XTTS voice cloning")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Get actual audio duration
            import soundfile as sf
            audio_data, sample_rate = sf.read(output_path)
            audio_duration_s = len(audio_data) / sample_rate
            
            logger.info(f"TTS completed in {duration_ms:.0f}ms, audio duration: {audio_duration_s:.2f}s")
            
            return output_path, duration_ms, audio_duration_s
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}", exc_info=True)
            raise
    
    def cleanup(self):
        """Cleanup model resources"""
        if self.model:
            del self.model
            if self.device == "cuda":
                torch.cuda.empty_cache()
            self._initialized = False
            logger.info("XTTS-v2 model cleaned up")


# Global instance
_xtts_model: Optional[XTTSModel] = None


def get_xtts_model() -> XTTSModel:
    """Get or create global XTTS model instance"""
    global _xtts_model
    if _xtts_model is None:
        _xtts_model = XTTSModel()
    return _xtts_model
