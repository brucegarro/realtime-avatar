"""
Lip sync coherence metric (basic heuristic)
"""
import logging
from typing import Dict
import numpy as np

logger = logging.getLogger(__name__)


def calculate_lip_sync_metrics(video_path: str, audio_path: str) -> Dict:
    """
    Calculate basic lip sync coherence.
    
    This is a simplified heuristic for Phase 1:
    - Checks if video and audio durations match
    - Future: Could analyze mouth movement vs audio amplitude
    
    Args:
        video_path: Path to generated video
        audio_path: Path to audio file
        
    Returns:
        Dictionary of lip sync metrics
    """
    try:
        import soundfile as sf
        import cv2
        
        # Get audio duration
        audio_data, sample_rate = sf.read(audio_path)
        audio_duration = len(audio_data) / sample_rate
        
        # Get video duration
        video = cv2.VideoCapture(video_path)
        fps = video.get(cv2.CAP_PROP_FPS)
        frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
        video_duration = frame_count / fps if fps > 0 else 0
        video.release()
        
        # Calculate duration match (simple coherence metric)
        duration_diff = abs(audio_duration - video_duration)
        
        # Score: 1.0 if durations match within 0.1s, decreases linearly
        coherence = max(0.0, 1.0 - (duration_diff / audio_duration))
        
        return {
            'lip_sync_coherence_0_1': float(coherence),
            'audio_duration_s': float(audio_duration),
            'video_duration_s': float(video_duration),
            'duration_diff_s': float(duration_diff)
        }
        
    except Exception as e:
        logger.error(f"Lip sync metrics calculation failed: {e}")
        return {
            'lip_sync_coherence_0_1': 0.0,
            'audio_duration_s': 0.0,
            'video_duration_s': 0.0,
            'duration_diff_s': 0.0
        }
