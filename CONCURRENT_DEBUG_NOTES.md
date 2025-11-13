# Concurrent Workers Debug Session - Nov 12, 2025

## Problem Identified

**ASR model initialization hangs** when called in concurrent context.

## Root Cause

The `ASRModel` (Faster-Whisper) has initialization issues when:
1. Called after TTS in the same process
2. Multiple instances attempted  
3. In multi-threaded context

## Fix Applied

Removed ASR from `ConcurrentVideoGenerator.initialize()` since:
- ASR is not used in our pipeline (TTS generates audio, Ditto uses it)
- Sequential benchmark loads it but never calls it
- Removing it eliminates the hang

## Current Status

- ✅ Sequential baseline: 6.29x RTF (stable)
- ⚠️ Concurrent test still not completing successfully
- Issue appears to be in Ditto model loading with multiple instances

## Next Debugging Steps

### 1. Test Single Ditto Instance
Try loading just one Ditto model after TTS to isolate the issue:
```python
tts = XTTSModel()
tts.initialize()
# This works ^

ditto1 = DittoModel()
# Does this work after TTS?
```

### 2. Test Multiple Ditto Sequential
Try loading 2-3 Ditto models sequentially (not in threads):
```python
ditto1 = DittoModel()
ditto2 = DittoModel()
# Do multiple instances work?
```

### 3. Check CUDA Context Issues
Ditto may have issues with:
- Shared CUDA context across threads
- Model loading race conditions  
- Memory allocation conflicts

### 4. Try ProcessPoolExecutor Instead
ThreadPoolExecutor may have issues with CUDA models:
```python
from concurrent.futures import ProcessPoolExecutor
# Each process gets its own CUDA context
```

### 5. Simplify: No ThreadPool
Try manual queue without ThreadPoolExecutor:
- Single thread pulls from queue
- Processes jobs with multiple Ditto instances
- Simpler but less concurrent

## Alternative: Skip Concurrent, Focus on Optimization

Given time spent debugging, may be more productive to:
1. Implement Ditto FP16 quantization (2-4x speedup)
2. Lower resolution inference (1.5-2x speedup)
3. Combined: 3-8x improvement → may hit <1.0x RTF goal

**Benefit**: Direct path to goal without multi-threading complexity

## Recommendation

**Switch to Option 2 (Ditto Optimization)** because:
- Clear path to 6x improvement needed
- Less complexity than debugging threading
- FP16 quantization is well-documented
- Can always return to concurrent later

Would deliver:
- Current: 6.29x RTF
- With FP16 (2x): 3.15x RTF  
- With FP16 + resolution (4x): 1.57x RTF
- With FP16 + resolution + other opts (6x): **1.05x RTF** ✅ Close to goal!
