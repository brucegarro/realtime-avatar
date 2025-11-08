"""
Configuration management for runtime service.
Supports local (CPU/MPS), and production (GPU) modes.
"""
from pydantic_settings import BaseSettings
from typing import Literal
import os
import torch


def auto_detect_device() -> str:
    """Auto-detect best available device (MPS for M1/M2/M3, CUDA for NVIDIA, CPU fallback)"""
    if torch.backends.mps.is_available():
        return "mps"  # Apple Silicon GPU
    elif torch.cuda.is_available():
        return "cuda"  # NVIDIA GPU
    else:
        return "cpu"


class Settings(BaseSettings):
    """Application settings"""
    
    # Execution mode
    mode: Literal["local", "production"] = "local"
    device: Literal["cpu", "cuda", "mps"] = auto_detect_device()
    
    # Server config
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    
    # Asset paths
    assets_dir: str = "/app/assets"
    images_dir: str = "/app/assets/images"
    videos_dir: str = "/app/assets/videos"
    voice_samples_dir: str = "/app/assets/voice/reference_samples"
    
    # Model cache paths
    model_cache_dir: str = "/root/.cache"
    xtts_model_path: str = "/root/.cache/tts_models"
    liveportrait_model_path: str = "/root/.cache/liveportrait"
    
    # Model settings
    xtts_language: Literal["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko"] = "en"
    default_reference_image: str = "bruce_neutral.jpg"
    
    # GPU Service settings (for hybrid deployment)
    gpu_service_url: str = os.getenv("GPU_SERVICE_URL", "http://host.docker.internal:8001")
    use_external_gpu_service: bool = os.getenv("USE_EXTERNAL_GPU_SERVICE", "true").lower() == "true"
    
    # Performance settings (adjust based on mode)
    @property
    def video_resolution(self) -> tuple[int, int]:
        """Target video resolution (width, height)"""
        if self.mode == "local":
            return (256, 256)  # Lower for CPU
        return (360, 360)  # Higher for GPU
    
    @property
    def video_fps(self) -> int:
        """Target frames per second"""
        if self.mode == "local":
            return 25
        return 30
    
    @property
    def max_audio_duration(self) -> int:
        """Maximum audio duration in seconds"""
        return 30
    
    # Output settings
    output_dir: str = "/tmp/realtime-avatar-output"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra env variables


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance"""
    return settings


def is_local() -> bool:
    """Check if running in local mode"""
    return settings.mode == "local"


def is_gpu_available() -> bool:
    """Check if GPU (CUDA or MPS) is available"""
    return settings.device in ("cuda", "mps")
