 PROJECT_SPEC.md

## Project Name
**Realtime Avatar System**

## Overview
This project creates a **low-latency, conversational avatar** that resembles Bruce, speaks in Bruce’s cloned voice, and can interact in **English, Chinese, and Spanish**. The avatar will live as a **sub-route** (`/avatar`) on Bruce’s personal site and will scale to **zero cost when idle**. The project will evolve in phases, starting from script-based video generation and eventually reaching real-time, bidirectional audiovisual interaction.

This system prioritizes:
- **Responsiveness over video resolution**
- **Cost control**
- **Ease of iteration**
- **Model modularity**
- **Cloud Run GPU scale-to-zero**

---

## Development & Deployment Environments

| Environment | Purpose | Execution |
|---|---|---|
| **Local** | Model development + evaluator testing | `docker compose` w/ CPU inference and local models |
| **Production** | On-demand user sessions | **GCP Cloud Run GPU (L4)**, scales to **zero** when idle |

---

## High-Level Goals

1. Produce realistic avatar videos driven by a **single reference image**.
2. Clone Bruce’s voice using **XTTS-v2** (multilingual: EN/中文/ES).
3. Support **incremental development path**:
   - Phase 1: Script → Pre-rendered talking video
   - Phase 2: Semi-interactive chat (short response clips)
   - Phase 3: Full real-time streaming interaction (WebRTC)
4. Ensure system can run **locally** for development and **remotely** on GCP for production.
5. Cost remains **below $100/month**, ideally much lower, with usage-based GPU billing.

---

## Functional Requirements

### Core Capabilities
| Phase | Capability | Description |
|---|---|---|
| **1** | Script → MP4 Video | Generate a talking-head video from a text script using the avatar and XTTS-v2 |
| **2** | Semi-Interactive Chat | User sends text; avatar replies with generated short video clips |
| **3** | Real-Time Conversation | Live mic input → ASR → LLM → TTS → Avatar animation → WebRTC stream |


## Core Models (Initial Recommendations)

| Task | Model | Reason |
|---|---|---|
| **Avatar Animation** | **LivePortrait** | Best “single-image + natural micro-motion” performance; lower latency than SadTalker |
| **Voice Cloning (TTS)** | **XTTS-v2** | Multilingual, self-hostable, controllable; no vendor dependency |
| **ASR (speech → text)** | **faster-whisper (small or medium)** | Accurate, fast, multilingual, runs well on CPU |
| **LLM (brain)** | **Qwen-2.5-7B** (local) → upgrade to **Qwen-2.5-14B-INT4** (Cloud Run GPU) | Native multilingual support, strong alignment, efficient inference |
| **Realtime Transport (Phase 3)** | **WebRTC** | Standard for low-latency browser streaming |

> **Key principle:** **Latency > resolution.** Start at **256p–360p** for video output.

---

### Avatar Appearance Requirements
- Avatar **look** is defined primarily by **one high-quality, forward-facing image**.
- Optionally, a **20–60 second motion reference video** may be used to enhance natural micro-motions.
- Initial animation target: **256p–360p** video resolution for responsiveness and real-time viability.

### Voice Requirements
- Voice clone generated via **XTTS-v2**.
- Must support output in multiple languages (English, Mandarin, Spanish).
- Voice inference pipeline must be able to run:
  - Locally (CPU mode) during development
  - On GPU (Cloud Run) in production

### Multilingual Requirements
- Automatic or explicit language switching based on context.
- Later: optional manual language toggle in UI.

---

## Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Cost** | Must scale to zero when idle; GPU billed only during active sessions; monthly spend target **< $100** |
| **Latency** | Optimized for **short, timely responses**; real-time phase target ~450–900 ms |
| **Privacy** | No requirement to store audio or transcripts by default |
| **Deployment** | Use **Google Cloud Platform** only (Cloud Run GPU + Cloud Run Web + GCS) |
| **Development Environment** | Must support **local inference** mode on a MacBook Pro |
| **Infrastructure** | Use **Docker** for all components and **Terraform** for infrastructure provisioning |

---

## Evaluator Specification (Local Development Focus, v0.2)

### Purpose
During early development (Phase 1 & Phase 2), the evaluator should focus on **local inference behavior**, **functionality**, **voice correctness**, and **basic latency**.  
Networking, media streaming, cost, and real-time metrics will be re-enabled during Phase 3.

### Scope (Current Phase)
- **Local pipeline only**: Script → (LLM optional) → XTTS-v2 → LivePortrait → MP4 output
- Run repeatedly to measure **consistency, output stability, and latency trends**

### Test Scenarios
1) **EN short line** (1–2s sentence)
2) **ZH short line** (普通话)
3) **ES short line**
4) **Multilingual switch** (EN → ZH → ES)
5) **Longer utterance** (~8–12s)

### Metrics (Active Now)

| Category | Metric | Description |
|---|---|---|
| **Latency (Local)** | `tts_ms` | Text → audio generation time |
|  | `avatar_render_ms` | Audio → talking-head video generation time |
|  | `total_generation_ms` | End-to-end latency for a single output clip |
| **Voice Quality (Local)** | `speaker_similarity` (cosine 0–1) | Embedding similarity between output voice & reference voice |
|  | `f0_rmse_hz` | Pitch stability vs reference baseline |
| **Language Correctness** | `language_detected` | Output language classifier result vs expected (EN / ZH / ES) |
|  | `language_correctness_1_1` | 1 = correct language used, 0 = mismatch |
| **Lip Sync (Basic Heuristic)** | `lip_sync_coherence_0_1` | Simple frame-level mouth-open vs phoneme timing match (heuristic) |

### Output Format
Write one JSON file per test run to `evaluator/outputs/`:

```json
{
  "run_id": "2025-11-06T01:23:45Z_EN_short",
  "metrics": {
    "tts_ms": 242,
    "avatar_render_ms": 1040,
    "total_generation_ms": 1290,
    "speaker_similarity": 0.84,
    "f0_rmse_hz": 17.9,
    "language_detected": "EN",
    "language_correctness_1_1": 1,
    "lip_sync_coherence_0_1": 0.72
  }
}

### React UI (local) : HTTP
Runtime Service (CPU mode)
- XTTS-v2 local inference
- LivePortrait CPU mode or downscaled settings
- Optional Qwen local or stubbed responses

### Production (GCP)
Browser UI (React) : WebRTC / HTTPS
Cloud Run Web (CPU)
- Serves UI, handles signaling
- Routes requests

Cloud Run Runtime (GPU)
- faster-whisper (ASR)
- Qwen-2.5 LLM (7B or 14B INT4)
- XTTS-v2 (voice)
- LivePortrait (avatar animation)

Google Cloud Storage (GCS)
- reference image
- optional reference motion video
- cached generated assets