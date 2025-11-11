import sys
import os
import torch
import time
from pathlib import Path

# Add runtime to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/runtime')

# Change to runtime directory for checkpoint path resolution
os.chdir('/app/runtime')

print("\n" + "="*60)
print("🚀 DIRECT SEQUENTIAL BENCHMARK")
print("="*60)

print("\n1. Importing models...")
from models.tts import XTTSModel
from models.asr import ASRModel
from models.ditto_model import DittoModel
print("   ✓ Imports complete")

print("\n2. Initializing TTS...")
start = time.time()
tts = XTTSModel()
tts.initialize()
tts_time = time.time() - start
print(f"   ✓ TTS ready ({tts_time:.1f}s)")

print("\n3. Initializing ASR...")
start = time.time()
asr = ASRModel()
asr.initialize()
asr_time = time.time() - start
print(f"   ✓ ASR ready ({asr_time:.1f}s)")

print("\n4. Initializing Ditto...")
start = time.time()
ditto = DittoModel(device="cuda")
ditto.initialize()
ditto_time = time.time() - start
print(f"   ✓ Ditto ready ({ditto_time:.1f}s)")

total_init = tts_time + asr_time + ditto_time
print(f"\n✅ All models initialized in {total_init:.1f}s")

# Test data - short phrases for faster benchmarking
test_texts = [
    "Testing video generation performance.",
    "Quick brown fox jumps over lazy dog.",
    "Measuring throughput and latency metrics."
]

print("\n" + "="*60)
print(f"📊 GENERATING {len(test_texts)} TEST VIDEOS")
print("="*60)

video_times = []
total_duration = 0

# Reference files
speaker_reference = "/app/bruce_expressive_motion_21s.mp3"
image_reference = "/app/bruce_haircut.jpg"

print(f"🎤 Voice cloning reference: {speaker_reference}")
print(f"🖼️  Image reference: {image_reference}")
print()

for i, text in enumerate(test_texts, 1):
    print(f"\n[Video {i}/{len(test_texts)}]")
    print(f"Text: {text[:50]}...")
    
    start = time.time()
    
    # TTS
    audio_path = f"/tmp/test_audio_{i}.wav"
    tts_start = time.time()
    audio_path, duration_ms, audio_duration = tts.synthesize(
        text=text,
        speaker_wav=speaker_reference,
        output_path=audio_path
    )
    tts_elapsed = time.time() - tts_start
    
    # Ditto
    video_path = f"/tmp/test_video_{i}.mp4"
    ditto_start = time.time()
    ditto.generate_video(
        audio_path=audio_path,
        reference_image_path=image_reference,
        output_path=video_path
    )
    ditto_elapsed = time.time() - ditto_start
    
    total = time.time() - start
    video_times.append(total)
    total_duration += audio_duration
    
    # Calculate RTF for this video
    video_rtf = total / audio_duration if audio_duration > 0 else 0
    tts_rtf = tts_elapsed / audio_duration if audio_duration > 0 else 0
    ditto_rtf = ditto_elapsed / audio_duration if audio_duration > 0 else 0
    
    print(f"  ├─ TTS:     {tts_elapsed:6.2f}s (RTF: {tts_rtf:.2f}x)")
    print(f"  ├─ Ditto:   {ditto_elapsed:6.2f}s (RTF: {ditto_rtf:.2f}x)")
    print(f"  └─ Total:   {total:6.2f}s (RTF: {video_rtf:.2f}x) | Audio: {audio_duration:.1f}s")

print("\n" + "="*60)
print("📈 BENCHMARK RESULTS")
print("="*60)

avg_time = sum(video_times) / len(video_times)
avg_audio_duration = total_duration / len(video_times)
avg_rtf = avg_time / avg_audio_duration if avg_audio_duration > 0 else 0

throughput_hour = 3600 / avg_time
throughput_day = throughput_hour * 24

print(f"\n⚡ Real-Time Performance:")
print(f"  Average RTF:  {avg_rtf:.2f}x realtime")
print(f"  Target:       < 1.0x realtime (GOAL)")
print(f"  Status:       {'✅ GOAL MET!' if avg_rtf < 1.0 else '⚠️  Need optimization'}")

print(f"\nPer-Video Performance:")
print(f"  Average time:  {avg_time:.2f}s")
print(f"  Average audio: {avg_audio_duration:.1f}s")
print(f"  Min time:      {min(video_times):.2f}s")
print(f"  Max time:      {max(video_times):.2f}s")
print(f"  Total time:    {sum(video_times):.2f}s")
print(f"  Total audio:   {total_duration:.1f}s")

print(f"\nThroughput (1 Worker):")
print(f"  {throughput_hour:.1f} videos/hour")
print(f"  {throughput_day:.0f} videos/day")

print(f"\nProjected Concurrent Performance:")
print(f"  2 Workers: {throughput_hour * 2:.1f} videos/hour ({throughput_day * 2:.0f}/day) - RTF: {avg_rtf/2:.2f}x")
print(f"  3 Workers: {throughput_hour * 3:.1f} videos/hour ({throughput_day * 3:.0f}/day) - RTF: {avg_rtf/3:.2f}x")

print("\n✅ Benchmark complete!")
print("="*60)
