"""
TTS accuracy metrics - transcribe generated audio and compare to expected text.
Uses Word Error Rate (WER) and Character Error Rate (CER).
"""
import logging
import os
import subprocess
import tempfile
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def extract_audio_from_video(video_path: str, output_path: Optional[str] = None) -> str:
    """Extract audio track from video file"""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')
    
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-ac', '1', '-ar', '16000',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")
    
    return output_path


def transcribe_audio(audio_path: str, language: str = "en") -> str:
    """
    Transcribe audio using faster-whisper.
    Runs locally for eval purposes.
    """
    try:
        from faster_whisper import WhisperModel
        
        # Use base model for eval (balance of speed/accuracy)
        model = WhisperModel("base", device="cpu", compute_type="int8")
        
        segments, info = model.transcribe(
            audio_path,
            language=language if language != "zh-cn" else "zh",
            beam_size=5
        )
        
        text = " ".join([seg.text for seg in segments]).strip()
        return text
        
    except ImportError:
        logger.error("faster-whisper not installed. Install with: pip install faster-whisper")
        return ""


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate between reference and hypothesis.
    WER = (S + D + I) / N where:
    - S = substitutions, D = deletions, I = insertions
    - N = number of words in reference
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    
    if not ref_words:
        return 1.0 if hyp_words else 0.0
    
    # Dynamic programming for edit distance
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(
                    d[i-1][j] + 1,    # deletion
                    d[i][j-1] + 1,    # insertion
                    d[i-1][j-1] + 1   # substitution
                )
    
    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    Calculate Character Error Rate between reference and hypothesis.
    Better for CJK languages where word boundaries are ambiguous.
    """
    ref_chars = list(reference.lower().replace(" ", ""))
    hyp_chars = list(hypothesis.lower().replace(" ", ""))
    
    if not ref_chars:
        return 1.0 if hyp_chars else 0.0
    
    # Dynamic programming for edit distance
    d = [[0] * (len(hyp_chars) + 1) for _ in range(len(ref_chars) + 1)]
    
    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i-1] == hyp_chars[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(
                    d[i-1][j] + 1,
                    d[i][j-1] + 1,
                    d[i-1][j-1] + 1
                )
    
    return d[len(ref_chars)][len(hyp_chars)] / len(ref_chars)


def calculate_tts_accuracy(
    video_path: str,
    expected_text: str,
    language: str = "en"
) -> Dict[str, float]:
    """
    Calculate TTS accuracy by transcribing generated audio and comparing to expected text.
    
    Args:
        video_path: Path to generated video file
        expected_text: The text that was supposed to be spoken (LLM response)
        language: Language code for transcription
        
    Returns:
        Dict with WER, CER, and transcribed text
    """
    try:
        # Extract audio from video
        audio_path = extract_audio_from_video(video_path)
        
        # Transcribe the audio
        transcribed = transcribe_audio(audio_path, language)
        
        # Clean up
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        # Calculate error rates
        wer = calculate_wer(expected_text, transcribed)
        cer = calculate_cer(expected_text, transcribed)
        
        return {
            "wer": wer,
            "cer": cer,
            "expected_text": expected_text,
            "transcribed_text": transcribed,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"TTS accuracy calculation failed: {e}")
        return {
            "wer": 1.0,
            "cer": 1.0,
            "error": str(e)
        }
