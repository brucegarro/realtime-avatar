#!/usr/bin/env python3
"""
Direct benchmark - import and call functions directly, no subprocess.
Just time 3 sequential video generations using the same code path as test_video_generation.py
"""

import time
import sys
import os

# Same setup as test_video_generation.py
sys.path.append("/app")
os.chdir("/app")

print("🚀 DIRECT SEQUENTIAL BENCHMARK")
print("="*80)

# Import models
print("\n1. Importing models...")
from runtime.models.tts import XTTSModel
from runtime.models.ditto_model import DittoModel

# Initialize models ONCE
print("\n2. Initializing TTS...")
init_start = time.time()
tts = XTTSModel()
tts.initialize()
tts_init_time = time.time() - init_start
print(f"   ✅ TTS ready ({tts_init_time:.1f}s)")

print("\n3. Initializing Ditto...")
ditto_start = time.time()
ditto = DittoModel()
ditto.initialize()
ditto_init_time = time.time() - ditto_start
print(f"   ✅ Ditto ready ({ditto_init_time:.1f}s)")

total_init = tts_init_time + ditto_init_time
print(f"\nTotal initialization: {total_init:.1f}s")

# Generate 3 videos
num_videos = 3
results = []

texts = [
    "Hey there! I'm excited to show you what we've built with this real-time avatar system.",
    "This is the second test video to measure consistent performance across multiple generations.",
    "And here's the third video to complete our benchmark testing sequence."
]

print(f"\n{'='*80}")
print(f"Generating {num_videos} videos sequentially...")
print(f"{'='*80}\n")

benchmark_start = time.time()

for i in range(num_videos):
    print(f"📹 Video {i+1}/{num_videos}")
    video_start = time.time()
    
    try:
        # Generate audio
        print(f"   🎤 TTS...")
        audio_path, tts_ms = tts.synthesize(
            text=texts[i],
            language="en",
            speaker_wav="/app/test_bruce_narration.wav",
            output_path=f"/tmp/bench_audio_{i+1}.wav"
        )
        print(f"      {tts_ms/1000:.1f}s")
        
        # Generate video
        print(f"   🎥 Ditto...")
        video_path, ditto_ms = ditto.generate_video(
            audio_path=audio_path,
            reference_image_path="/app/bruce_haircut.jpg",
            output_path=f"/tmp/bench_video_{i+1}.mp4"
        )
        print(f"      {ditto_ms/1000:.1f}s")
        
        video_time = time.time() - video_start
        
        results.append({
            'success': True,
            'total': video_time,
            'tts': tts_ms / 1000,
            'ditto': ditto_ms / 1000
        })
        
        print(f"   ✅ Complete: {video_time:.1f}s\n")
        
    except Exception as e:
        print(f"   ❌ Error: {e}\n")
        results.append({
            'success': False,
            'total': time.time() - video_start,
            'error': str(e)
        })

total_benchmark = time.time() - benchmark_start

# Print results
print(f"{'='*80}")
print(f"📊 BENCHMARK RESULTS")
print(f"{'='*80}")

successful = [r for r in results if r.get('success')]

print(f"\nVideos generated:  {len(successful)}/{num_videos}")
print(f"Total time:        {total_benchmark:.1f}s")
print(f"Init overhead:     {total_init:.1f}s")
print(f"Pure generation:   {total_benchmark:.1f}s")

if successful:
    print(f"\nPer-video breakdown:")
    for i, r in enumerate(results):
        if r.get('success'):
            print(f"  Video {i+1}: {r['total']:.1f}s (TTS: {r['tts']:.1f}s, Ditto: {r['ditto']:.1f}s)")
        else:
            print(f"  Video {i+1}: FAILED")
    
    avg_total = sum(r['total'] for r in successful) / len(successful)
    avg_tts = sum(r['tts'] for r in successful) / len(successful)
    avg_ditto = sum(r['ditto'] for r in successful) / len(successful)
    
    print(f"\nAverages:")
    print(f"  Per video:  {avg_total:.1f}s")
    print(f"  TTS:        {avg_tts:.1f}s")
    print(f"  Ditto:      {avg_ditto:.1f}s")
    
    # Throughput calculations
    throughput_pure = len(successful) / total_benchmark * 3600
    throughput_with_init = len(successful) / (total_benchmark + total_init) * 3600
    per_worker_rate = 3600 / avg_total
    
    print(f"\nThroughput (single worker):")
    print(f"  Pure generation:    {throughput_pure:.1f} videos/hour")
    print(f"  With init:          {throughput_with_init:.1f} videos/hour")
    print(f"  Steady state rate:  {per_worker_rate:.1f} videos/hour")
    
    print(f"\nProjected concurrent performance:")
    print(f"  2 workers: {per_worker_rate * 2:.1f} videos/hour (2.0x)")
    print(f"  3 workers: {per_worker_rate * 3:.1f} videos/hour (3.0x)")

print(f"\n{'='*80}\n")
print("✅ Benchmark complete!")
