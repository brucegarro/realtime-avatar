# Streaming Implementation - Resolved Issues

**Date:** November 24, 2025  
**Status:** ✅ All Issues Resolved

## Historical Context

This document previously tracked streaming video issues. All issues have been resolved through:
1. **HTTP/2 Migration** - Eliminated connection limit bottlenecks
2. **Intelligent Chunking** - Optimized chunk sizes for smooth playback

## What Was Fixed

### Issue 1: First Chunk 9+ Second Delay ✅ RESOLVED
- **Problem:** First video chunk took 9.2 seconds to load despite fast backend
- **Root Cause:** HTTP/1.1 connection limit (6 per domain) + SSE holding 1 connection
- **Solution:** Migrated to HTTP/2 for unlimited multiplexed streams
- **Result:** First chunk now loads in 0.17s (54x improvement)
- **Documentation:** See [HTTP2_MIGRATION.md](./HTTP2_MIGRATION.md)

### Issue 2: Long Video Chunks (33+ seconds) ✅ RESOLVED
- **Problem:** Text chunking didn't split on semicolons, creating huge chunks
- **Root Cause:** Regex only split on `.!?`, missed `;` in poetry/prose
- **Solution:** Enhanced splitting logic with semicolons and 120-char limit
- **Result:** Consistent 8-10s video chunks
- **Documentation:** See [STREAMING_OPTIMIZATION.md](./STREAMING_OPTIMIZATION.md)

### Issue 3: Playback Stops After First Chunk ✅ RESOLVED
- **Problem:** Video queue playback loop exited when queue temporarily empty
- **Root Cause:** Loop condition `while (queue.length > 0)` didn't wait for more chunks
- **Solution:** Added `isStreamComplete` flag and wait logic
- **Result:** 100% chunk playback completion
- **Documentation:** See [STREAMING_OPTIMIZATION.md](./STREAMING_OPTIMIZATION.md)

### Issue 4: Video Download Stalls ✅ RESOLVED
- **Problem:** Browser reported "video download stalled" warnings
- **Root Cause:** HTTP/1.1 connection limits caused request queuing
- **Solution:** HTTP/2 eliminated connection bottleneck
- **Result:** No more stall warnings, consistent fast loads

## Current Performance

All metrics are now excellent:

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| First chunk load | <1s | 0.17s | ✅ |
| Subsequent chunks | <0.5s | 0.14-0.21s | ✅ |
| Chunk duration | 8-10s | 8-10s | ✅ |
| Playback gaps | <3s | 0-2s | ✅ |
| Completion rate | 100% | 100% | ✅ |

## References

For current implementation details, see:
- [STREAMING_OPTIMIZATION.md](./STREAMING_OPTIMIZATION.md) - Complete optimization guide
- [HTTP2_MIGRATION.md](./HTTP2_MIGRATION.md) - HTTP/2 migration details
- [PERFORMANCE.md](../PERFORMANCE.md) - Performance benchmarks

---

**This document is kept for historical reference. All issues are resolved.**
// In frontend, when chunk N arrives:
1. Add chunk N to queue
2. If chunk N+1 is already known, create hidden <video> element
3. Preload chunk N+1 in background
4. When chunk N finishes, swap to preloaded element

Benefits:
- Masks download time with playback time
- User never waits for download after first chunk
- Browser can use full bandwidth during playback

Tradeoffs:
- More complex state management
- Need to handle preload failures
- Memory overhead (2 video elements)
```

**Estimated complexity:** Medium (2-3 hours)
**Impact:** High - should eliminate most stalls after first chunk

---

### Solution 2: Adaptive Video Quality
**Concept:** Serve lower resolution/bitrate videos for faster delivery

**Implementation:**
```python
# Backend: Generate multiple qualities
- High quality: 512x512, 2Mbps (current)
- Medium quality: 384x384, 1Mbps
- Low quality: 256x256, 512kbps

# Frontend: Detect connection speed
if (navigator.connection.downlink < 2) {
    quality = 'low';
}

# Backend serves appropriate quality
return FileResponse(f"{job_id}_{quality}.mp4")
```

**Estimated complexity:** High (1-2 days for backend changes)
**Impact:** High - smaller files = faster downloads

---

### Solution 3: Video Chunk Compression
**Concept:** Reduce video file size without quality loss

**Implementation:**
```bash
# Current: Ditto generates videos with default settings
# Optimize with ffmpeg post-processing:

ffmpeg -i input.mp4 \
  -c:v libx264 \
  -preset fast \
  -crf 23 \
  -movflags +faststart \
  output.mp4

Flags:
- crf 23: Slightly higher compression
- faststart: Moves moov atom to beginning for streaming
- preset fast: Balance quality vs speed
```

**Estimated complexity:** Low (30 mins)
**Impact:** Medium - 20-30% file size reduction

---

### Solution 4: Range Request Optimization
**Concept:** Enable partial content downloads for better streaming

**Implementation:**
```python
# Backend: Support Range requests properly
from fastapi.responses import FileResponse
import os

@app.get("/api/v1/videos/{filename}")
async def get_video(filename: str, request: Request):
    file_path = os.path.join("/tmp/gpu-service-output", filename)
    
    # Check for Range header
    range_header = request.headers.get("range")
    
    if range_header:
        # Parse range and return partial content
        return StreamingResponse(
            file_iterator(file_path, range_header),
            status_code=206,
            headers={
                "Content-Range": f"bytes {start}-{end}/{size}",
                "Accept-Ranges": "bytes",
            }
        )
    
    return FileResponse(file_path)
```

**Estimated complexity:** Medium (1-2 hours)
**Impact:** Medium - better browser buffering, faster initial playback

---

### Solution 5: CDN/Edge Caching
**Concept:** Cache video chunks closer to user

**Implementation:**
```
Options:
1. GCP Cloud CDN (easy integration)
2. Cloudflare in front of GCP
3. S3 + CloudFront

Trade-off: Adds latency for first user, but helps if videos reused
```

**Estimated complexity:** Medium (depends on infrastructure)
**Impact:** Low for single user, High for multiple users

---

### Solution 6: WebRTC Data Channel
**Concept:** Use WebRTC for faster peer-to-peer video delivery

**Implementation:**
```javascript
// Frontend initiates WebRTC connection
// Backend pushes video chunks over data channel
// Bypasses HTTP overhead

Benefits:
- Lower latency than HTTP
- Better for real-time streaming
- Can prioritize video data

Tradeoffs:
- Complex implementation
- Requires STUN/TURN servers
- More moving parts
```

**Estimated complexity:** Very High (3-5 days)
**Impact:** High - but may be overkill

---

### Solution 7: Fallback to Blob URL
**Concept:** Download entire video as blob, then play

**Implementation:**
```javascript
// Instead of direct video src:
async function loadVideoAsBlob(url) {
    const response = await fetch(url);
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    videoSource.src = blobUrl;
    avatarVideo.load();
    
    // Cleanup after playback
    avatarVideo.onended = () => {
        URL.revokeObjectURL(blobUrl);
    };
}

Benefits:
- Full control over download
- Can show progress bar
- Retry logic easier

Tradeoffs:
- Must download entire video before playing
- Higher memory usage
```

**Estimated complexity:** Low (1 hour)
**Impact:** Medium - trades download time for reliability

---

## Recommended Approach

**Phase 1 (Quick wins):**
1. **Video compression** (Solution 3) - 30 mins, immediate impact
2. **Blob URL fallback** (Solution 7) - 1 hour, improves reliability

**Phase 2 (Core fix):**
3. **Preloading strategy** (Solution 1) - 3 hours, best UX improvement

**Phase 3 (Optional optimization):**
4. **Adaptive quality** (Solution 2) - if users have slow connections
5. **Range requests** (Solution 4) - if compression isn't enough

## Testing Strategy

For each solution, measure:
- **TTFF** (time to first frame) - should be < 20s
- **Stall rate** - % of chunks that timeout
- **Total playback time** - all chunks should play smoothly
- **Network transfer** - MB downloaded per conversation

Target metrics:
- TTFF: < 15s (currently ~23s)
- Stall rate: < 5% (currently ~30-50%)
- Smooth playback: no gaps between chunks

## Video Optimization Deep Dive

### What is `faststart`?

`faststart` moves the MP4 moov atom (metadata) to the beginning of the file, enabling progressive playback. Without it, browsers must download the entire file before playing.

**Normal MP4:**
```
[ftyp][mdat: 99% of file][moov: metadata]
         ↑ Browser downloads all this before reading moov
```

**With faststart:**
```
[ftyp][moov: metadata][mdat: video data]
      ↑ Browser reads metadata immediately, plays while downloading
```

**Impact:** Instant playback start, eliminates download stalls

### Recommended Quick Wins

**1. Enable faststart (CRITICAL)**
```python
'-movflags', '+faststart'  # Progressive download
```
- Zero quality cost
- Eliminates most stalls
- 2-5s TTFF improvement

**2. Lower frame rate to 18 FPS**
```python
'-r', '18'  # Down from 25-30 FPS
```
- 40% faster generation
- 40% smaller files
- Talking heads look fine at 18 FPS

**3. Codec optimization**
```python
'-preset', 'veryfast',     # Faster encoding
'-profile:v', 'baseline',  # Max compatibility
'-crf', '28',              # Balanced quality/size
```
- 20-30% faster encoding
- 10-15% smaller files
- Better browser compatibility

**4. Audio optimization**
```python
'-ar', '24000',  # 24kHz (down from 48kHz)
'-ac', '1',      # Mono
'-b:a', '64k',   # 64kbps (down from 192kbps)
```
- 10-15% smaller files
- Speech quality preserved

### Full FFmpeg Command

```python
def optimize_video_for_streaming(input_path: str, output_path: str):
    """Optimize MP4 for web streaming"""
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        
        # Video optimization
        '-c:v', 'libx264',
        '-preset', 'veryfast',      # Fast encoding
        '-profile:v', 'baseline',   # Max compatibility
        '-level', '3.0',
        '-crf', '28',               # Balanced quality
        '-r', '18',                 # 18 FPS
        '-movflags', '+faststart',  # Progressive download ⭐
        
        # Audio optimization
        '-c:a', 'aac',
        '-ar', '24000',             # 24kHz
        '-ac', '1',                 # Mono
        '-b:a', '64k',              # 64kbps
        
        output_path
    ]
    subprocess.run(cmd, check=True)
```

### Expected Improvements

**Before optimizations:**
- Generation: 18s for 10s video (RTF: 1.8x)
- File size: ~5MB per chunk
- TTFF: ~23s
- Stall rate: 30-50%

**After quick wins:**
- Generation: ~10s for 10s video (RTF: 1.0x) 🎯
- File size: ~2.5MB per chunk (50% reduction)
- TTFF: ~8-10s (60% improvement)
- Stall rate: <5% (95% reduction)

### Optional Optimizations

**If still not fast enough:**
- Lower resolution to 384x512 (test quality first)
- Aggressive compression: CRF 30
- Shorter keyframe interval for better seeking

**Don't bother with:**
- H.265/VP9 codecs (slower encoding)
- Hardware encoding (limited L4 support)
- Adaptive bitrate (overkill for short chunks)

## Next Session Plan

1. **Implement video optimizations** (faststart + FPS + codec + audio)
2. **Deploy and test** stall rate improvement
3. **If needed:** Add blob URL fallback with progress tracking
4. **If needed:** Implement preloading strategy
