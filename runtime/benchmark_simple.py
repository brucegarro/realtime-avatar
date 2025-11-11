"""
Simple manual benchmark - generate videos sequentially to test baseline performance.
Then we can compare with concurrent execution.
"""

import time
import sys
sys.path.append("/app")

from runtime.models.tts import XTTSModel
from runtime.models.ditto_model import DittoModel

def benchmark_sequential(num_videos=4):
    """Generate videos one at a time."""
    print("="*80)
    print("SEQUENTIAL BENCHMARK")
    print("="*80)
    
    # Initialize models
    print("\n📦 Loading models...")
    tts = XTTSModel()
    tts.initialize()
    
    ditto = DittoModel()
    ditto.initialize()
    
    print("✅ Models loaded\n")
    
    # Test texts
    texts = [
        "Hello, this is test number one.",
        "The quick brown fox jumps over the lazy dog.",
        "Testing sequential video generation.",
        "This is the fourth and final test."
    ]
    
    total_start = time.time()
    results = []
    
    for i in range(num_videos):
        print(f"\n🎬 Generating video {i+1}/{num_videos}...")
        job_start = time.time()
        
        try:
            # Generate audio
            print(f"  🎤 TTS...")
            audio_path, tts_time = tts.synthesize(
                text=texts[i % len(texts)],
                language="en",
                speaker_wav="/app/test_bruce_narration.wav",
                output_path=f"/tmp/seq_audio_{i+1}.wav"
            )
            
            # Generate video
            print(f"  🎥 Ditto...")
            video_path, ditto_time = ditto.generate_video(
                audio_path=audio_path,
                reference_image_path="/app/bruce_haircut.jpg",
                output_path=f"/tmp/seq_video_{i+1}.mp4"
            )
            
            job_time = time.time() - job_start
            results.append({
                "success": True,
                "job_time": job_time,
                "tts_time": tts_time / 1000.0,  # Convert ms to seconds
                "ditto_time": ditto_time / 1000.0
            })
            
            print(f"  ✅ Complete: {job_time:.2f}s (TTS: {tts_time/1000:.2f}s, Ditto: {ditto_time/1000:.2f}s)")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results.append({"success": False, "error": str(e)})
    
    total_time = time.time() - total_start
    
    # Print results
    print(f"\n{'='*80}")
    print("📊 SEQUENTIAL RESULTS")
    print(f"{'='*80}")
    
    successful = [r for r in results if r.get("success")]
    print(f"Videos Generated:    {len(successful)}/{num_videos}")
    print(f"Total Time:          {total_time:.2f}s")
    if successful:
        avg_time = sum(r["job_time"] for r in successful) / len(successful)
        print(f"Avg Time/Video:      {avg_time:.2f}s")
        print(f"Throughput:          {len(successful)/total_time:.3f} videos/sec")
        print(f"                     {len(successful)/total_time*3600:.0f} videos/hour")
    print(f"{'='*80}\n")
    
    return results, total_time


if __name__ == "__main__":
    results, total_time = benchmark_sequential(4)
    print(f"\n🎉 Benchmark complete! Total time: {total_time:.2f}s")
