"""
Simple concurrent benchmark - generate multiple videos and compare sequential vs concurrent.
Avoids re-initialization by loading models once.
"""

import time
import sys
import os
sys.path.append("/app")

from runtime.models.tts import XTTSModel
from runtime.models.ditto_model import DittoModel

def sequential_benchmark(tts, ditto, num_videos=3):
    """Generate videos sequentially."""
    print("\n" + "="*80)
    print("SEQUENTIAL BENCHMARK ({} videos)".format(num_videos))
    print("="*80)
    
    texts = [
        "This is test video number one for sequential processing.",
        "The quick brown fox jumps over the lazy dog in test two.",
        "Final test video three for baseline performance measurement."
    ]
    
    results = []
    total_start = time.time()
    
    for i in range(num_videos):
        print(f"\n🎬 Video {i+1}/{num_videos}...")
        vid_start = time.time()
        
        # Generate audio
        audio_path, tts_ms = tts.synthesize(
            text=texts[i % len(texts)],
            language="en",
            speaker_wav="/app/test_bruce_narration.wav",
            output_path=f"/tmp/seq_audio_{i+1}.wav"
        )
        
        # Generate video  
        video_path, ditto_ms = ditto.generate_video(
            audio_path=audio_path,
            reference_image_path="/app/bruce_haircut.jpg",
            output_path=f"/tmp/seq_video_{i+1}.mp4"
        )
        
        vid_time = time.time() - vid_start
        results.append(vid_time)
        print(f"  ✅ {vid_time:.1f}s (TTS: {tts_ms/1000:.1f}s, Ditto: {ditto_ms/1000:.1f}s)")
    
    total_time = time.time() - total_start
    avg_time = sum(results) / len(results)
    
    print(f"\n📊 SEQUENTIAL RESULTS:")
    print(f"  Total time:    {total_time:.1f}s")
    print(f"  Avg per video: {avg_time:.1f}s")
    print(f"  Throughput:    {num_videos/total_time*3600:.0f} videos/hour")
    
    return total_time, avg_time

def concurrent_benchmark_manual(tts, num_videos=3):
    """
    Simulate concurrent by generating audio for all videos first,
    then videos in quick succession (limited parallelism test).
    """
    print("\n" + "="*80)
    print("PSEUDO-CONCURRENT BENCHMARK ({} videos)".format(num_videos))
    print("="*80)
    print("(Pre-generate all audio, then generate videos)")
    
    texts = [
        "This is test video number one for concurrent processing.",
        "The quick brown fox jumps over the lazy dog in test two.",
        "Final test video three for concurrent performance measurement."
    ]
    
    total_start = time.time()
    
    # Phase 1: Generate all audio files
    print("\n📢 Phase 1: Generating all audio files...")
    audio_files = []
    for i in range(num_videos):
        audio_path, tts_ms = tts.synthesize(
            text=texts[i % len(texts)],
            language="en",
            speaker_wav="/app/test_bruce_narration.wav",
            output_path=f"/tmp/conc_audio_{i+1}.wav"
        )
        audio_files.append(audio_path)
        print(f"  ✅ Audio {i+1}: {tts_ms/1000:.1f}s")
    
    # Phase 2: Generate all videos (Ditto can't really parallelize without threading)
    print("\n🎥 Phase 2: Generating all videos...")
    ditto1 = DittoModel()
    ditto1.initialize()
    
    video_times = []
    for i, audio_path in enumerate(audio_files):
        vid_start = time.time()
        video_path, ditto_ms = ditto1.generate_video(
            audio_path=audio_path,
            reference_image_path="/app/bruce_haircut.jpg",
            output_path=f"/tmp/conc_video_{i+1}.mp4"
        )
        vid_time = time.time() - vid_start
        video_times.append(vid_time)
        print(f"  ✅ Video {i+1}: {vid_time:.1f}s (Ditto: {ditto_ms/1000:.1f}s)")
    
    total_time = time.time() - total_start
    avg_time = total_time / num_videos
    
    print(f"\n📊 PSEUDO-CONCURRENT RESULTS:")
    print(f"  Total time:    {total_time:.1f}s")
    print(f"  Avg per video: {avg_time:.1f}s")
    print(f"  Throughput:    {num_videos/total_time*3600:.0f} videos/hour")
    
    return total_time, avg_time

def main():
    print("="*80)
    print("BENCHMARK: Sequential vs Concurrent Video Generation")
    print("="*80)
    
    num_videos = 3
    
    # Initialize models ONCE
    print("\n📦 Loading models...")
    init_start = time.time()
    
    tts = XTTSModel()
    tts.initialize()
    print(f"  ✅ TTS loaded ({time.time()-init_start:.1f}s)")
    
    ditto_start = time.time()
    ditto = DittoModel()
    ditto.initialize()
    print(f"  ✅ Ditto loaded ({time.time()-ditto_start:.1f}s)")
    
    # Run sequential benchmark
    seq_time, seq_avg = sequential_benchmark(tts, ditto, num_videos)
    
    # Run pseudo-concurrent benchmark
    conc_time, conc_avg = concurrent_benchmark_manual(tts, num_videos)
    
    # Compare
    print("\n" + "="*80)
    print("📈 COMPARISON")
    print("="*80)
    speedup = seq_time / conc_time if conc_time > 0 else 0
    print(f"Sequential:        {seq_time:.1f}s ({seq_avg:.1f}s avg)")
    print(f"Pseudo-Concurrent: {conc_time:.1f}s ({conc_avg:.1f}s avg)")
    print(f"Speedup:           {speedup:.2f}x")
    print("="*80)

if __name__ == "__main__":
    main()
