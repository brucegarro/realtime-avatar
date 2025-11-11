"""
Workers module for concurrent video generation.

Provides multi-threaded video generation with shared models
and per-worker Ditto instances for GPU parallelism.
"""

from .concurrent_generator import (
    ConcurrentVideoGenerator,
    VideoJob,
    JobResult
)

__all__ = [
    "ConcurrentVideoGenerator",
    "VideoJob", 
    "JobResult"
]
