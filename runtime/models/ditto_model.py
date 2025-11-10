"""
Ditto TalkingHead model wrapper
Audio-driven talking head synthesis built on LivePortrait
https://github.com/antgroup/ditto-talkinghead
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple
import tempfile

import torch

logger = logging.getLogger(__name__)


class DittoModel:
    """
    Ditto model wrapper for audio-driven talking head synthesis.
    Uses StreamSDK from ditto-talkinghead for video generation.
    """
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self._initialized = False
        self.sdk = None
        self.data_root = None
        self.cfg_pkl = None
        
    def initialize(self, data_root: Optional[str] = None, cfg_pkl: Optional[str] = None):
        """
        Initialize Ditto StreamSDK with models.
        
        Args:
            data_root: Path to model checkpoints (default: ./checkpoints/ditto_pytorch)
            cfg_pkl: Path to config file (default: ./checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl)
        """
        if self._initialized:
            return
            
        logger.info(f"Initializing Ditto model on {self.device}...")
        start_time = time.time()
        
        try:
            # Import here to avoid issues if ditto isn't available
            from stream_pipeline_offline import StreamSDK
            
            # Set default paths relative to ditto-talkinghead directory
            if data_root is None:
                data_root = "./checkpoints/ditto_pytorch"
            if cfg_pkl is None:
                cfg_pkl = "./checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl"
                
            self.data_root = data_root
            self.cfg_pkl = cfg_pkl
            
            # Initialize StreamSDK
            logger.info(f"Loading Ditto models from {data_root}")
            self.sdk = StreamSDK(cfg_pkl, data_root)
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Ditto initialized in {elapsed:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to initialize Ditto: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if model is initialized"""
        return self._initialized and self.sdk is not None
    
    def generate_video(
        self,
        audio_path: str,
        reference_image_path: str,
        output_path: Optional[str] = None,
        enhancer: Optional[str] = None,  # Ignored for Ditto, kept for API compatibility
        crop_scale: float = 2.3,
        crop_vx_ratio: float = 0,
        crop_vy_ratio: float = -0.125,
        **kwargs
    ) -> Tuple[str, float]:
        """
        Generate animated talking-head video from audio and reference image.
        
        Args:
            audio_path: Path to input audio file (WAV format)
            reference_image_path: Path to reference portrait image
            output_path: Path to save output video (default: temp file)
            enhancer: Ignored for Ditto (kept for API compatibility)
            crop_scale: Crop scale factor for face detection (default: 2.3)
            crop_vx_ratio: Horizontal crop offset (default: 0)
            crop_vy_ratio: Vertical crop offset (default: -0.125)
            **kwargs: Additional parameters for StreamSDK
            
        Returns:
            Tuple of (output_path, generation_time_milliseconds)
        """
        if not self.is_ready():
            # Lazy initialize if not done yet
            self.initialize()
            
        start_time = time.time()
        
        # Create temp output if not specified
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
        
        try:
            logger.info(f"Generating video from audio: {audio_path}")
            logger.info(f"Reference image: {reference_image_path}")
            
            # Register avatar (source image)
            avatar_id = "default"
            self.sdk.avatar_registrar.register(
                reference_image_path,
                avatar_id,
                crop_scale=crop_scale,
                crop_vx_ratio=crop_vx_ratio,
                crop_vy_ratio=crop_vy_ratio
            )
            
            # Process audio and generate video
            self.sdk.drive_one_avatar(
                audio_path=audio_path,
                avatar_id=avatar_id,
                output_path=output_path,
                **kwargs
            )
            
            elapsed = time.time() - start_time
            elapsed_ms = elapsed * 1000  # Convert to milliseconds for consistency
            
            if not os.path.exists(output_path):
                raise RuntimeError(f"Video generation failed - output not found: {output_path}")
                
            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
            logger.info(f"Video generated in {elapsed:.2f}s ({file_size:.1f}MB): {output_path}")
            
            return output_path, elapsed_ms
            
        except Exception as e:
            logger.error(f"Ditto generation failed: {e}")
            if output_path and os.path.exists(output_path):
                os.remove(output_path)
            raise
    
    def unload(self):
        """Unload model to free memory"""
        if self.sdk:
            logger.info("Unloading Ditto model")
            # Ditto doesn't have explicit unload, just delete references
            del self.sdk
            self.sdk = None
            
            # Clear CUDA cache if using GPU
            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                
        self._initialized = False
