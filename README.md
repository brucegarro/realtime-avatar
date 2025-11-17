# Realtime Avatar: Interactive Conversational Avatar

Full-stack conversational AI avatar with voice input, intelligent responses, and realistic video synthesis.

## 🎯 Overview

**Status:** Phase 4 Complete ✅ | **Performance:** ~35-40s per conversation turn

An end-to-end conversational avatar that:
- 🎤 Listens to **voice input** (Whisper large-v3 ASR)
- 🧠 Responds intelligently (Qwen-2.5-7B LLM)
- 🗣️ Speaks in **cloned voice** (XTTS-v2 TTS)
- 🎭 Animates from **single photo** (Ditto + TensorRT)
- ⚡ **2x RTF video** generation (TensorRT acceleration)
- 🌐 **Web UI** with push-to-talk interface
- 🔧 Hybrid deployment: Local web + Cloud GPU backend

## 🚀 Latest Performance (Nov 16, 2025)

**Full Conversation Pipeline:** Voice input → AI response → Video output

| Component | Performance | Time (17s audio) |
|-----------|-------------|------------------|
| ASR (Whisper) | Real-time | ~2s |
| LLM (Qwen-2.5) | Streaming | ~5s |
| TTS (XTTS-v2) | **0.70x RTF** | ~12s |
| Video (Ditto TRT) | **1.23x RTF** | ~21s |
| **Total Pipeline** | End-to-end | **~35-40s** |

**Key Metrics:**
- Interactive conversation: ~35-40s per turn
- TensorRT video: 2.5x faster than PyTorch
- GPU memory: 12GB used (L4 has 24GB)
- Web UI: Push-to-talk, real-time feedback

📊 [Detailed benchmarks →](PERFORMANCE.md)

## 🏗️ Architecture

**Phase 4: Full Conversation System**

```
User Voice Input → ASR → LLM → TTS → Video Synthesis → Avatar Response
     (Web UI)    Whisper  Qwen  XTTS     Ditto TRT      (Playback)
```

**Components:**
- **ASR:** Whisper large-v3 (multilingual transcription)
- **LLM:** Qwen-2.5-7B (intelligent conversation)
- **TTS:** XTTS-v2 (voice cloning, EN/ZH/ES)
- **Video:** Ditto + TensorRT (audio-driven animation)
- **Web:** Nginx + vanilla JS (push-to-talk interface)

**Deployment:**
- **Local:** Web UI on Mac (Nginx container)
- **Cloud:** Backend on GCP L4 GPU (Docker containers)
- **Hybrid:** Local frontend → Cloud backend over HTTP

📖 [Complete deployment guide →](DEPLOYMENT.md)

## 🚀 Quick Start

### One-Command Deployment

```bash
# Deploy everything (backend + web UI)
./deploy_phase4_hybrid.sh

# Open web interface
open http://localhost:8080
```

This script will:
1. Create/start GCP L4 GPU instance
2. Install Docker + NVIDIA drivers
3. Build and start backend containers
4. Configure and start local web UI

**That's it!** Start having conversations with your avatar.

📖 [Detailed deployment guide →](DEPLOYMENT.md)

### Manual Quick Start

**1. Deploy Backend to GCP:**
```bash
# Create L4 instance
gcloud compute instances create realtime-avatar-test \
  --zone=us-east1-c --machine-type=g2-standard-4 \
  --accelerator=type=nvidia-l4,count=1 \
  --boot-disk-size=100GB

# Deploy (see DEPLOYMENT.md for full steps)
```

**2. Start Web UI Locally:**
```bash
cd web
./configure_web.sh <INSTANCE_IP>
docker compose up -d
open http://localhost:8080
```

**3. Have a Conversation:**
- Click "Start Recording"
- Speak your message
- Click "Stop Recording"  
- Wait ~35-40s for avatar response
- Video plays automatically

## 📊 API Examples

**Full Conversation (Voice → Video):**
```bash
# Record audio, get avatar video response
curl -X POST http://INSTANCE_IP:8000/api/v1/conversation \
  -F "audio=@my_question.wav" \
  --output avatar_response.mp4
```

**Individual Components:**

```bash
# Transcribe audio
curl -X POST http://INSTANCE_IP:8000/api/v1/transcribe \
  -F "audio=@audio.wav"
# → {"text": "Hello, how are you?", "language": "en"}

# Chat (text → text)
curl -X POST http://INSTANCE_IP:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about yourself"}'
# → {"response": "I'm an AI assistant..."}

# Generate speech (text → audio)  
curl -X POST http://INSTANCE_IP:8000/api/v1/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world!", "language": "en"}' \
  --output speech.wav

# Generate video (audio → video)
curl -X POST http://INSTANCE_IP:8000/api/v1/animate \
  -F "audio=@speech.wav" \
  --output video.mp4
```

## 🎨 Features

**Phase 4 (Current):**
- ✅ Voice input with Whisper ASR
- ✅ Intelligent conversation with Qwen-2.5
- ✅ Voice cloning with XTTS-v2
- ✅ Video synthesis with Ditto TensorRT
- ✅ Web UI with push-to-talk
- ✅ Hybrid deployment model

**Phase 3:**
- ✅ TensorRT optimization (2.5x speedup)
- ✅ 2x RTF video generation
- ✅ Concurrent worker support

**Phase 2:**
- ✅ XTTS-v2 voice cloning
- ✅ Multilingual support (EN/ZH/ES)

**Phase 1:**
- ✅ Ditto avatar model integration
- ✅ Single photo animation

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | **Complete deployment guide** (start here) |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Current phase & achievements |
| [PERFORMANCE.md](PERFORMANCE.md) | Detailed benchmarks |
| [SETUP.md](SETUP.md) | Environment setup |

## 🛠️ Development

**Requirements:**
- Python 3.10+ (GPU service) / 3.11+ (runtime)
- Docker & Docker Compose
- NVIDIA GPU (L4, A100, or similar)
- 100GB+ disk space
- 12GB+ GPU memory

**Local Development:**
```bash
# Setup environment
cd runtime
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start GPU service
./run_gpu_service.sh &

# Start runtime
uvicorn app:app --reload

# Start web UI
cd ../web
docker compose up -d
```

**Testing:**
```bash
# Run API tests
pytest tests/

# Run benchmarks
python benchmark_simple.py

# Run evaluator
cd evaluator
python run_evaluator.py
```

## 💰 Cost Estimate

**GCP L4 GPU (g2-standard-4):**
- **Running:** ~$0.80/hour
- **Stopped:** ~$16/month (disk only)
- **Monthly (24/7):** ~$600/month
- **Monthly (8hrs/day):** ~$200/month

**Optimization Tips:**
- Stop instance when not in use
- Use preemptible instances for testing
- Consider Cloud Run GPU for auto-scaling

## 🚧 Known Limitations

- First model load takes 30-60s (cold start)
- ~35-40s per conversation turn (optimization ongoing)
- Single concurrent user per instance
- Requires GPU with 12GB+ VRAM
- English works best, CJK languages experimental

## 🔮 Roadmap

**Near-term:**
- [ ] WebSocket streaming (reduce latency)
- [ ] Voice activity detection (hands-free)
- [ ] Multi-user support
- [ ] Cloud Run GPU deployment

**Future:**
- [ ] Real-time streaming (<5s latency)
- [ ] Custom avatar training
- [ ] Emotion detection & expression
- [ ] Multi-modal input (text + voice)

## 📄 License

MIT License - see LICENSE file

## 🙏 Acknowledgments

Built with:
- [Ditto](https://github.com/hkchengrex/Ditto) - Audio-driven video synthesis
- [XTTS-v2](https://github.com/coqui-ai/TTS) - Voice cloning
- [Whisper](https://github.com/openai/whisper) - Speech recognition
- [Qwen](https://github.com/QwenLM/Qwen) - Language model
- [TensorRT](https://developer.nvidia.com/tensorrt) - GPU acceleration

---

**Status:** Phase 4 Complete ✅  
**Last Updated:** November 16, 2025  
**Performance:** ~35-40s per conversation turn

**Generate Spanish video:**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "¡Hola mundo!", "language": "es"}'
```

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **TTS** | XTTS-v2 (multilingual voice cloning) |
| **Avatar** | Ditto + TensorRT (audio-driven animation) |
| **ASR** | Faster-Whisper (Phase 3) |
| **API** | FastAPI (Python async) |
| **Deployment** | Docker + GCP L4 GPU |

## 📂 Key Files

- `runtime/app.py` - FastAPI application
- `runtime/models/tts.py` - XTTS-v2 voice cloning
- `runtime/models/ditto_model.py` - Ditto avatar with TensorRT
- `runtime/gpu_service.py` - GPU acceleration service
- `runtime/pipelines/phase1_script.py` - Text → video pipeline
- `evaluator/run_evaluator.py` - Automated testing

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Complete setup guide (local + GCP)
- **[PERFORMANCE.md](PERFORMANCE.md)** - Benchmarks and optimization
- **[PROJECT_STATUS.md](PROJECT_STATUS.md)** - Current development status
- **[docs/TENSORRT_SETUP.md](docs/TENSORRT_SETUP.md)** - TensorRT installation

## 🎯 Development Roadmap

- ✅ **Phase 1:** Script → video (GPU accelerated)
- ✅ **Phase 2:** Voice cloning + optimization
- ✅ **Phase 3:** TensorRT (2.5x speedup)
- 📅 **Phase 4:** Semi-interactive chat
- 📅 **Phase 5:** Real-time WebRTC streaming

---

**Last Updated:** November 16, 2025 | **Status:** Phase 3 Complete ✅
