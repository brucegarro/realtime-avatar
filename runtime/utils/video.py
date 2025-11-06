"""
Video processing utilities
"""
import logging
import os
from typing import Tuple, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def get_video_info(video_path: str) -> dict:
    """
    Get video file information.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video info
    """
    try:
        video = cv2.VideoCapture(video_path)
        
        info = {
            'fps': video.get(cv2.CAP_PROP_FPS),
            'frame_count': int(video.get(cv2.CAP_PROP_FRAME_COUNT)),
            'width': int(video.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'duration': video.get(cv2.CAP_PROP_FRAME_COUNT) / video.get(cv2.CAP_PROP_FPS)
        }
        
        video.release()
        return info
        
    except Exception as e:
        logger.error(f"Failed to get video info: {e}")
        raise


def extract_frame(
    video_path: str,
    frame_number: int = 0,
    output_path: Optional[str] = None
) -> np.ndarray:
    """
    Extract a single frame from video.
    
    Args:
        video_path: Path to video file
        frame_number: Frame index to extract
        output_path: Optional path to save frame
        
    Returns:
        Frame as numpy array
    """
    try:
        video = cv2.VideoCapture(video_path)
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = video.read()
        video.release()
        
        if not ret:
            raise ValueError(f"Failed to read frame {frame_number}")
        
        if output_path:
            cv2.imwrite(output_path, frame)
            logger.debug(f"Frame saved: {output_path}")
        
        return frame
        
    except Exception as e:
        logger.error(f"Failed to extract frame: {e}")
        raise


def resize_frame(
    frame: np.ndarray,
    target_size: Tuple[int, int],
    interpolation=cv2.INTER_LINEAR
) -> np.ndarray:
    """
    Resize video frame.
    
    Args:
        frame: Input frame
        target_size: (width, height)
        interpolation: OpenCV interpolation method
        
    Returns:
        Resized frame
    """
    try:
        return cv2.resize(frame, target_size, interpolation=interpolation)
    except Exception as e:
        logger.error(f"Failed to resize frame: {e}")
        raise


def combine_audio_video(
    video_path: str,
    audio_path: str,
    output_path: str,
    video_codec: str = "libx264",
    audio_codec: str = "aac"
) -> str:
    """
    Combine video and audio into single file.
    
    Args:
        video_path: Path to video file
        audio_path: Path to audio file
        output_path: Output file path
        video_codec: Video codec
        audio_codec: Audio codec
        
    Returns:
        Path to output file
    """
    import subprocess
    
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-i', video_path,
            '-i', audio_path,
            '-c:v', video_codec,
            '-c:a', audio_codec,
            '-strict', 'experimental',
            '-shortest',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        logger.debug(f"Audio/video combined: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to combine audio/video: {e}")
        raise


def create_video_from_frames(
    frames: list,
    output_path: str,
    fps: int = 30,
    codec: str = "mp4v"
) -> str:
    """
    Create video from list of frames.
    
    Args:
        frames: List of numpy arrays (frames)
        output_path: Output video path
        fps: Frames per second
        codec: Video codec fourcc
        
    Returns:
        Path to output video
    """
    try:
        if not frames:
            raise ValueError("No frames provided")
        
        height, width = frames[0].shape[:2]
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # Write frames
        for frame in frames:
            writer.write(frame)
        
        writer.release()
        logger.debug(f"Video created from frames: {output_path}")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to create video from frames: {e}")
        raise


def loop_video(
    video_path: str,
    duration: float,
    output_path: str
) -> str:
    """
    Loop video to match target duration.
    
    Args:
        video_path: Input video path
        duration: Target duration in seconds
        output_path: Output video path
        
    Returns:
        Path to output video
    """
    import subprocess
    
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-stream_loop', '-1',  # Infinite loop
            '-i', video_path,
            '-t', str(duration),  # Duration
            '-c', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        logger.debug(f"Video looped: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to loop video: {e}")
        raise


def add_subtitles(
    video_path: str,
    subtitles: list,
    output_path: str,
    font_size: int = 24,
    font_color: str = "white"
) -> str:
    """
    Add subtitles to video.
    
    Args:
        video_path: Input video path
        subtitles: List of (start_time, end_time, text) tuples
        output_path: Output video path
        font_size: Font size
        font_color: Font color
        
    Returns:
        Path to output video
    """
    # TODO: Implement subtitle overlay using ffmpeg or OpenCV
    logger.warning("Subtitle overlay not yet implemented")
    return video_path


def convert_video_format(
    input_path: str,
    output_path: str,
    target_format: str = "mp4",
    video_codec: str = "libx264",
    crf: int = 23
) -> str:
    """
    Convert video to different format.
    
    Args:
        input_path: Input video path
        output_path: Output video path
        target_format: Target format
        video_codec: Video codec
        crf: Constant rate factor (quality)
        
    Returns:
        Path to output video
    """
    import subprocess
    
    try:
        cmd = [
            'ffmpeg',
            '-y',
            '-i', input_path,
            '-c:v', video_codec,
            '-crf', str(crf),
            '-preset', 'medium',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        logger.debug(f"Video converted: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to convert video: {e}")
        raise
