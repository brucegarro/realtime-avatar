#!/usr/bin/env python3
"""
Simple single-threaded worker test - no ThreadPoolExecutor
Process jobs one at a time with pre-loaded models
"""
import sys
import os
import time
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, '/app')
sys.path.insert(0, '/app/runtime')
os.chdir('/app/runtime')

print("\n" + "="*70)
print("🔧 SINGLE-THREADED WORKER TEST")
print("="*70)

from models.tts import XTTSModel
from models.ditto_model import DittoModel

@dataclass
class Job:
    job_id: str
    text: str
    output_path: str

# Initialize models once
print("\n1. Initializing TTS...")
start = time.time()
tts = XTTSModel()
tts.initialize()
print(f"   ✅ TTS ready in {time.time() - start:.1f}s")

print("\n2. Creating Ditto instance...")
start = time.time()
ditto = DittoModel(device="cuda")
print(f"   ✅ Ditto ready in {time.time() - start:.1f}s")

# Test jobs
jobs = [
    Job("job_1", "Testing video generation performance.", "/tmp/single_1.mp4"),
    Job("job_2", "Quick brown fox jumps over lazy dog.", "/tmp/single_2.mp4"),
]

REFERENCE_IMAGE = "/app/bruce_haircut.jpg"
VOICE_SAMPLE = "/app/bruce_expressive_motion_21s.mp3"

print(f"\n3. Processing {len(jobs)} jobs sequentially...")
total_start = time.time()

for job in jobs:
    job_start = time.time()
    print(f"\n   [{job.job_id}] Generating audio...")
    
    # Generate audio
    temp_audio = f"/tmp/audio_{job.job_id}.wav"
    audio_path, duration_ms, audio_duration = tts.synthesize(
        text=job.text,
        language="en",
        speaker_wav=VOICE_SAMPLE,
        output_path=temp_audio
    )
    print(f"   [{job.job_id}] Audio: {audio_duration:.1f}s")
    
    # Generate video
    print(f"   [{job.job_id}] Generating video...")
    video_path = ditto.generate(
        audio_path=audio_path,
        reference_image_path=REFERENCE_IMAGE,
        output_path=job.output_path
    )
    
    # Clean up
    if os.path.exists(audio_path):
        os.remove(audio_path)
    
    job_time = time.time() - job_start
    rtf = job_time / audio_duration if audio_duration > 0 else 0
    print(f"   [{job.job_id}] ✅ Complete in {job_time:.1f}s (RTF: {rtf:.2f}x)")

total_time = time.time() - total_start
avg_time = total_time / len(jobs)
print(f"\n" + "="*70)
print(f"📊 RESULTS")
print(f"="*70)
print(f"Total time:    {total_time:.1f}s")
print(f"Avg per video: {avg_time:.1f}s")
print(f"Success:       {len(jobs)}/{len(jobs)} videos")
print("="*70 + "\n")
