#!/usr/bin/env python3
"""
Phase 2 Performance Testing Script
Tests Faster-Whisper ASR, image resolution optimization, and full pipeline
"""
import time
import sys
import os
from pathlib import Path

# Add paths
sys.path.insert(0, '/app/runtime')
sys.path.insert(0, '/app/ditto-talkinghead')

def test_image_resolution():
    """Test how image resolution affects Ditto performance"""
    print("\n" + "="*70)
    print("TEST 1: IMAGE RESOLUTION IMPACT ON DITTO PERFORMANCE")
    print("="*70)
    
    from PIL import Image
    import numpy as np
    
    test_images = [
        ("bruce_haircut.jpg", "original", None),
        ("bruce_haircut.jpg", "1024x1024", (1024, 1024)),
        ("bruce_haircut.jpg", "512x512", (512, 512)),
    ]
    
    for img_path, label, target_size in test_images:
        if not os.path.exists(img_path):
            print(f"❌ Image not found: {img_path}")
            continue
            
        # Load and optionally resize
        img = Image.open(img_path)
        original_size = img.size
        
        if target_size:
            # Resize maintaining aspect ratio
            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            resized_path = f"temp_{label}_{img_path}"
            img.save(resized_path, quality=95)
            test_path = resized_path
        else:
            test_path = img_path
        
        img_size = img.size
        file_size = os.path.getsize(test_path) / 1024  # KB
        
        print(f"\n📸 Testing: {label}")
        print(f"   Original: {original_size}, Current: {img_size}")
        print(f"   File size: {file_size:.1f} KB")
        
        # Clean up temp file
        if target_size and os.path.exists(resized_path):
            os.remove(resized_path)


def test_faster_whisper():
    """Test Faster-Whisper ASR with CUDA 12"""
    print("\n" + "="*70)
    print("TEST 2: FASTER-WHISPER ASR (CUDA 12)")
    print("="*70)
    
    try:
        from models.asr import ASRModel
        
        print("\n🎤 Initializing Faster-Whisper ASR...")
        asr = ASRModel(device="cuda")
        asr.initialize(model_size="base")
        
        # Test audio files
        test_audios = [
            "bruce_expressive_motion_21s.mp3",
            "bruce_expressive_motion_41s.mp3"
        ]
        
        for audio_path in test_audios:
            if not os.path.exists(audio_path):
                # Try in ditto-talkinghead directory
                audio_path = f"/home/brucegarro/ditto-talkinghead/{audio_path}"
                if not os.path.exists(audio_path):
                    print(f"⚠️  Audio not found: {audio_path}")
                    continue
            
            print(f"\n🔊 Transcribing: {os.path.basename(audio_path)}")
            start = time.time()
            
            result = asr.transcribe(audio_path)
            
            elapsed = time.time() - start
            audio_duration = result.get('duration', 0)
            rtf = elapsed / audio_duration if audio_duration > 0 else 0
            
            print(f"✅ Transcription complete in {elapsed:.2f}s")
            print(f"   Audio duration: {audio_duration:.2f}s")
            print(f"   RTF: {rtf:.3f}x (lower is better)")
            print(f"   Text: {result['text'][:100]}...")
            
            if rtf < 0.3:
                print(f"   🚀 EXCELLENT! Real-time capable (<0.3x RTF)")
            elif rtf < 1.0:
                print(f"   ✅ GOOD! Faster than real-time")
            else:
                print(f"   ⚠️  Slower than real-time")
                
    except Exception as e:
        print(f"❌ ASR test failed: {e}")
        import traceback
        traceback.print_exc()


def test_tts_interesting_scripts():
    """Test TTS with interesting, varied content"""
    print("\n" + "="*70)
    print("TEST 3: TTS WITH INTERESTING SCRIPTS")
    print("="*70)
    
    test_scripts = [
        {
            "name": "Tech Explanation",
            "text": "We're using a streaming architecture that processes audio in real-time. "
                   "The system transcribes speech in under 200 milliseconds, generates a response, "
                   "and synthesizes audio at 10 times faster than real-time. This enables natural conversations."
        },
        {
            "name": "Storytelling",
            "text": "I remember standing on that boat, watching the sun set over the water. "
                   "The waves were gentle, the air was warm, and for a moment, everything felt perfect. "
                   "It's funny how certain memories stay with you forever."
        },
        {
            "name": "Technical Demo",
            "text": "This avatar uses CUDA 12 acceleration on an L4 GPU. We've optimized the diffusion model "
                   "to generate 25 frames per second with only 10 diffusion steps. The result? "
                   "Three times faster than our baseline."
        },
        {
            "name": "Casual Chat",
            "text": "Hey! So I've been thinking about how we could make this even faster. "
                   "Maybe we could try TensorRT optimization next? That could give us another 2x speedup. "
                   "What do you think?"
        }
    ]
    
    try:
        from models.tts import TTSModel
        
        print("\n🔊 Initializing XTTS-v2 TTS...")
        tts = TTSModel(device="cuda")
        tts.initialize()
        
        for i, script in enumerate(test_scripts, 1):
            print(f"\n📝 Script {i}/{len(test_scripts)}: {script['name']}")
            print(f"   Text: {script['text'][:80]}...")
            
            start = time.time()
            output_path = f"test_tts_{i}_{script['name'].replace(' ', '_').lower()}.wav"
            
            result = tts.synthesize(
                text=script['text'],
                output_path=output_path
            )
            
            elapsed = time.time() - start
            
            # Get audio duration
            import soundfile as sf
            audio, sr = sf.read(output_path)
            audio_duration = len(audio) / sr
            rtf = elapsed / audio_duration if audio_duration > 0 else 0
            
            print(f"✅ Synthesis complete in {elapsed:.2f}s")
            print(f"   Audio duration: {audio_duration:.2f}s")
            print(f"   RTF: {rtf:.3f}x")
            
            if rtf < 0.2:
                print(f"   🚀 BLAZING FAST! (<0.2x RTF)")
            elif rtf < 1.0:
                print(f"   ✅ Faster than real-time")
            else:
                print(f"   ⚠️  Could be faster")
                
    except Exception as e:
        print(f"❌ TTS test failed: {e}")
        import traceback
        traceback.print_exc()


def test_ditto_with_optimized_images():
    """Test Ditto video generation with different image sizes"""
    print("\n" + "="*70)
    print("TEST 4: DITTO VIDEO GENERATION - RESOLUTION COMPARISON")
    print("="*70)
    
    try:
        from models.ditto_model import DittoModel
        from PIL import Image
        
        print("\n🎬 Initializing Ditto model...")
        ditto = DittoModel(device="cuda")
        ditto.initialize()
        
        # Create different resolution versions
        base_image = "bruce_on_a_boat.jpg"
        test_configs = [
            ("original", None),
            ("1024x", (1024, 1024)),
            ("512x", (512, 512)),
        ]
        
        test_audio = "test_tts_1_tech_explanation.wav"
        if not os.path.exists(test_audio):
            print(f"⚠️  Test audio not found: {test_audio}")
            print("   Run TTS test first to generate test audio")
            return
        
        for label, target_size in test_configs:
            print(f"\n📸 Testing {label} resolution...")
            
            # Prepare image
            img = Image.open(base_image)
            original_size = img.size
            
            if target_size:
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
                test_image = f"temp_{label}_{base_image}"
                img.save(test_image, quality=95)
            else:
                test_image = base_image
            
            img_size = img.size
            file_size = os.path.getsize(test_image) / 1024
            
            print(f"   Image: {img_size}, {file_size:.1f} KB")
            
            # Generate video
            start = time.time()
            output_video = f"test_ditto_{label}.mp4"
            
            result = ditto.generate_video(
                audio_path=test_audio,
                image_path=test_image,
                output_path=output_video
            )
            
            elapsed = time.time() - start
            
            # Get video duration
            import soundfile as sf
            audio, sr = sf.read(test_audio)
            audio_duration = len(audio) / sr
            rtf = elapsed / audio_duration
            
            print(f"✅ Video generated in {elapsed:.2f}s")
            print(f"   Audio duration: {audio_duration:.2f}s")
            print(f"   RTF: {rtf:.2f}x realtime")
            print(f"   Output: {output_video}")
            
            # Clean up temp image
            if target_size and os.path.exists(test_image):
                os.remove(test_image)
                
    except Exception as e:
        print(f"❌ Ditto test failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("="*70)
    print("PHASE 2 PERFORMANCE TESTING")
    print("Testing: Faster-Whisper ASR, TTS, Ditto with image optimization")
    print("="*70)
    
    # Stay in /app directory where files are copied
    # os.chdir is not needed
    
    # Run tests
    try:
        test_image_resolution()
    except Exception as e:
        print(f"Image resolution test error: {e}")
    
    try:
        test_faster_whisper()
    except Exception as e:
        print(f"ASR test error: {e}")
    
    try:
        test_tts_interesting_scripts()
    except Exception as e:
        print(f"TTS test error: {e}")
    
    try:
        test_ditto_with_optimized_images()
    except Exception as e:
        print(f"Ditto test error: {e}")
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETE!")
    print("="*70)


if __name__ == "__main__":
    main()
