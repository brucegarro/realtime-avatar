"""
SadTalker Model Wrapper
Audio-driven talking head video generation using SadTalker
"""
import os
import sys
import time
import torch
import logging
from pathlib import Path

# Add SadTalker to path
SADTALKER_DIR = Path(__file__).parent.parent / "SadTalker"
sys.path.insert(0, str(SADTALKER_DIR))

from src.utils.preprocess import CropAndExtract
from src.test_audio2coeff import Audio2Coeff  
from src.facerender.animate import AnimateFromCoeff
from src.generate_batch import get_data
from src.generate_facerender_batch import get_facerender_data
from src.utils.init_path import init_path

logger = logging.getLogger(__name__)


class SadTalkerModel:
    """
    SadTalker wrapper for audio-driven talking head generation
    Supports MPS (Apple Silicon) and CUDA acceleration
    """
    
    def __init__(self):
        self.device = "cpu"  # Will be set externally
        self.preprocess_model = None
        self.audio_to_coeff = None
        self.animate_from_coeff = None
        self.sadtalker_paths = None
        self._ready = False
        
    def initialize(self):
        """Initialize SadTalker models with GPU acceleration"""
        start_time = time.time()
        
        try:
            # Setup paths
            checkpoint_dir = str(SADTALKER_DIR / "checkpoints")
            config_dir = str(SADTALKER_DIR / "src" / "config")
            
            # Initialize model paths
            self.sadtalker_paths = init_path(
                checkpoint_dir=checkpoint_dir,
                config_dir=config_dir,
                size=256,  # Use 256x256 for faster inference
                old_version=False,
                preprocess='crop'
            )
            
            # PyTorch 2.4+ supports Conv3D on MPS - full GPU acceleration available
            # Note: Requires PyTorch >= 2.4.0 for MPS Conv3D support
            device = self.device
            
            logger.info(f"Initializing SadTalker on device: {device}")
            
            # Initialize preprocessing (face detection, 3DMM extraction)
            logger.info("Loading preprocessing model...")
            self.preprocess_model = CropAndExtract(self.sadtalker_paths, device)
            
            # Initialize audio to 3D coefficients model
            logger.info("Loading audio-to-coefficients model...")
            self.audio_to_coeff = Audio2Coeff(self.sadtalker_paths, device)
            
            # Initialize face rendering model
            logger.info("Loading face animation model...")
            self.animate_from_coeff = AnimateFromCoeff(self.sadtalker_paths, device)
            
            elapsed = time.time() - start_time
            logger.info(f"✅ SadTalker initialized successfully in {elapsed:.2f}s")
            self._ready = True
            
        except Exception as e:
            logger.error(f"Failed to initialize SadTalker: {e}", exc_info=True)
            raise
    
    def is_ready(self) -> bool:
        """Check if model is initialized and ready"""
        return self._ready
    
    def generate_video(
        self,
        audio_path: str,
        reference_image_path: str,
        output_path: str,
        pose_style: int = 0,
        expression_scale: float = 1.0,
        still_mode: bool = False,
        enhancer: str = None
    ) -> tuple[str, float]:
        """
        Generate talking head video from audio and reference image
        
        Args:
            audio_path: Path to input audio file (WAV)
            reference_image_path: Path to reference face image
            output_path: Path for output video
            pose_style: Head pose style (0-45)
            expression_scale: Expression intensity multiplier
            still_mode: If True, minimize head movement
            enhancer: Optional face enhancer ('gfpgan' or None)
            
        Returns:
            Tuple of (output_video_path, generation_time_ms)
        """
        if not self._ready:
            raise RuntimeError("SadTalker model not initialized")
        
        start_time = time.time()
        
        try:
            # Create temporary directory for intermediate files
            save_dir = Path(output_path).parent / f"sadtalker_tmp_{int(time.time())}"
            save_dir.mkdir(exist_ok=True, parents=True)
            
            # Step 1: Extract 3DMM from source image
            logger.info("Extracting 3DMM from source image...")
            first_frame_dir = save_dir / "first_frame_dir"
            first_frame_dir.mkdir(exist_ok=True)
            
            first_coeff_path, crop_pic_path, crop_info = self.preprocess_model.generate(
                reference_image_path,
                str(first_frame_dir),
                crop_or_resize='crop',
                source_image_flag=True,
                pic_size=256
            )
            
            if first_coeff_path is None:
                raise RuntimeError("Failed to extract face coefficients from image")
            
            # Step 2: Generate coefficients from audio
            logger.info("Generating motion coefficients from audio...")
            batch = get_data(
                first_coeff_path,
                audio_path,
                self.device,
                ref_eyeblink_coeff_path=None,
                still=still_mode
            )
            
            coeff_path = self.audio_to_coeff.generate(
                batch,
                str(save_dir),
                pose_style,
                ref_pose_coeff_path=None
            )
            
            # Step 3: Render final video
            logger.info("Rendering animated video...")
            data = get_facerender_data(
                coeff_path,
                crop_pic_path,
                first_coeff_path,
                audio_path,
                batch_size=2,
                input_yaw_list=None,
                input_pitch_list=None,
                input_roll_list=None,
                expression_scale=expression_scale,
                still_mode=still_mode,
                preprocess='crop',
                size=256
            )
            
            result_path = self.animate_from_coeff.generate(
                data,
                str(save_dir),
                reference_image_path,
                crop_info,
                enhancer=enhancer,
                background_enhancer=None,
                preprocess='crop',
                img_size=256
            )
            
            # Move result to desired output path
            import shutil
            final_output = str(output_path)
            shutil.move(result_path, final_output)
            
            # Clean up temporary directory
            shutil.rmtree(save_dir)
            
            generation_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info(f"✅ Video generated in {generation_time:.0f}ms")
            
            return final_output, generation_time
            
        except Exception as e:
            logger.error(f"Video generation failed: {e}", exc_info=True)
            # Clean up on error
            if 'save_dir' in locals() and save_dir.exists():
                import shutil
                shutil.rmtree(save_dir, ignore_errors=True)
            raise
