#!/usr/bin/env python3
"""
Generate a test video using bruce_haircut.jpg with TTS and Ditto
"""
import time
import sys
import os

sys.path.insert(0, '/app/runtime')

print("="*70)
print("VIDEO GENERATION TEST - Bruce Haircut Portrait")
print("="*70)

# Interesting script for the video
test_script = """
Hey there! I'm excited to show you what we've built with this real-time avatar system.
We're using CUDA acceleration on an L4 GPU to generate talking head videos at nearly 
three times real-time speed. The system combines speech synthesis with facial animation,
creating natural-looking videos from just a single photo and text input. 
Pretty cool, right?
"""

try:
    print("\n📝 Script:")
    print(test_script.strip())
    print()
    
    # Step 1: Generate audio with TTS
    print("="*70)
    print("STEP 1: Generating Audio with XTTS-v2")
    print("="*70)
    
    from models.tts import XTTSModel
    
    tts = XTTSModel()
    print("🔊 Initializing TTS model...")
    tts.initialize()
    
    audio_output = "/app/test_bruce_narration.wav"
    speaker_reference = "/app/bruce_expressive_motion_21s.mp3"
    
    print(f"🎤 Synthesizing speech with voice cloning...")
    print(f"   Reference: {speaker_reference}")
    start_tts = time.time()
    tts.synthesize(
        text=test_script.strip(),
        output_path=audio_output,
        speaker_wav=speaker_reference
    )
    tts_time = time.time() - start_tts
    
    # Get audio duration
    import soundfile as sf
    audio_data, sr = sf.read(audio_output)
    audio_duration = len(audio_data) / sr
    tts_rtf = tts_time / audio_duration
    
    print(f"✅ Audio generated in {tts_time:.2f}s")
    print(f"   Audio duration: {audio_duration:.2f}s")
    print(f"   TTS RTF: {tts_rtf:.2f}x")
    print(f"   Output: {audio_output}")
    
    # Step 2: Generate video with Ditto
    print("\n" + "="*70)
    print("STEP 2: Generating Video with Ditto")
    print("="*70)
    
    from models.ditto_model import DittoModel
    
    ditto = DittoModel(device="cuda")
    print("🎬 Initializing Ditto model...")
    ditto.initialize()
    
    image_input = "/app/bruce_haircut.jpg"
    video_output = "/app/bruce_haircut_demo.mp4"
    
    print(f"📸 Input image: {image_input}")
    print(f"🔊 Input audio: {audio_output}")
    print(f"🎥 Generating video...")
    
    start_video = time.time()
    result = ditto.generate_video(
        audio_path=audio_output,
        reference_image_path=image_input,
        output_path=video_output
    )
    video_time = time.time() - start_video
    video_rtf = video_time / audio_duration
    
    print(f"✅ Video generated in {video_time:.2f}s")
    print(f"   Video duration: {audio_duration:.2f}s")
    print(f"   Video RTF: {video_rtf:.2f}x realtime")
    print(f"   Output: {video_output}")
    
    # Summary
    print("\n" + "="*70)
    print("GENERATION COMPLETE!")
    print("="*70)
    print(f"Total time: {tts_time + video_time:.2f}s")
    print(f"TTS: {tts_time:.2f}s ({tts_rtf:.2f}x RTF)")
    print(f"Video: {video_time:.2f}s ({video_rtf:.2f}x RTF)")
    print(f"\n📹 Video saved to: {video_output}")
    print(f"   Download with: gcloud compute scp realtime-avatar-test:{video_output} ./")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
