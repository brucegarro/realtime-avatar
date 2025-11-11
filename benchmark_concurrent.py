#!/usr/bin/env python3
"""
Concurrent Worker Benchmark - Test 1-8 workers with same workload
"""
import sys
import os
import time
from pathlib import Path

# Add runtime to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/runtime')

# Change to runtime directory for checkpoint resolution
os.chdir('/app/runtime')

print("\n" + "="*70)
print("🚀 CONCURRENT WORKER BENCHMARK")
print("="*70)

from workers.concurrent_generator import ConcurrentVideoGenerator, VideoJob

# Test configuration
TEST_JOBS = [
    {"text": "Testing video generation performance.", "output": "/tmp/concurrent_test_1.mp4"},
    {"text": "Quick brown fox jumps over lazy dog.", "output": "/tmp/concurrent_test_2.mp4"},
    {"text": "Measuring throughput and latency metrics.", "output": "/tmp/concurrent_test_3.mp4"},
]

WORKER_CONFIGS = [1, 2, 3, 4, 6, 8]  # Test up to 8 workers
REFERENCE_IMAGE = "/app/bruce_haircut.jpg"
VOICE_SAMPLE = "/app/bruce_expressive_motion_21s.mp3"

# Baseline: Calculate expected audio duration
EXPECTED_AUDIO_DURATION = 6.8  # seconds average from sequential benchmark

def run_concurrent_test(num_workers: int) -> dict:
    """Run benchmark with specified number of workers."""
    
    print(f"\n{'='*70}")
    print(f"📊 Testing {num_workers} Worker{'s' if num_workers > 1 else ''}")
    print(f"{'='*70}")
    
    try:
        # Create generator with specified workers
        print(f"Initializing {num_workers}-worker generator...")
        init_start = time.time()
        generator = ConcurrentVideoGenerator(
            num_workers=num_workers,
            voice_sample_path=VOICE_SAMPLE
        )
        generator.initialize()
        generator.start()
        init_time = time.time() - init_start
        print(f"✅ Initialized in {init_time:.1f}s")
        
        # Create and submit jobs
        job_ids = []
        for i, job_config in enumerate(TEST_JOBS):
            job = VideoJob(
                job_id=f"job_{i+1}",
                image_path=REFERENCE_IMAGE,
                text=job_config["text"],
                output_path=job_config["output"],
                voice_sample=VOICE_SAMPLE,
                language="en"
            )
            generator.submit_job(job)
            job_ids.append(job.job_id)
        
        # Wait for all jobs to complete
        print(f"\n🎬 Generating {len(job_ids)} videos...")
        gen_start = time.time()
        results = []
        for job_id in job_ids:
            result = generator.get_result(job_id, timeout=300)
            if result:
                results.append(result)
        gen_time = time.time() - gen_start
        
        # Calculate metrics
        successful = sum(1 for r in results if r.success)
        total_processing = gen_time
        avg_per_video = total_processing / len(TEST_JOBS) if TEST_JOBS else 0
        
        # Calculate RTF based on expected audio duration
        total_audio_duration = EXPECTED_AUDIO_DURATION * len(TEST_JOBS)
        rtf = total_processing / total_audio_duration if total_audio_duration > 0 else 0
        
        # Throughput
        videos_per_hour = (3600 / avg_per_video) if avg_per_video > 0 else 0
        
        # Cleanup
        generator.stop()
        
        result = {
            "workers": num_workers,
            "success": successful == len(TEST_JOBS),
            "successful_jobs": successful,
            "total_jobs": len(TEST_JOBS),
            "init_time": init_time,
            "generation_time": gen_time,
            "avg_per_video": avg_per_video,
            "rtf": rtf,
            "videos_per_hour": videos_per_hour,
            "speedup": None  # Will calculate relative to 1 worker
        }
        
        print(f"\n✅ Results:")
        print(f"  Success: {successful}/{len(TEST_JOBS)} videos")
        print(f"  Total time: {gen_time:.1f}s")
        print(f"  Avg per video: {avg_per_video:.1f}s")
        print(f"  RTF: {rtf:.2f}x realtime")
        print(f"  Throughput: {videos_per_hour:.1f} videos/hour")
        
        return result
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "workers": num_workers,
            "success": False,
            "error": str(e)
        }

def main():
    """Run benchmark across all worker configurations."""
    
    print(f"\n📝 Test Configuration:")
    print(f"  Jobs per test: {len(TEST_JOBS)}")
    print(f"  Worker counts: {WORKER_CONFIGS}")
    print(f"  Expected audio: ~{EXPECTED_AUDIO_DURATION:.1f}s per video")
    
    results = []
    baseline_time = None
    
    for num_workers in WORKER_CONFIGS:
        result = run_concurrent_test(num_workers)
        
        if result.get("success"):
            # Calculate speedup relative to 1 worker
            if num_workers == 1:
                baseline_time = result["generation_time"]
            elif baseline_time:
                result["speedup"] = baseline_time / result["generation_time"]
        
        results.append(result)
        
        # Brief pause between tests
        if num_workers < WORKER_CONFIGS[-1]:
            print(f"\n⏸️  Cooling down 5s...")
            time.sleep(5)
    
    # Summary
    print(f"\n{'='*70}")
    print("📈 BENCHMARK SUMMARY")
    print(f"{'='*70}")
    
    print(f"\n{'Workers':<10}{'RTF':<12}{'Videos/Hr':<15}{'Speedup':<12}{'Status':<10}")
    print("-" * 70)
    
    for r in results:
        if r.get("success"):
            workers = r["workers"]
            rtf = f"{r['rtf']:.2f}x"
            throughput = f"{r['videos_per_hour']:.1f}"
            speedup = f"{r['speedup']:.2f}x" if r.get("speedup") else "baseline"
            status = "✅ OK" if r["rtf"] < 1.0 else "⚠️  Slow"
            print(f"{workers:<10}{rtf:<12}{throughput:<15}{speedup:<12}{status:<10}")
        else:
            print(f"{r['workers']:<10}{'FAILED':<12}{r.get('error', 'Unknown')[:40]}")
    
    # Find best configuration
    successful = [r for r in results if r.get("success")]
    if successful:
        print(f"\n🎯 Best Performance:")
        
        # Best RTF (fastest relative to realtime)
        best_rtf = min(successful, key=lambda x: x["rtf"])
        print(f"  Fastest RTF: {best_rtf['workers']} workers @ {best_rtf['rtf']:.2f}x realtime")
        
        # Best throughput
        best_throughput = max(successful, key=lambda x: x["videos_per_hour"])
        print(f"  Max throughput: {best_throughput['workers']} workers @ {best_throughput['videos_per_hour']:.0f} videos/hour")
        
        # Check if any meet goal
        realtime_configs = [r for r in successful if r["rtf"] < 1.0]
        if realtime_configs:
            print(f"\n🎉 GOAL MET! Realtime achieved with {len(realtime_configs)} configuration(s):")
            for r in realtime_configs:
                print(f"    {r['workers']} workers: {r['rtf']:.2f}x RTF")
        else:
            print(f"\n⚠️  Goal not met. Best RTF: {best_rtf['rtf']:.2f}x (need <1.0x)")
    
    print(f"\n{'='*70}")
    print("✅ Benchmark complete!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
