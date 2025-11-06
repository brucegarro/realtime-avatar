"""
Audio processing utilities
"""
import logging
import os
from typing import Tuple
import numpy as np

logger = logging.getLogger(__name__)


def load_audio(file_path: str) -> Tuple[np.ndarray, int]:
    """
    Load audio file.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Tuple of (audio_data, sample_rate)
    """
    import soundfile as sf
    
    try:
        audio, sr = sf.read(file_path)
        return audio, sr
    except Exception as e:
        logger.error(f"Failed to load audio {file_path}: {e}")
        raise


def save_audio(audio: np.ndarray, sample_rate: int, file_path: str):
    """
    Save audio to file.
    
    Args:
        audio: Audio data
        sample_rate: Sample rate
        file_path: Output file path
    """
    import soundfile as sf
    
    try:
        sf.write(file_path, audio, sample_rate)
        logger.debug(f"Audio saved: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save audio: {e}")
        raise


def get_audio_duration(file_path: str) -> float:
    """
    Get audio file duration in seconds.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Duration in seconds
    """
    audio, sr = load_audio(file_path)
    return len(audio) / sr


def resample_audio(
    audio: np.ndarray,
    orig_sr: int,
    target_sr: int
) -> np.ndarray:
    """
    Resample audio to target sample rate.
    
    Args:
        audio: Audio data
        orig_sr: Original sample rate
        target_sr: Target sample rate
        
    Returns:
        Resampled audio
    """
    import librosa
    
    if orig_sr == target_sr:
        return audio
    
    try:
        resampled = librosa.resample(
            audio,
            orig_sr=orig_sr,
            target_sr=target_sr
        )
        return resampled
    except Exception as e:
        logger.error(f"Failed to resample audio: {e}")
        raise


def normalize_audio(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """
    Normalize audio to target dB level.
    
    Args:
        audio: Audio data
        target_db: Target level in dB
        
    Returns:
        Normalized audio
    """
    import librosa
    
    try:
        # Calculate current RMS
        rms = np.sqrt(np.mean(audio ** 2))
        
        if rms == 0:
            return audio
        
        # Calculate target RMS from dB
        target_rms = 10 ** (target_db / 20)
        
        # Normalize
        normalized = audio * (target_rms / rms)
        
        # Clip to prevent distortion
        normalized = np.clip(normalized, -1.0, 1.0)
        
        return normalized
    except Exception as e:
        logger.error(f"Failed to normalize audio: {e}")
        raise


def trim_silence(
    audio: np.ndarray,
    sr: int,
    top_db: float = 30.0
) -> np.ndarray:
    """
    Trim silence from beginning and end of audio.
    
    Args:
        audio: Audio data
        sr: Sample rate
        top_db: Threshold in dB below max
        
    Returns:
        Trimmed audio
    """
    import librosa
    
    try:
        trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
        return trimmed
    except Exception as e:
        logger.error(f"Failed to trim silence: {e}")
        raise


def extract_audio_from_video(video_path: str, output_path: str) -> str:
    """
    Extract audio track from video file.
    
    Args:
        video_path: Path to video file
        output_path: Output audio file path
        
    Returns:
        Path to extracted audio
    """
    import subprocess
    
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM 16-bit
            '-ar', '22050',  # Sample rate
            '-ac', '1',  # Mono
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        logger.debug(f"Audio extracted: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to extract audio: {e}")
        raise


def combine_audio_files(
    audio_files: list,
    output_path: str,
    crossfade_duration: float = 0.1
) -> str:
    """
    Combine multiple audio files with crossfade.
    
    Args:
        audio_files: List of audio file paths
        output_path: Output file path
        crossfade_duration: Crossfade duration in seconds
        
    Returns:
        Path to combined audio
    """
    from pydub import AudioSegment
    
    try:
        if not audio_files:
            raise ValueError("No audio files provided")
        
        # Load first audio
        combined = AudioSegment.from_file(audio_files[0])
        
        # Crossfade subsequent files
        for audio_file in audio_files[1:]:
            next_audio = AudioSegment.from_file(audio_file)
            combined = combined.append(
                next_audio,
                crossfade=int(crossfade_duration * 1000)
            )
        
        # Export
        combined.export(output_path, format="wav")
        logger.debug(f"Audio files combined: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to combine audio: {e}")
        raise
