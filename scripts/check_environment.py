#!/usr/bin/env python3
"""
Simple test script to verify environment setup
Run this before building Docker images
"""
import sys
import subprocess


def check_command(cmd, name):
    """Check if command exists"""
    try:
        result = subprocess.run(
            [cmd, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"✅ {name}: Found")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print(f"❌ {name}: Not found")
        return False


def check_python_package(package, import_name=None):
    """Check if Python package is installed"""
    if import_name is None:
        import_name = package
    
    try:
        __import__(import_name)
        print(f"✅ Python package '{package}': Installed")
        return True
    except ImportError:
        print(f"⚠️  Python package '{package}': Not installed (will be installed in Docker)")
        return True  # Not critical for pre-Docker check


def main():
    print("=== Realtime Avatar Environment Check ===\n")
    
    all_ok = True
    
    print("Checking system commands:")
    all_ok &= check_command('docker', 'Docker')
    all_ok &= check_command('ffmpeg', 'FFmpeg')
    
    # Check Docker Compose (can be 'docker-compose' or 'docker compose')
    has_compose = False
    try:
        subprocess.run(['docker', 'compose', 'version'], capture_output=True, timeout=5)
        print("✅ Docker Compose: Found (docker compose)")
        has_compose = True
    except:
        try:
            subprocess.run(['docker-compose', '--version'], capture_output=True, timeout=5)
            print("✅ Docker Compose: Found (docker-compose)")
            has_compose = True
        except:
            print("❌ Docker Compose: Not found")
            all_ok = False
    
    print("\nChecking Python environment:")
    print(f"Python version: {sys.version}")
    
    # These are nice to have but not required (will be in Docker)
    check_python_package('torch', 'torch')
    check_python_package('fastapi', 'fastapi')
    check_python_package('TTS', 'TTS')
    
    print("\nChecking project structure:")
    import os
    
    required_dirs = [
        'assets/images',
        'assets/videos',
        'assets/voice/reference_samples',
        'runtime',
        'evaluator',
        'scripts'
    ]
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}: Exists")
        else:
            print(f"❌ {dir_path}: Missing")
            all_ok = False
    
    print("\nChecking assets:")
    
    # Check images
    image_files = ['bruce_neutral.jpg', 'bruce_smiling.jpg']
    for img in image_files:
        path = os.path.join('assets/images', img)
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024  # KB
            print(f"✅ {img}: {size:.0f} KB")
        else:
            print(f"❌ {img}: Missing")
            all_ok = False
    
    # Check videos
    video_files = ['bruce_english.mp4', 'bruce_mandarin.mp4', 'bruce_spanish.mp4']
    for vid in video_files:
        path = os.path.join('assets/videos', vid)
        if os.path.exists(path):
            size = os.path.getsize(path) / (1024 * 1024)  # MB
            print(f"✅ {vid}: {size:.0f} MB")
        else:
            print(f"❌ {vid}: Missing")
            all_ok = False
    
    # Check voice samples
    voice_files = ['bruce_en_sample.wav', 'bruce_zh_sample.wav', 'bruce_es_sample.wav']
    any_voice = False
    for voice in voice_files:
        path = os.path.join('assets/voice/reference_samples', voice)
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024  # KB
            print(f"✅ {voice}: {size:.0f} KB")
            any_voice = True
        else:
            print(f"⚠️  {voice}: Not yet extracted")
    
    if not any_voice:
        print("\n⚠️  Voice samples not extracted. Run: ./scripts/extract_voice_samples.sh")
    
    print("\n" + "="*50)
    if all_ok and any_voice:
        print("✅ Environment check PASSED - Ready to build!")
        print("\nNext steps:")
        print("  1. Build Docker images: ./scripts/build_images.sh")
        print("  2. Start runtime: docker compose up runtime")
        return 0
    elif all_ok:
        print("⚠️  Environment check PASSED but voice samples missing")
        print("\nNext steps:")
        print("  1. Extract voice samples: ./scripts/extract_voice_samples.sh")
        print("  2. Build Docker images: ./scripts/build_images.sh")
        print("  3. Start runtime: docker compose up runtime")
        return 0
    else:
        print("❌ Environment check FAILED - Please fix issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
