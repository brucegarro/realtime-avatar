"""
Voice quality metrics: speaker similarity and pitch analysis
"""
import logging
from typing import Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


def calculate_voice_metrics(
    output_audio_path: str,
    reference_audio_path: Optional[str] = None
) -> Dict:
    """
    Calculate voice quality metrics.
    
    Args:
        output_audio_path: Path to generated audio
        reference_audio_path: Path to reference audio (for similarity)
        
    Returns:
        Dictionary of voice quality metrics
    """
    metrics = {}
    
    try:
        import soundfile as sf
        import librosa
        
        # Load output audio
        audio, sr = sf.read(output_audio_path)
        
        # Calculate F0 (pitch) statistics
        try:
            f0, voiced_flag, _ = librosa.pyin(
                audio.astype(np.float32),
                fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7'),
                sr=sr
            )
            
            # Remove NaN values
            f0_valid = f0[~np.isnan(f0)]
            
            if len(f0_valid) > 0:
                metrics['f0_mean_hz'] = float(np.mean(f0_valid))
                metrics['f0_std_hz'] = float(np.std(f0_valid))
                metrics['f0_rmse_hz'] = float(np.sqrt(np.mean(f0_valid ** 2)))
            else:
                metrics['f0_mean_hz'] = 0.0
                metrics['f0_std_hz'] = 0.0
                metrics['f0_rmse_hz'] = 0.0
        except Exception as e:
            logger.warning(f"F0 extraction failed: {e}")
            metrics['f0_mean_hz'] = 0.0
            metrics['f0_std_hz'] = 0.0
            metrics['f0_rmse_hz'] = 0.0
        
        # Calculate speaker similarity if reference provided
        if reference_audio_path:
            try:
                from resemblyzer import VoiceEncoder, preprocess_wav
                
                encoder = VoiceEncoder()
                
                # Load and preprocess both audio files
                ref_wav = preprocess_wav(reference_audio_path)
                out_wav = preprocess_wav(output_audio_path)
                
                # Get embeddings
                ref_embed = encoder.embed_utterance(ref_wav)
                out_embed = encoder.embed_utterance(out_wav)
                
                # Calculate cosine similarity
                similarity = np.dot(ref_embed, out_embed) / (
                    np.linalg.norm(ref_embed) * np.linalg.norm(out_embed)
                )
                
                metrics['speaker_similarity'] = float(similarity)
                
            except Exception as e:
                logger.warning(f"Speaker similarity calculation failed: {e}")
                metrics['speaker_similarity'] = 0.0
        else:
            metrics['speaker_similarity'] = 0.0
        
    except Exception as e:
        logger.error(f"Voice metrics calculation failed: {e}")
        metrics = {
            'speaker_similarity': 0.0,
            'f0_mean_hz': 0.0,
            'f0_std_hz': 0.0,
            'f0_rmse_hz': 0.0
        }
    
    return metrics
