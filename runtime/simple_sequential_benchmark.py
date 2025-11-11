#!/usr/bin/env python3
"""
Ultra-simple benchmark: Run test_video_generation.py multiple times.
Use the working script, just time it.
"""

import subprocess
import time
import sys

def run_video_generation(run_num):
    """Run the working test script and capture timing."""
    print(f"\n{'='*80}")
    print(f"RUN {run_num}: Starting video generation...")
    print(f"{'='*80}")
    
    start = time.time()
    
    # Run the known-working script
    result = subprocess.run(
        ["python", "/app/test_video_generation.py"],
        capture_output=True,
        text=True
    )
    
    elapsed = time.time() - start
    
    if result.returncode == 0:
        print(f"✅ Run {run_num} completed in {elapsed:.1f}s")
        
        # Try to extract timing from output
        for line in result.stdout.split('\n'):
            if 'Total time:' in line or 'TTS:' in line or 'Video:' in line:
                print(f"   {line.strip()}")
        
        return elapsed, True
    else:
        print(f"❌ Run {run_num} failed!")
        print(result.stderr[-500:] if result.stderr else "No error output")
        return elapsed, False

def main():
    num_runs = 3
    
    print(f"🚀 SEQUENTIAL BENCHMARK: {num_runs} video generations")
    print(f"Using proven working script: test_video_generation.py")
    print(f"{'='*80}\n")
    
    results = []
    total_start = time.time()
    
    for i in range(1, num_runs + 1):
        elapsed, success = run_video_generation(i)
        results.append({
            'run': i,
            'time': elapsed,
            'success': success
        })
        
        # Short pause between runs
        if i < num_runs:
            print(f"\n⏸️  Waiting 5 seconds before next run...")
            time.sleep(5)
    
    total_time = time.time() - total_start
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"📊 BENCHMARK SUMMARY")
    print(f"{'='*80}")
    
    successful = [r for r in results if r['success']]
    
    print(f"Total runs:        {num_runs}")
    print(f"Successful:        {len(successful)}")
    print(f"Failed:            {num_runs - len(successful)}")
    print(f"Total time:        {total_time:.1f}s")
    
    if successful:
        times = [r['time'] for r in successful]
        avg_time = sum(times) / len(times)
        
        print(f"\nTiming per video:")
        for r in results:
            status = "✅" if r['success'] else "❌"
            print(f"  Run {r['run']}: {r['time']:.1f}s {status}")
        
        print(f"\nAverage time:      {avg_time:.1f}s")
        print(f"Throughput:        {len(successful)/total_time*3600:.1f} videos/hour")
        print(f"Sequential rate:   {3600/avg_time:.1f} videos/hour per worker")
    
    print(f"{'='*80}\n")
    
    return 0 if len(successful) == num_runs else 1

if __name__ == "__main__":
    sys.exit(main())
