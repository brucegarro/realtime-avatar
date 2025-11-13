#!/usr/bin/env python3
"""
Simple 2-worker concurrent test
"""
import sys
import os
import time

# Add runtime to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/runtime')
os.chdir('/app/runtime')

print("\n" + "="*70)
print("🚀 2-WORKER CONCURRENT TEST")
print("="*70)

from workers.concurrent_generator import ConcurrentVideoGenerator, VideoJob

# Test configuration
REFERENCE_IMAGE = "/app/bruce_haircut.jpg"
VOICE_SAMPLE = "/app/bruce_expressive_motion_21s.mp3"

print("\n📝 Test: 2 workers, 3 videos")
print(f"  Image: {REFERENCE_IMAGE}")
print(f"  Voice: {VOICE_SAMPLE}")

# Create generator
print("\n1. Creating generator...")
start = time.time()
generator = ConcurrentVideoGenerator(
    num_workers=2,
    voice_sample_path=VOICE_SAMPLE
)
print(f"   ✓ Created in {time.time() - start:.1f}s")

# Initialize models
print("\n2. Initializing models...")
start = time.time()
generator.initialize()
init_time = time.time() - start
print(f"   ✓ Initialized in {init_time:.1f}s")

# Start workers
print("\n3. Starting workers...")
start = time.time()
generator.start()
print(f"   ✓ Workers started in {time.time() - start:.1f}s")

# Create jobs
jobs = [
    VideoJob(
        job_id="job_1",
        image_path=REFERENCE_IMAGE,
        text="Testing video generation performance.",
        output_path="/tmp/test_worker_1.mp4",
        voice_sample=VOICE_SAMPLE,
        language="en"
    ),
    VideoJob(
        job_id="job_2",
        image_path=REFERENCE_IMAGE,
        text="Quick brown fox jumps over lazy dog.",
        output_path="/tmp/test_worker_2.mp4",
        voice_sample=VOICE_SAMPLE,
        language="en"
    ),
    VideoJob(
        job_id="job_3",
        image_path=REFERENCE_IMAGE,
        text="Measuring throughput and latency metrics.",
        output_path="/tmp/test_worker_3.mp4",
        voice_sample=VOICE_SAMPLE,
        language="en"
    )
]

# Submit jobs
print("\n4. Submitting jobs...")
for job in jobs:
    generator.submit_job(job)
    print(f"   ✓ Submitted {job.job_id}")

# Wait for results
print("\n5. Waiting for results...")
gen_start = time.time()
results = []
for job in jobs:
    print(f"   ⏳ Waiting for {job.job_id}...")
    result = generator.get_result(job.job_id, timeout=300)
    if result:
        results.append(result)
        if result.success:
            print(f"   ✅ {job.job_id}: {result.duration:.1f}s by worker {result.worker_id+1}")
        else:
            print(f"   ❌ {job.job_id}: {result.error}")
gen_time = time.time() - gen_start

# Stop workers
generator.stop()

# Calculate metrics
successful = sum(1 for r in results if r.success)
avg_time = gen_time / len(jobs)
rtf = gen_time / (6.8 * len(jobs))  # Expected 6.8s audio per video

print("\n" + "="*70)
print("📊 RESULTS")
print("="*70)
print(f"Success:      {successful}/{len(jobs)} videos")
print(f"Total time:   {gen_time:.1f}s")
print(f"Avg per video: {avg_time:.1f}s")
print(f"RTF:          {rtf:.2f}x realtime")
print(f"Throughput:   {3600/avg_time:.1f} videos/hour")
print("="*70 + "\n")
