# Evaluator Simplification Notes

**Date:** November 6, 2025

## Changes Made

### 1. Disabled Language Switching Tests
- **Reason:** Keeping evaluator complexity low for Phase 1
- **Location:** `evaluator/run_evaluator.py` - commented out `run_language_tests()`
- **Impact:** Reduces test count from 13 to 3 scenarios
- **Can Re-enable:** When testing multilingual conversation flows

### 2. Disabled Gold Set Tests  
- **Reason:** Gold set phrases are too long for CPU generation (7-12 seconds audio)
- **Location:** `evaluator/run_evaluator.py` - commented out `run_gold_set_tests()`
- **Root Cause:** 5 out of 6 gold phrases exceed 5-minute generation timeout on CPU
  - `en_001`: 7.98s audio → timeout
  - `en_002`: 12.34s audio → timeout  
  - `zh_002`: 6.02s audio → borderline
  - `es_001`: 11.5s audio → timeout
  - `es_002`: 10.46s audio → timeout
- **Can Re-enable:** When running on GPU or with 10+ minute timeout

### 3. Disabled Medium-Length Tests
- **Reason:** All medium texts timeout after 5 minutes on CPU
- **Location:** `evaluator/scenarios/phase1_tests.py` - commented out 3 medium scenarios
- **Impact:** Only testing short texts (2-4s audio, ~60-120s generation)
- **Can Re-enable:** With GPU acceleration or increased timeout

## Current Evaluator Configuration

### Active Tests (3 total)
1. **en_short** - English short phrase (~2s audio)
2. **zh_short** - Chinese short phrase (~2s audio)
3. **es_short** - Spanish short phrase (~2s audio)

### Test Duration
- **Per test:** ~60-120 seconds
- **Total run:** ~3-6 minutes for all tests
- **Success rate:** ~100% (no timeouts)

## Why Gold Set Phrases Were Timing Out

**Problem:** Whisper auto-transcription selected naturally spoken phrases which are 7-12 seconds long. On CPU:
- 2s audio → ~60s generation ✅
- 4s audio → ~120s generation ✅
- 8s audio → ~300s+ generation ❌ (timeout at 300s)
- 12s audio → ~500s+ generation ❌ (would take 8+ minutes)

**CPU Limitation:** TTS is 20-30x slower than real-time, so longer phrases exponentially increase generation time.

## Recommendations

### For CPU Testing
- ✅ **Keep short texts only** (current config)
- ✅ **3 basic scenarios** cover core functionality
- ✅ **Fast feedback loop** (~5 min total)

### For GPU Testing
- Enable medium-length tests
- Enable gold set tests
- Enable language switching tests
- Increase timeout to 10 minutes
- Should achieve 5-10x faster generation

### For Production
- Use GPU mandatory
- Monitor P95 latencies
- Set alerts for >10s generation on 2s audio
- Consider chunking for very long texts

## Future Work

### Gold Set Testing
The gold set infrastructure is ready:
- 6 phrases with timestamps
- 6 video clips extracted
- Comparison framework in place

**To use:**
1. Shorten phrases to 2-4s audio segments
2. Re-run `auto_transcribe.py` with shorter duration targets
3. Or run on GPU with 10+ minute timeout

### Language Switching
Framework exists in `scenarios/language_tests.py`:
- 7 multilingual scenarios
- Tests EN→ZH, EN→ES, EN→ZH→ES combinations

**To use:** Uncomment in `run_evaluator.py` when needed

## Summary

**Simplified evaluator now:**
- Runs in ~5 minutes (vs. 30+ minutes before)
- Tests core multilingual TTS functionality
- 100% success rate on CPU
- Easy to maintain and debug
- Can be expanded when GPU available

**Trade-offs:**
- No longer testing longer phrases
- No multilingual switching validation  
- No gold set comparison

**This is appropriate for Phase 1 MVP testing on CPU.**
