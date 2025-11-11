"""
Quick test - just generate ONE video to verify system works.
"""

import time
import sys
sys.path.append("/app")

print("=" * 80)
print("STARTING TEST")
print("=" * 80)

print("\n1. Importing TTS...")
from runtime.models.tts import XTTSModel
print("   ✓ TTS imported")

print("\n2. Importing Ditto...")
from runtime.models.ditto_model import DittoModel
print("   ✓ Ditto imported")

print("\n3. Creating TTS model...")
tts = XTTSModel()
print("   ✓ TTS object created")

print("\n4. Initializing TTS (this takes ~10-15 seconds)...")
tts.initialize()
print("   ✓ TTS initialized")

print("\n5. Creating Ditto model...")
ditto = DittoModel()
print("   ✓ Ditto object created")

print("\n6. Initializing Ditto (this takes ~5-10 seconds)...")
ditto.initialize()
print("   ✓ Ditto initialized")

print("\n7. Generating audio...")
start = time.time()
audio_path, tts_time = tts.synthesize(
    text="Hello, this is a quick test.",
    language="en",
    speaker_wav="/app/test_bruce_narration.wav",
    output_path="/tmp/test_audio.wav"
)
print(f"   ✓ Audio generated in {tts_time/1000:.2f}s")

print("\n8. Generating video...")
video_start = time.time()
video_path, ditto_time = ditto.generate_video(
    audio_path=audio_path,
    reference_image_path="/app/bruce_haircut.jpg",
    output_path="/tmp/test_video.mp4"
)
video_elapsed = time.time() - video_start
print(f"   ✓ Video generated in {video_elapsed:.2f}s")

total_time = time.time() - start
print(f"\n{'='*80}")
print(f"✅ TEST COMPLETE")
print(f"Total time: {total_time:.2f}s")
print(f"TTS: {tts_time/1000:.2f}s, Ditto: {ditto_time/1000:.2f}s")
print(f"Output: {video_path}")
print(f"{'='*80}")
