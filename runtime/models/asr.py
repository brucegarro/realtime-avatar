"""
Faster-Whisper ASR model wrapper for real-time speech recognition
~5-10x faster than OpenAI Whisper with same accuracy

GitHub: https://github.com/guillaumekln/faster-whisper
Based on: CTranslate2 (optimized inference engine)
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional, List, Tuple, Iterator
import tempfile

import numpy as np

logger = logging.getLogger(__name__)


class ASRModel:
    """
    Faster-Whisper wrapper for real-time speech recognition.
    
    Performance:
    - Speed: 5-10x faster than vanilla Whisper
    - Latency: ~100-200ms for short utterances
    - Accuracy: Same as OpenAI Whisper (same models)
    - Memory: Lower memory usage with CTranslate2
    """
    
    def __init__(self, device: str = "cuda", compute_type: str = "float16"):
        """
        Initialize Faster-Whisper model.
        
        Args:
            device: "cuda" or "cpu"
            compute_type: Precision ("float16", "int8_float16", "int8")
                         int8 is ~2x faster with minimal quality loss
        """
        self.device = device
        self.compute_type = compute_type
        self._initialized = False
        self.model = None
        self.vad_model = None
        
    def initialize(self, 
                   model_size: str = "base",
                   use_vad: bool = True,
                   vad_threshold: float = 0.5):
        """
        Initialize Faster-Whisper model and optional VAD.
        
        Args:
            model_size: Model size ("tiny", "base", "small", "medium", "large-v2", "large-v3")
                       - tiny: fastest, least accurate (~1GB)
                       - base: good balance (~1GB)
                       - small: better quality (~2GB)
                       - medium: high quality (~5GB)
                       - large-v3: best quality (~3GB, newest)
            use_vad: Enable Voice Activity Detection for filtering
            vad_threshold: VAD sensitivity (0-1, lower = more sensitive)
        """
        if self._initialized:
            return
            
        logger.info(f"Initializing Faster-Whisper ({model_size}) on {self.device}...")
        start_time = time.time()
        
        try:
            from faster_whisper import WhisperModel
            
            # Initialize Whisper model
            self.model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root="./checkpoints/faster-whisper"
            )
            
            # Initialize VAD if requested
            if use_vad:
                self._initialize_vad(vad_threshold)
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Faster-Whisper initialized in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to initialize Faster-Whisper: {e}")
            raise
    
    def _initialize_vad(self, threshold: float = 0.5):
        """Initialize Silero VAD for voice activity detection"""
        try:
            import torch
            
            logger.info("Loading Silero VAD model...")
            self.vad_model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            (self.get_speech_timestamps,
             self.save_audio,
             self.read_audio,
             self.VADIterator,
             self.collect_chunks) = utils
            
            self.vad_threshold = threshold
            logger.info("VAD initialized")
            
        except Exception as e:
            logger.warning(f"VAD initialization failed: {e}. Continuing without VAD.")
            self.vad_model = None
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized and self.model is not None
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        best_of: int = 5,
        temperature: float = 0.0,
        vad_filter: bool = True
    ) -> Tuple[str, dict]:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to audio file (any format supported by ffmpeg)
            language: Source language code (None = auto-detect)
            task: "transcribe" or "translate" (to English)
            beam_size: Beam search size (1-10, higher = more accurate but slower)
            best_of: Number of candidates (1-10)
            temperature: Sampling temperature (0.0 = greedy, >0 = sampling)
            vad_filter: Apply VAD filtering if available
            
        Returns:
            Tuple of (transcription text, metadata dict)
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized. Call initialize() first.")
        
        start_time = time.time()
        
        # Log language parameter for debugging
        logger.info(f"ASR transcribe called: language={language}, task={task}")
        
        try:
            # Apply VAD if enabled
            if vad_filter and self.vad_model is not None:
                audio_path = self._apply_vad(audio_path)
            
            # Transcribe with anti-hallucination settings
            # - condition_on_previous_text=False prevents repetition loops
            # - no_speech_threshold helps filter silence
            # - compression_ratio_threshold catches repetitive hallucinations
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                task=task,
                beam_size=beam_size,
                best_of=best_of,
                temperature=temperature,
                vad_filter=vad_filter and self.vad_model is not None,
                condition_on_previous_text=False,  # Prevents repetition hallucinations
                no_speech_threshold=0.6,  # Filter low-confidence segments
                compression_ratio_threshold=2.4,  # Catch repetitive text
            )
            
            # Log detected language vs requested
            logger.info(f"ASR result: detected_lang={info.language}, probability={info.language_probability:.2f}")
            
            # Collect segments
            full_text = []
            segment_list = []
            
            for segment in segments:
                full_text.append(segment.text)
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "confidence": getattr(segment, 'avg_logprob', None)
                })
            
            transcription = " ".join(full_text).strip()
            
            elapsed = time.time() - start_time
            logger.info(
                f"Transcribed in {elapsed:.2f}s | "
                f"Language: {info.language} | "
                f"Text: '{transcription[:50]}...'"
            )
            
            metadata = {
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "transcription_time": elapsed,
                "segments": segment_list
            }
            
            return transcription, metadata
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise
    
    def _apply_vad(self, audio_path: str) -> str:
        """Apply VAD filtering to remove silence"""
        try:
            import torch
            
            # Read audio
            wav = self.read_audio(audio_path, sampling_rate=16000)
            
            # Get speech timestamps
            speech_timestamps = self.get_speech_timestamps(
                wav,
                self.vad_model,
                threshold=self.vad_threshold,
                sampling_rate=16000
            )
            
            if not speech_timestamps:
                logger.warning("No speech detected by VAD")
                return audio_path
            
            # Collect speech chunks
            speech_audio = self.collect_chunks(speech_timestamps, wav)
            
            # Save filtered audio
            output_path = tempfile.mktemp(suffix=".wav")
            self.save_audio(output_path, speech_audio, sampling_rate=16000)
            
            logger.debug(f"VAD filtered: {len(speech_timestamps)} speech segments")
            return output_path
            
        except Exception as e:
            logger.warning(f"VAD filtering failed: {e}. Using original audio.")
            return audio_path
    
    def detect_language(self, audio_path: str) -> Tuple[str, float]:
        """
        Detect language of audio file.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Tuple of (language_code, confidence)
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized. Call initialize() first.")
        
        try:
            segments, info = self.model.transcribe(audio_path, beam_size=1)
            
            # Consume first segment to get info
            _ = next(segments, None)
            
            return info.language, info.language_probability
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            raise
    
    def cleanup(self):
        """Cleanup model resources"""
        if self.model:
            del self.model
            self._initialized = False
            logger.info("ASR model cleaned up")


# Global instance
_asr_model: Optional[ASRModel] = None


def get_asr_model() -> ASRModel:
    """Get or create global ASR model instance"""
    global _asr_model
    if _asr_model is None:
        _asr_model = ASRModel()
    return _asr_model
