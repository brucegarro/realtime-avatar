"""
Latency metrics calculation
"""
from typing import Dict


def calculate_latency_metrics(result: Dict) -> Dict:
    """
    Calculate latency metrics from generation result.
    
    Args:
        result: Generation result from runtime API
        
    Returns:
        Dictionary of latency metrics
    """
    metadata = result.get('metadata', {})
    
    return {
        'tts_ms': metadata.get('tts_ms', 0),
        'avatar_render_ms': metadata.get('avatar_ms', 0),
        'total_generation_ms': metadata.get('duration_ms', 0),
        'audio_duration_s': metadata.get('audio_duration_s', 0)
    }
