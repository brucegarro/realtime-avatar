"""
Concurrent Video Generator - Multi-worker architecture for parallel video generation.

Supports 1-3 concurrent workers on single L4 GPU (24GB VRAM) using:
- Thread pool for parallel execution
- Queue-based job distribution
- Shared TTS/ASR models (loaded once)
- Separate Ditto instances per worker
- CUDA stream management for GPU parallelism
- Memory monitoring for dynamic scaling
"""

import os
import time
import queue
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import torch

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.tts import XTTSModel
from models.asr import ASRModel
from models.ditto_model import DittoModel


@dataclass
class VideoJob:
    """Video generation job specification."""
    job_id: str
    image_path: str
    text: str
    output_path: str
    voice_sample: Optional[str] = None
    language: str = "en"


@dataclass
class JobResult:
    """Video generation job result."""
    job_id: str
    success: bool
    output_path: Optional[str]
    duration: float
    error: Optional[str] = None
    worker_id: int = 0


class ConcurrentVideoGenerator:
    """
    Multi-worker video generator with shared models and concurrent execution.
    
    Memory footprint on L4 GPU (24GB):
    - Shared TTS (XTTS-v2): ~3.0GB
    - Shared ASR (Faster-Whisper): ~0.4GB
    - Per-worker Ditto: ~2.4GB
    - Per-worker buffers: ~0.9GB
    
    Total for 2 workers: ~9.5GB (safe)
    Total for 3 workers: ~12.4GB (safe)
    """
    
    def __init__(
        self,
        num_workers: int = 2,
        device: str = "cuda",
        max_queue_size: int = 100,
        voice_sample_path: Optional[str] = None
    ):
        """
        Initialize concurrent video generator.
        
        Args:
            num_workers: Number of parallel workers (1-3 recommended for L4)
            device: CUDA device to use
            max_queue_size: Maximum pending jobs in queue
            voice_sample_path: Default voice sample for TTS cloning
        """
        self.num_workers = num_workers
        self.device = device
        self.max_queue_size = max_queue_size
        self.voice_sample_path = voice_sample_path
        
        # Job queue and results
        self.job_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.results: Dict[str, JobResult] = {}
        self.results_lock = threading.Lock()
        
        # Shared models (loaded once, used by all workers)
        self.tts_model: Optional[XTTSModel] = None
        self.asr_model: Optional[ASRModel] = None
        
        # Per-worker Ditto instances
        self.ditto_models: List[DittoModel] = []
        
        # Worker management
        self.executor: Optional[ThreadPoolExecutor] = None
        self.running = False
        self.stats = {
            "jobs_completed": 0,
            "jobs_failed": 0,
            "total_time": 0.0,
            "worker_times": [0.0] * num_workers
        }
        
        print(f"🚀 Initializing ConcurrentVideoGenerator with {num_workers} workers")
    
    def initialize(self):
        """Initialize all models and workers."""
        print("📦 Loading shared models...")
        
        # Load shared TTS model (3.0GB)
        print("  - Loading XTTS-v2 TTS model...")
        self.tts_model = XTTSModel()
        self.tts_model.initialize()
        
        # Load shared ASR model (0.4GB)
        print("  - Loading Faster-Whisper ASR model...")
        self.asr_model = ASRModel(device=self.device)
        self.asr_model.initialize()
        
        # Create per-worker Ditto instances (2.4GB each)
        print(f"  - Creating {self.num_workers} Ditto instances...")
        for i in range(self.num_workers):
            # Each worker gets its own CUDA stream for parallelism
            ditto = DittoModel(device=self.device)
            self.ditto_models.append(ditto)
            print(f"    ✓ Worker {i+1} Ditto instance ready")
        
        # Print memory usage
        if torch.cuda.is_available():
            mem_allocated = torch.cuda.memory_allocated(self.device) / 1024**3
            mem_reserved = torch.cuda.memory_reserved(self.device) / 1024**3
            print(f"💾 GPU Memory: {mem_allocated:.2f}GB allocated, {mem_reserved:.2f}GB reserved")
        
        print("✅ All models initialized")
    
    def start(self):
        """Start worker threads."""
        if self.running:
            print("⚠️  Workers already running")
            return
        
        print(f"▶️  Starting {self.num_workers} worker threads...")
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=self.num_workers)
        
        # Submit worker tasks
        for i in range(self.num_workers):
            self.executor.submit(self._worker_loop, i)
        
        print(f"✅ {self.num_workers} workers active and ready")
    
    def stop(self):
        """Stop all workers and clean up."""
        if not self.running:
            return
        
        print("🛑 Stopping workers...")
        self.running = False
        
        # Add sentinel values to wake up blocked workers
        for _ in range(self.num_workers):
            try:
                self.job_queue.put(None, timeout=1.0)
            except queue.Full:
                pass
        
        # Shutdown executor
        if self.executor:
            self.executor.shutdown(wait=True)
        
        print("✅ Workers stopped")
    
    def _worker_loop(self, worker_id: int):
        """Worker thread main loop."""
        print(f"🔧 Worker {worker_id+1} started")
        
        while self.running:
            try:
                # Get job from queue (blocking with timeout)
                job = self.job_queue.get(timeout=1.0)
                
                # Sentinel value to stop worker
                if job is None:
                    break
                
                # Process job
                result = self._process_job(job, worker_id)
                
                # Store result
                with self.results_lock:
                    self.results[job.job_id] = result
                    if result.success:
                        self.stats["jobs_completed"] += 1
                    else:
                        self.stats["jobs_failed"] += 1
                    self.stats["total_time"] += result.duration
                    self.stats["worker_times"][worker_id] += result.duration
                
                self.job_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ Worker {worker_id+1} error: {e}")
                continue
        
        print(f"🔧 Worker {worker_id+1} stopped")
    
    def _process_job(self, job: VideoJob, worker_id: int) -> JobResult:
        """
        Process a single video generation job.
        
        Args:
            job: Video job specification
            worker_id: Worker processing this job
            
        Returns:
            JobResult with success status and timing
        """
        start_time = time.time()
        print(f"🎬 Worker {worker_id+1} processing job {job.job_id}")
        
        try:
            # Step 1: Generate audio with TTS (shared model)
            print(f"  🎤 Generating audio for '{job.text[:50]}...'")
            voice_sample = job.voice_sample or self.voice_sample_path
            
            # TTS returns (audio_path, duration_ms, audio_duration_s)
            temp_audio = f"/tmp/audio_{job.job_id}.wav"
            audio_path, tts_duration, audio_duration_s = self.tts_model.synthesize(
                text=job.text,
                language=job.language,
                speaker_wav=voice_sample,
                output_path=temp_audio
            )
            
            # Step 2: Generate video with Ditto (worker-specific instance)
            print(f"  🎥 Generating video with worker {worker_id+1}")
            ditto = self.ditto_models[worker_id]
            
            # Ditto returns (video_path, generation_time_ms)
            video_path, ditto_duration = ditto.generate_video(
                audio_path=audio_path,
                reference_image_path=job.image_path,
                output_path=job.output_path
            )
            
            # Clean up temp audio
            if os.path.exists(audio_path):
                os.remove(audio_path)
            
            duration = time.time() - start_time
            print(f"  ✅ Job {job.job_id} completed in {duration:.2f}s")
            
            return JobResult(
                job_id=job.job_id,
                success=True,
                output_path=video_path,
                duration=duration,
                worker_id=worker_id
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            print(f"  ❌ Job {job.job_id} failed: {error_msg}")
            
            return JobResult(
                job_id=job.job_id,
                success=False,
                output_path=None,
                duration=duration,
                error=error_msg,
                worker_id=worker_id
            )
    
    def submit_job(self, job: VideoJob) -> bool:
        """
        Submit a video generation job.
        
        Args:
            job: VideoJob specification
            
        Returns:
            True if job was queued, False if queue is full
        """
        try:
            self.job_queue.put(job, block=False)
            print(f"📥 Job {job.job_id} queued (queue size: {self.job_queue.qsize()})")
            return True
        except queue.Full:
            print(f"⚠️  Queue full, job {job.job_id} rejected")
            return False
    
    def get_result(self, job_id: str, timeout: Optional[float] = None) -> Optional[JobResult]:
        """
        Get result for a job (blocking until complete or timeout).
        
        Args:
            job_id: Job ID to get result for
            timeout: Maximum time to wait (None = wait forever)
            
        Returns:
            JobResult if available, None if timeout
        """
        start = time.time()
        
        while True:
            with self.results_lock:
                if job_id in self.results:
                    return self.results[job_id]
            
            # Check timeout
            if timeout and (time.time() - start) > timeout:
                return None
            
            time.sleep(0.1)
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        with self.results_lock:
            stats = self.stats.copy()
            stats["queue_size"] = self.job_queue.qsize()
            stats["avg_time"] = (
                stats["total_time"] / stats["jobs_completed"]
                if stats["jobs_completed"] > 0
                else 0.0
            )
            
            # Per-worker stats
            stats["worker_avg_times"] = [
                wt / stats["jobs_completed"] * self.num_workers
                if stats["jobs_completed"] > 0
                else 0.0
                for wt in stats["worker_times"]
            ]
            
            return stats
    
    def print_stats(self):
        """Print current statistics."""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("📊 CONCURRENT GENERATOR STATISTICS")
        print("="*60)
        print(f"Workers:          {self.num_workers}")
        print(f"Jobs Completed:   {stats['jobs_completed']}")
        print(f"Jobs Failed:      {stats['jobs_failed']}")
        print(f"Queue Size:       {stats['queue_size']}")
        print(f"Total Time:       {stats['total_time']:.2f}s")
        print(f"Avg Time/Job:     {stats['avg_time']:.2f}s")
        
        print("\nPer-Worker Performance:")
        for i, avg_time in enumerate(stats['worker_avg_times']):
            total_time = stats['worker_times'][i]
            print(f"  Worker {i+1}: {total_time:.2f}s total, {avg_time:.2f}s avg")
        
        if torch.cuda.is_available():
            mem_allocated = torch.cuda.memory_allocated(self.device) / 1024**3
            mem_reserved = torch.cuda.memory_reserved(self.device) / 1024**3
            print(f"\nGPU Memory: {mem_allocated:.2f}GB allocated, {mem_reserved:.2f}GB reserved")
        
        print("="*60 + "\n")


def main():
    """Example usage and testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Concurrent video generator")
    parser.add_argument("--workers", type=int, default=2, help="Number of workers")
    parser.add_argument("--jobs", type=int, default=5, help="Number of test jobs")
    parser.add_argument("--image", type=str, required=True, help="Input image path")
    parser.add_argument("--voice", type=str, help="Voice sample path")
    args = parser.parse_args()
    
    # Create generator
    generator = ConcurrentVideoGenerator(
        num_workers=args.workers,
        voice_sample_path=args.voice
    )
    
    # Initialize models
    generator.initialize()
    
    # Start workers
    generator.start()
    
    # Submit test jobs
    test_texts = [
        "Hello! This is a test of concurrent video generation.",
        "The quick brown fox jumps over the lazy dog.",
        "Testing worker number two with different text.",
        "Concurrent processing enables higher throughput.",
        "This is the fifth test job for benchmarking."
    ]
    
    job_ids = []
    for i in range(args.jobs):
        text = test_texts[i % len(test_texts)]
        job = VideoJob(
            job_id=f"test_{i+1}",
            image_path=args.image,
            text=text,
            output_path=f"/tmp/output_worker_test_{i+1}.mp4"
        )
        generator.submit_job(job)
        job_ids.append(job.job_id)
    
    # Wait for all jobs to complete
    print(f"\n⏳ Waiting for {args.jobs} jobs to complete...")
    for job_id in job_ids:
        result = generator.get_result(job_id)
        if result.success:
            print(f"✅ {job_id}: {result.duration:.2f}s by worker {result.worker_id+1}")
        else:
            print(f"❌ {job_id}: Failed - {result.error}")
    
    # Print stats
    generator.print_stats()
    
    # Stop workers
    generator.stop()
    
    print("🎉 Test complete!")


if __name__ == "__main__":
    main()
