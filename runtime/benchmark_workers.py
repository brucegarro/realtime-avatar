"""
Benchmark script for concurrent video generation.

Tests 1, 2, and 3 workers to measure:
- Throughput (videos per second)
- GPU utilization
- Memory usage
- Average generation time
"""

import os
import sys
import time
import json
from typing import List, Dict
import torch

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from workers.concurrent_generator import ConcurrentVideoGenerator, VideoJob


def measure_gpu_memory() -> Dict[str, float]:
    """Measure current GPU memory usage."""
    if not torch.cuda.is_available():
        return {"allocated_gb": 0.0, "reserved_gb": 0.0}
    
    allocated = torch.cuda.memory_allocated(0) / 1024**3
    reserved = torch.cuda.memory_reserved(0) / 1024**3
    
    return {
        "allocated_gb": round(allocated, 2),
        "reserved_gb": round(reserved, 2)
    }


def run_benchmark(
    num_workers: int,
    num_jobs: int,
    image_path: str,
    voice_sample: str,
    output_dir: str = "/tmp/benchmark"
) -> Dict:
    """
    Run benchmark with specified number of workers.
    
    Args:
        num_workers: Number of concurrent workers
        num_jobs: Number of videos to generate
        image_path: Path to input image
        voice_sample: Path to voice sample
        output_dir: Directory for output videos
        
    Returns:
        Dict with benchmark results
    """
    print(f"\n{'='*80}")
    print(f"🏃 BENCHMARK: {num_workers} Worker{'s' if num_workers > 1 else ''}")
    print(f"{'='*80}\n")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create generator
    generator = ConcurrentVideoGenerator(
        num_workers=num_workers,
        voice_sample_path=voice_sample
    )
    
    # Initialize and measure baseline memory
    print("📦 Initializing models...")
    init_start = time.time()
    generator.initialize()
    init_time = time.time() - init_start
    
    baseline_memory = measure_gpu_memory()
    print(f"💾 Baseline memory: {baseline_memory['allocated_gb']:.2f}GB allocated")
    
    # Start workers
    generator.start()
    
    # Test texts (vary length for realism)
    test_texts = [
        "Hello! This is a short test.",
        "The quick brown fox jumps over the lazy dog while testing concurrent video generation.",
        "Testing worker performance with medium length text for benchmarking.",
        "This is a longer sentence that will take more time to synthesize, allowing us to better measure the concurrent processing capabilities of the system.",
        "Short one.",
        "Another medium length test to ensure we have variety in our benchmark dataset.",
        "The weather is nice today, perfect for testing video generation performance.",
        "We are measuring throughput, latency, and GPU utilization across multiple workers.",
        "Final test with some more text content.",
        "Benchmark complete!"
    ]
    
    # Submit all jobs
    print(f"📥 Submitting {num_jobs} jobs...")
    job_ids = []
    submit_start = time.time()
    
    for i in range(num_jobs):
        text = test_texts[i % len(test_texts)]
        job = VideoJob(
            job_id=f"bench_{num_workers}w_{i+1}",
            image_path=image_path,
            text=text,
            output_path=f"{output_dir}/output_{num_workers}w_{i+1}.mp4"
        )
        generator.submit_job(job)
        job_ids.append(job.job_id)
    
    submit_time = time.time() - submit_start
    
    # Wait for all jobs and track timing
    print(f"⏳ Processing {num_jobs} jobs with {num_workers} worker(s)...")
    process_start = time.time()
    
    results = []
    for job_id in job_ids:
        result = generator.get_result(job_id)
        results.append(result)
        
        status = "✅" if result.success else "❌"
        print(f"  {status} {job_id}: {result.duration:.2f}s (worker {result.worker_id+1})")
    
    total_time = time.time() - process_start
    
    # Get final stats
    stats = generator.get_stats()
    peak_memory = measure_gpu_memory()
    
    # Calculate metrics
    successful_jobs = sum(1 for r in results if r.success)
    failed_jobs = len(results) - successful_jobs
    
    throughput = successful_jobs / total_time if total_time > 0 else 0
    avg_job_time = sum(r.duration for r in results if r.success) / successful_jobs if successful_jobs > 0 else 0
    
    # Calculate per-worker utilization
    worker_utilization = []
    for i in range(num_workers):
        worker_time = stats['worker_times'][i]
        utilization = (worker_time / total_time * 100) if total_time > 0 else 0
        worker_utilization.append(round(utilization, 1))
    
    # Stop workers
    generator.stop()
    
    # Compile results
    benchmark_results = {
        "num_workers": num_workers,
        "num_jobs": num_jobs,
        "successful_jobs": successful_jobs,
        "failed_jobs": failed_jobs,
        "init_time_s": round(init_time, 2),
        "submit_time_s": round(submit_time, 2),
        "total_processing_time_s": round(total_time, 2),
        "throughput_videos_per_sec": round(throughput, 3),
        "throughput_videos_per_hour": round(throughput * 3600, 0),
        "avg_job_time_s": round(avg_job_time, 2),
        "worker_utilization_pct": worker_utilization,
        "baseline_memory_gb": baseline_memory['allocated_gb'],
        "peak_memory_gb": peak_memory['allocated_gb'],
        "memory_per_worker_gb": round((peak_memory['allocated_gb'] - baseline_memory['allocated_gb']) / num_workers, 2) if num_workers > 0 else 0,
    }
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"📊 BENCHMARK RESULTS: {num_workers} Worker{'s' if num_workers > 1 else ''}")
    print(f"{'='*80}")
    print(f"Jobs:                    {successful_jobs}/{num_jobs} successful")
    print(f"Total Time:              {total_time:.2f}s")
    print(f"Throughput:              {throughput:.3f} videos/sec ({benchmark_results['throughput_videos_per_hour']:.0f} videos/hour)")
    print(f"Avg Job Time:            {avg_job_time:.2f}s")
    print(f"Init Time:               {init_time:.2f}s")
    print(f"\nMemory Usage:")
    print(f"  Baseline:              {baseline_memory['allocated_gb']:.2f}GB")
    print(f"  Peak:                  {peak_memory['allocated_gb']:.2f}GB")
    print(f"  Per Worker:            {benchmark_results['memory_per_worker_gb']:.2f}GB")
    print(f"\nWorker Utilization:")
    for i, util in enumerate(worker_utilization):
        print(f"  Worker {i+1}:              {util:.1f}%")
    print(f"{'='*80}\n")
    
    return benchmark_results


def compare_results(results: List[Dict]):
    """Compare benchmark results across different worker counts."""
    print(f"\n{'='*80}")
    print("📈 COMPARISON ACROSS WORKER COUNTS")
    print(f"{'='*80}\n")
    
    # Sort by worker count
    results = sorted(results, key=lambda x: x['num_workers'])
    
    # Print comparison table
    print(f"{'Workers':<10} {'Throughput':<20} {'Speedup':<12} {'Avg Time':<12} {'Peak Mem':<12}")
    print(f"{'-'*10} {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
    
    baseline_throughput = results[0]['throughput_videos_per_sec']
    
    for r in results:
        speedup = r['throughput_videos_per_sec'] / baseline_throughput if baseline_throughput > 0 else 0
        print(f"{r['num_workers']:<10} {r['throughput_videos_per_sec']:.3f} vid/s ({r['throughput_videos_per_hour']:.0f}/hr)  {speedup:.2f}x        {r['avg_job_time_s']:.2f}s       {r['peak_memory_gb']:.2f}GB")
    
    print(f"\n{'='*80}\n")
    
    # Recommendations
    print("💡 RECOMMENDATIONS:\n")
    
    # Find best throughput/memory ratio
    best_ratio = max(results, key=lambda x: x['throughput_videos_per_sec'] / x['peak_memory_gb'])
    print(f"Best throughput/memory ratio: {best_ratio['num_workers']} workers")
    print(f"  - {best_ratio['throughput_videos_per_hour']:.0f} videos/hour")
    print(f"  - {best_ratio['peak_memory_gb']:.2f}GB peak memory")
    
    # Find best absolute throughput
    best_throughput = max(results, key=lambda x: x['throughput_videos_per_sec'])
    if best_throughput['num_workers'] != best_ratio['num_workers']:
        print(f"\nHighest throughput: {best_throughput['num_workers']} workers")
        print(f"  - {best_throughput['throughput_videos_per_hour']:.0f} videos/hour")
        print(f"  - {best_throughput['peak_memory_gb']:.2f}GB peak memory")
    
    print()


def main():
    """Run full benchmark suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark concurrent video generation")
    parser.add_argument("--image", type=str, required=True, help="Input image path")
    parser.add_argument("--voice", type=str, required=True, help="Voice sample path")
    parser.add_argument("--jobs", type=int, default=10, help="Number of jobs per test")
    parser.add_argument("--workers", type=str, default="1,2,3", help="Worker counts to test (comma-separated)")
    parser.add_argument("--output", type=str, default="/tmp/benchmark", help="Output directory")
    parser.add_argument("--save-json", type=str, help="Save results to JSON file")
    args = parser.parse_args()
    
    # Parse worker counts
    worker_counts = [int(w.strip()) for w in args.workers.split(",")]
    
    print(f"\n🚀 Starting benchmark suite")
    print(f"   Image: {args.image}")
    print(f"   Voice: {args.voice}")
    print(f"   Jobs per test: {args.jobs}")
    print(f"   Worker counts: {worker_counts}")
    print(f"   Output: {args.output}")
    
    # Run benchmarks
    all_results = []
    
    for num_workers in worker_counts:
        try:
            result = run_benchmark(
                num_workers=num_workers,
                num_jobs=args.jobs,
                image_path=args.image,
                voice_sample=args.voice,
                output_dir=args.output
            )
            all_results.append(result)
            
            # Cool down between tests
            if num_workers != worker_counts[-1]:
                print("\n⏸️  Cooling down for 5 seconds...\n")
                time.sleep(5)
                
        except Exception as e:
            print(f"\n❌ Benchmark failed for {num_workers} workers: {e}\n")
            import traceback
            traceback.print_exc()
    
    # Compare results
    if len(all_results) > 1:
        compare_results(all_results)
    
    # Save results
    if args.save_json:
        with open(args.save_json, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"💾 Results saved to {args.save_json}")
    
    print("🎉 Benchmark suite complete!")


if __name__ == "__main__":
    main()
