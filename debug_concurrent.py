#!/usr/bin/env python3
"""
Debug concurrent worker initialization
Test each component separately to find the hang
"""
import sys
import os
import time

# Add runtime to path
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/runtime')

# Change to runtime directory for checkpoint resolution
os.chdir('/app/runtime')

print("\n" + "="*70)
print("🔍 CONCURRENT WORKER DEBUG")
print("="*70)

# Test 1: Import check
print("\n[1/6] Testing imports...")
try:
    from workers.concurrent_generator import ConcurrentVideoGenerator, VideoJob
    from models.tts import XTTSModel
    from models.asr import ASRModel
    from models.ditto_model import DittoModel
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Single TTS initialization
print("\n[2/6] Testing TTS initialization (shared model)...")
try:
    start = time.time()
    tts = XTTSModel()
    tts.initialize()
    elapsed = time.time() - start
    print(f"✅ TTS initialized in {elapsed:.1f}s")
except Exception as e:
    print(f"❌ TTS init failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: ASR initialization
print("\n[3/6] Testing ASR initialization (shared model)...")
try:
    start = time.time()
    asr = ASRModel(device="cuda")
    asr.initialize()
    elapsed = time.time() - start
    print(f"✅ ASR initialized in {elapsed:.1f}s")
except Exception as e:
    print(f"❌ ASR init failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Single Ditto initialization
print("\n[4/6] Testing single Ditto initialization...")
try:
    start = time.time()
    ditto1 = DittoModel(device="cuda")
    elapsed = time.time() - start
    print(f"✅ Ditto #1 initialized in {elapsed:.1f}s")
except Exception as e:
    print(f"❌ Ditto init failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Multiple Ditto instances (the potential issue)
print("\n[5/6] Testing multiple Ditto instances...")
try:
    start = time.time()
    ditto2 = DittoModel(device="cuda")
    elapsed = time.time() - start
    print(f"✅ Ditto #2 initialized in {elapsed:.1f}s")
    
    import torch
    if torch.cuda.is_available():
        mem_allocated = torch.cuda.memory_allocated("cuda") / 1024**3
        mem_reserved = torch.cuda.memory_reserved("cuda") / 1024**3
        print(f"💾 GPU Memory: {mem_allocated:.2f}GB allocated, {mem_reserved:.2f}GB reserved")
except Exception as e:
    print(f"❌ Multiple Ditto init failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: ConcurrentVideoGenerator with 1 worker
print("\n[6/6] Testing ConcurrentVideoGenerator with 1 worker...")
try:
    start = time.time()
    generator = ConcurrentVideoGenerator(
        num_workers=1,
        voice_sample_path="/app/bruce_expressive_motion_21s.mp3"
    )
    print(f"  Created generator object in {time.time() - start:.1f}s")
    
    start = time.time()
    generator.initialize()
    print(f"  ✅ Models initialized in {time.time() - start:.1f}s")
    
    start = time.time()
    generator.start()
    print(f"  ✅ Workers started in {time.time() - start:.1f}s")
    
    # Wait a moment to ensure threads are stable
    time.sleep(2)
    
    generator.stop()
    print(f"✅ ConcurrentVideoGenerator working!")
    
except Exception as e:
    print(f"❌ ConcurrentVideoGenerator failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("✅ ALL TESTS PASSED - Concurrent workers should work!")
print("="*70 + "\n")
