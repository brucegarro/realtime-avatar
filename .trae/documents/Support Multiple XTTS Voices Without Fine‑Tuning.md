## Short Answer
- No separate models needed. XTTS supports multiple speakers via per‑speaker reference samples (embeddings). Fine‑tuning per person is optional for higher fidelity and robustness.

## Approach Options
- Zero‑shot/embedding: Single XTTS model + per‑speaker WAVs → compute speaker embedding per request or cache.
- Optional fine‑tune: Train per‑speaker checkpoints if you have ~30–60 min of clean, transcribed speech. Load the chosen checkpoint by voice ID.

## Implement Multiple Voices (No Training)
### Assets
- Record 20–60s clean speech for each person → `assets/voice/reference_samples/<voice_id>.wav` (mono, 16 kHz).

### Backend API
- Use existing params:
  - `POST /api/v1/speak` and `POST /api/v1/generate` already accept `voice_sample` (see ScriptRequest field `voice_sample`).
- Extend conversation endpoints to accept voice:
  - Add `voice_sample` (or `voice_id`) to `/api/v1/conversation` and streaming endpoints.
  - Pass through to Phase1/Conversation pipeline → `tts_client` sends `speaker_wav` to GPU service.

### GPU Service (XTTS)
- Accept `speaker_wav` per request (current logs show this works).
- Add caching: first call computes embedding, cache in memory keyed by `voice_id` to cut 100–300ms per request.

### Web UI
- Add a voice selector (dropdown): `voice_id` values mapped to sample file names.
- Include selected `voice_id` in API calls.

### Validation
- Per voice: run `/api/v1/speak` and `/api/v1/generate` with `voice_sample` set; check timbre consistency and language coverage (EN/ZH/ES).
- Measure per‑voice latency and cache hits.

## Optional Fine‑Tuning Plan (If Needed)
- Data: 30–60 min clean speech per person + transcripts.
- Train XTTS speaker on GPU → produce per‑speaker checkpoint.
- Load checkpoint based on `voice_id` in GPU service; expose `model_id` parameter.
- Compare quality vs reference‑sample approach; keep both paths available.

## Rollout
1) Add reference WAVs for Person‑A and Person‑B.
2) Expose `voice_sample` on conversation endpoints and propagate to TTS.
3) Add voice selector to the web UI.
4) Implement embedding cache in GPU service.
5) Validate latency/quality; iterate on samples.

Confirm and I’ll implement the API parameter, GPU embedding cache, and the web UI voice selector.