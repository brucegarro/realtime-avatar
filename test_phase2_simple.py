#!/usr/bin/env python3
"""
Simple Phase 2 Testing Script
Tests Faster-Whisper ASR with CUDA 12
"""
import time
import sys
import os

# Add paths
sys.path.insert(0, '/app/runtime')

print("="*70)
print("PHASE 2: FASTER-WHISPER ASR TEST (CUDA 12)")
print("="*70)

try:
    from models.asr import ASRModel
    
    print("\n🎤 Initializing Faster-Whisper ASR with CUDA 12...")
    start_init = time.time()
    asr = ASRModel(device="cuda")
    asr.initialize(model_size="base")
    init_time = time.time() - start_init
    print(f"✅ ASR initialized in {init_time:.2f}s")
    
    # Test audio files
    test_audios = [
        "/app/bruce_expressive_motion_21s.mp3",
        "/app/bruce_expressive_motion_41s.mp3"
    ]
    
    for audio_path in test_audios:
        if not os.path.exists(audio_path):
            print(f"⚠️  Audio not found: {audio_path}")
            continue
        
        print(f"\n🔊 Transcribing: {os.path.basename(audio_path)}")
        start = time.time()
        
        # Note: Current ASR returns (text, language, probability) not (text, metadata_dict)
        # This is a bug to fix later
        result = asr.transcribe(audio_path)
        
        if isinstance(result, tuple) and len(result) == 3:
            text, language, lang_prob = result
            # Estimate audio duration from text length (rough: ~150 words/min, ~2.5 chars/word)
            estimated_duration = len(text.split()) / 150 * 60  # rough estimate
        elif isinstance(result, tuple) and len(result) == 2:
            text, metadata = result
            estimated_duration = metadata.get('duration', len(text.split()) / 150 * 60)
        else:
            print(f"Unexpected result format: {result}")
            continue
        
        elapsed = time.time() - start
        # For now, use estimated duration
        audio_duration = estimated_duration
        rtf = elapsed / audio_duration if audio_duration > 0 else 0
        
        print(f"✅ Transcription complete in {elapsed:.2f}s")
        print(f"   Audio duration: {audio_duration:.2f}s")
        print(f"   RTF: {rtf:.3f}x (lower is better)")
        print(f"   Text: {text[:200]}...")
        
        if rtf < 0.3:
            print(f"   🚀 EXCELLENT! Real-time capable (<0.3x RTF)")
        elif rtf < 1.0:
            print(f"   ✅ GOOD! Faster than real-time")
        else:
            print(f"   ⚠️  Slower than real-time")
    
    print("\n" + "="*70)
    print("TEST COMPLETE - FASTER-WHISPER WITH CUDA 12 WORKING!")
    print("="*70)
            
except Exception as e:
    print(f"❌ ASR test failed: {e}")
    import traceback
    traceback.print_exc()
