"""
StyleTTS2 model wrapper for fast voice cloning and TTS
~10-20x faster than XTTS-v2 with comparable quality

GitHub: https://github.com/yl4579/StyleTTS2
Paper: https://arxiv.org/abs/2306.07691
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional, List
import tempfile

import torch
import torchaudio
import numpy as np

logger = logging.getLogger(__name__)


class StyleTTS2Model:
    """
    StyleTTS2 wrapper for fast, high-quality voice cloning.
    
    Performance:
    - Speed: ~0.1-0.2s per second of audio (10-20x faster than XTTS-v2)
    - Quality: Near XTTS quality with emotional control
    - Voice cloning: Few-shot (10-30s of reference audio)
    """
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self._initialized = False
        self.model = None
        self.sampler = None
        self.text_cleaner = None
        self.to_mel = None
        
    def initialize(self, 
                   model_path: Optional[str] = None,
                   config_path: Optional[str] = None):
        """
        Initialize StyleTTS2 model.
        
        Args:
            model_path: Path to model checkpoint (default: download LJSpeech multi-speaker)
            config_path: Path to model config (default: use bundled config)
        """
        if self._initialized:
            return
            
        logger.info(f"Initializing StyleTTS2 model on {self.device}...")
        start_time = time.time()
        
        try:
            # Import StyleTTS2 components
            from styletts2 import tts
            from styletts2.text_utils import TextCleaner
            from styletts2.Utils.PLBERT.util import load_plbert
            
            # Set default paths
            if model_path is None:
                model_path = "./checkpoints/styletts2/lj_speech_multispeaker.pth"
            if config_path is None:
                config_path = "./checkpoints/styletts2/config.yml"
                
            # Check if model exists, download if needed
            if not os.path.exists(model_path):
                logger.info("StyleTTS2 model not found, downloading...")
                self._download_models(model_path, config_path)
            
            # Initialize text cleaner
            self.text_cleaner = TextCleaner()
            
            # Load model
            logger.info(f"Loading StyleTTS2 from {model_path}")
            self.model = tts.StyleTTS2(
                config_path=config_path,
                model_path=model_path,
                device=self.device
            )
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"StyleTTS2 initialized in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to initialize StyleTTS2: {e}")
            raise
    
    def _download_models(self, model_path: str, config_path: str):
        """Download pre-trained StyleTTS2 models"""
        import urllib.request
        from pathlib import Path
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Download LJSpeech multi-speaker model
        model_url = "https://huggingface.co/yl4579/StyleTTS2-LJSpeech/resolve/main/Models/LJSpeech/epoch_2nd_00100.pth"
        config_url = "https://huggingface.co/yl4579/StyleTTS2-LJSpeech/resolve/main/Models/LJSpeech/config.yml"
        
        logger.info(f"Downloading model to {model_path}")
        urllib.request.urlretrieve(model_url, model_path)
        
        logger.info(f"Downloading config to {config_path}")
        urllib.request.urlretrieve(config_url, config_path)
        
        logger.info("StyleTTS2 models downloaded successfully")
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized and self.model is not None
    
    def synthesize(
        self,
        text: str,
        reference_audio: Optional[str] = None,
        output_path: Optional[str] = None,
        alpha: float = 0.3,
        beta: float = 0.7,
        diffusion_steps: int = 5,
        embedding_scale: float = 1.0
    ) -> str:
        """
        Synthesize speech from text using voice cloning.
        
        Args:
            text: Text to synthesize
            reference_audio: Path to reference audio for voice cloning
            output_path: Output audio file path (default: temp file)
            alpha: Timbre control (0-1, lower = closer to reference)
            beta: Prosody control (0-1, lower = more expressive)
            diffusion_steps: Decoder steps (5-10 recommended, lower = faster)
            embedding_scale: Style strength (0.5-2.0)
            
        Returns:
            Path to output audio file
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized. Call initialize() first.")
        
        start_time = time.time()
        
        try:
            # Create output path if not provided
            if output_path is None:
                output_path = tempfile.mktemp(suffix=".wav")
            
            # Load reference audio if provided
            ref_embedding = None
            if reference_audio and os.path.exists(reference_audio):
                logger.debug(f"Loading reference audio: {reference_audio}")
                ref_embedding = self._extract_embedding(reference_audio)
            
            # Clean and prepare text
            cleaned_text = self.text_cleaner(text)
            
            # Synthesize
            logger.debug(f"Synthesizing: '{text[:50]}...'")
            audio = self.model.inference(
                text=cleaned_text,
                ref_s=ref_embedding,
                alpha=alpha,
                beta=beta,
                diffusion_steps=diffusion_steps,
                embedding_scale=embedding_scale
            )
            
            # Save audio
            torchaudio.save(
                output_path,
                torch.tensor(audio).unsqueeze(0),
                24000  # StyleTTS2 default sample rate
            )
            
            elapsed = time.time() - start_time
            audio_duration = len(audio) / 24000
            realtime_factor = elapsed / audio_duration if audio_duration > 0 else 0
            
            logger.info(
                f"Generated {audio_duration:.2f}s audio in {elapsed:.2f}s "
                f"(RTF: {realtime_factor:.2f}x)"
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"StyleTTS2 synthesis failed: {e}")
            raise
    
    def _extract_embedding(self, audio_path: str) -> torch.Tensor:
        """Extract speaker embedding from reference audio"""
        try:
            # Load audio
            wav, sr = torchaudio.load(audio_path)
            
            # Resample to 24kHz if needed
            if sr != 24000:
                resampler = torchaudio.transforms.Resample(sr, 24000)
                wav = resampler(wav)
            
            # Convert to mono if stereo
            if wav.shape[0] > 1:
                wav = wav.mean(dim=0, keepdim=True)
            
            # Extract embedding using model's encoder
            with torch.no_grad():
                embedding = self.model.extract_speaker_embedding(wav.to(self.device))
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to extract embedding from {audio_path}: {e}")
            raise
    
    def synthesize_batch(
        self,
        texts: List[str],
        reference_audio: Optional[str] = None,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> List[str]:
        """
        Synthesize multiple texts in batch (for better efficiency).
        
        Args:
            texts: List of texts to synthesize
            reference_audio: Reference audio for voice cloning
            output_dir: Output directory (default: temp dir)
            **kwargs: Additional synthesis parameters
            
        Returns:
            List of output audio file paths
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp()
        os.makedirs(output_dir, exist_ok=True)
        
        outputs = []
        for i, text in enumerate(texts):
            output_path = os.path.join(output_dir, f"output_{i:03d}.wav")
            result = self.synthesize(
                text=text,
                reference_audio=reference_audio,
                output_path=output_path,
                **kwargs
            )
            outputs.append(result)
        
        return outputs
    
    def clone_voice(
        self,
        reference_audios: List[str],
        output_embedding_path: Optional[str] = None
    ) -> str:
        """
        Create a voice embedding from multiple reference audios (for fine-tuning).
        
        Args:
            reference_audios: List of reference audio paths
            output_embedding_path: Path to save embedding
            
        Returns:
            Path to saved embedding file
        """
        logger.info(f"Creating voice embedding from {len(reference_audios)} samples")
        
        embeddings = []
        for audio_path in reference_audios:
            embedding = self._extract_embedding(audio_path)
            embeddings.append(embedding)
        
        # Average embeddings
        avg_embedding = torch.stack(embeddings).mean(dim=0)
        
        # Save embedding
        if output_embedding_path is None:
            output_embedding_path = tempfile.mktemp(suffix=".pt")
        
        torch.save(avg_embedding, output_embedding_path)
        logger.info(f"Voice embedding saved to {output_embedding_path}")
        
        return output_embedding_path
