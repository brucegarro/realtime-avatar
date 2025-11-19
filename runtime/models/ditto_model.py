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
        
    def initialize(self, data_root: Optional[str] = None, cfg_pkl: Optional[str] = None, use_tensorrt: bool = True):
        """
        Initialize Ditto StreamSDK with models.
        
        Args:
            data_root: Path to model checkpoints (default: auto-detect TRT or PyTorch)
            cfg_pkl: Path to config file (default: auto-detect TRT or PyTorch config)
            use_tensorrt: Whether to use TensorRT engines (default: True for CUDA)
        """
        if self._initialized:
            return
            
        logger.info(f"Initializing Ditto model on {self.device} (TensorRT: {use_tensorrt})...")
        start_time = time.time()
        
        try:
            # Enable PyTorch CUDA optimizations for faster inference
            if self.device == "cuda" and torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                logger.info("CUDA optimizations enabled (TF32, cuDNN benchmark)")
            
            # Import here to avoid issues if ditto isn't available
            from stream_pipeline_offline import StreamSDK
            
            # Auto-detect TensorRT or PyTorch checkpoints
            if data_root is None:
                trt_path = "/app/ditto-checkpoints/ditto_trt_Ampere_Plus"
                trt_exists = os.path.exists(trt_path)
                logger.info(f"TensorRT checkpoint check: use_tensorrt={use_tensorrt}, path_exists={trt_exists}")
                
                if use_tensorrt and trt_exists:
                    data_root = trt_path
                    logger.info("✅ Using TensorRT Ampere+ engines")
                else:
                    data_root = "/app/ditto-talkinghead/checkpoints/ditto_pytorch"
                    logger.info(f"Using PyTorch models (TRT disabled or path missing)")
                    
            if cfg_pkl is None:
                if use_tensorrt and "trt" in str(data_root):
                    # TensorRT config
                    cfg_pkl = "/app/ditto-checkpoints/ditto_cfg/v0.4_hubert_cfg_trt.pkl"
                    logger.info(f"Using TensorRT config: {os.path.basename(cfg_pkl)}")
                else:
                    # PyTorch config
                    fast_cfg = "/app/ditto-talkinghead/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch_fast.pkl"
                    default_cfg = "/app/ditto-talkinghead/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl"
                    cfg_pkl = fast_cfg if os.path.exists(fast_cfg) else default_cfg
                    logger.info(f"Using PyTorch config: {os.path.basename(cfg_pkl)}")
                
            self.data_root = data_root
            self.cfg_pkl = cfg_pkl
            
            # Initialize StreamSDK
            logger.info(f"Loading Ditto models from {data_root}")
            self.sdk = StreamSDK(cfg_pkl, data_root)
            
            self._initialized = True
            elapsed = time.time() - start_time
            logger.info(f"Ditto initialized with {os.path.basename(data_root)} in {elapsed:.2f}s")
            
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
            
            # Setup SDK with source image and output path
            setup_kwargs = {
                'crop_scale': crop_scale,
                'crop_vx_ratio': crop_vx_ratio,
                'crop_vy_ratio': crop_vy_ratio
            }
            self.sdk.setup(reference_image_path, output_path, **setup_kwargs)
            
            # Load audio and calculate number of frames
            import librosa
            import math
            audio, sr = librosa.core.load(audio_path, sr=16000)
            num_frames = math.ceil(len(audio) / 16000 * 25)
            
            # Setup number of frames
            fade_in = kwargs.get('fade_in', -1)
            fade_out = kwargs.get('fade_out', -1)
            ctrl_info = kwargs.get('ctrl_info', {})
            self.sdk.setup_Nd(N_d=num_frames, fade_in=fade_in, fade_out=fade_out, ctrl_info=ctrl_info)
            
            # Process audio (offline mode)
            aud_feat = self.sdk.wav2feat.wav2feat(audio)
            self.sdk.audio2motion_queue.put(aud_feat)
            self.sdk.close()
            
            # Add audio track to video
            tmp_video = self.sdk.tmp_output_path
            cmd = f'ffmpeg -loglevel error -y -i "{tmp_video}" -i "{audio_path}" -map 0:v -map 1:a -c:v copy -c:a aac "{output_path}"'
            os.system(cmd)
            
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
