# EV — Local Jarvis-Style Voice AI Assistant

A local, voice-first AI assistant. You speak, it listens, thinks, and (soon)
speaks back — with a pipeline built so every stage can be swapped independently.

```
Mic Input → Wake Word → STT (faster-whisper) → LLM (Gemma 4 + tools) → TTS (streaming) → Speaker
```

**Milestone status**

| Stage | Module | Status |
|-------|--------|--------|
| 1. Audio input (wake word / push-to-talk) | `audio_input.py` | ✅ wired & verified |
| 2. STT (faster-whisper, local) | `stt.py` | ✅ wired & verified |
| 3. LLM + tool use (Gemma 4) | `llm.py`, `tools.py` | ✅ wired (validated with a mocked API — real-key smoke test pending) |
| 4. TTS (ElevenLabs / Piper) | `tts.py` | ✅ Piper wired (local, no key) |

Run `python main.py` (or `./run.sh`) for the working stage 1–3 loop: say
**"Hey Jarvis"** and then your request — EV answers via Gemma 4, with tool use.

---

## Setup

### 1. System audio dependencies

**macOS** — nothing. **Windows** — nothing (native WASAPI).

**Linux (desktop)** — install ALSA/Pulse:

```bash
sudo apt install -y libasound2t64 libasound2-plugins libportaudio2
```

**WSL2 (this project was developed on it)** — WSL2 exposes no sound cards;
audio routes through WSLg's PulseAudio daemon. Ubuntu's WSL2 image ships no
audio libraries at all, so run the rootless setup script (no sudo needed):

```bash
bash scripts/setup_wsl2_audio.sh
```

It downloads the audio .debs and extracts them into `~/.local/ev-audio`, which
`run.sh` points the process at. (With sudo you could instead run the
equivalent `apt install` line above — the script exists so no root is
required.) The Windows mic appears as `RDPSource`; the speaker as `RDPSink`.

### 2. Python environment

Requires **Python 3.10+** (tested on 3.14).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> On Linux, the default `pip install pynput` tries to build the `evdev` C
> extension. Under X11/WSLg you don't need it — use the pure-Python backend:
>
> ```bash
> .venv/bin/pip install --no-deps pynput python-xlib six
> ```

### 3. API keys

Copy `.env.example` to `.env` and fill in what you have:

```bash
cp .env.example .env
```

- `GOOGLE_API_KEY` — required for stage 3 (LLM) only, when
  `EV_LLM_PROVIDER=gemini`. Free tier: https://aistudio.google.com/apikey
  (15 req/min, 1500 req/day — more than enough for a voice assistant).
  No key is needed with `EV_LLM_PROVIDER=ollama` (local Ollama server).
- `ELEVENLABS_API_KEY` — required for stage 4 only if `EV_TTS_PROVIDER=elevenlabs`.
  The local `piper` fallback needs `EV_PIPER_VOICE_PATH` instead (download a
  voice from https://huggingface.co/rhasspy/piper-voices, e.g.
  `en/en_US/lessac/medium`).

Stages 1–2 work with **no keys at all** — the Whisper model downloads
automatically on first run (~75 MB for `tiny`, ~460 MB for the default
`small`).

---

## Running

```bash
# WSL2
./run.sh

# regular Linux / macOS / Windows
.venv/bin/python main.py
```

Controls:

- Say **"Hey Jarvis"** (the wake word) and then your request. EV listens until
  you stop speaking (~1s of silence ends the utterance).
- `EV_TRIGGER=ptt` restores hold-**SPACE**-to-talk mode.
- **Ctrl+C** to quit.

CLI:

```text
python main.py                    push-to-talk -> transcribe -> Gemma 4 (stages 1-3)
python main.py --text "hi EV"     skip the mic; send text straight to the LLM
python main.py --once             single utterance, then exit
python main.py transcribe         stages 1-2 only: just print what it hears
python main.py --list-devices     show audio devices and exit
```

On WSL2, set `EV_AUDIO_INPUT_DEVICE=RDPSource` if the default source isn't the
Windows mic:

```bash
./run.sh --list-devices      # find your input device name
EV_AUDIO_INPUT_DEVICE=RDPSource ./run.sh
```

## Stage 3: the brain (LLM + tools)

The LLM stage runs Gemma 4 through one of two providers (`EV_LLM_PROVIDER`):

- **`gemini`** (default) — Google AI Studio API, `gemma-4-31b-it` by default
  (`EV_LLM_MODEL`; any hosted `gemma-4-*` ID works). Requires `GOOGLE_API_KEY`.
- **`ollama`** — a local Ollama server's OpenAI-compatible endpoint
  (`http://localhost:11434`, `gemma4:e4b` by default). Fully offline; no key.

Personality lives in `persona.md` (or `EV_PERSONA_PROMPT` env var) — edit it
without touching code. Conversation history is a rolling in-memory window
(`EV_LLM_MAX_TURNS`).

Tools (all wired, safety-gated):

- **run_shell_command** — the command is echoed to the terminal before
  execution; commands outside `EV_SHELL_ALLOWLIST` prompt y/N first
  (`EV_CONFIRM_SHELL=ask|never|always`). stdout/stderr/exit code return to the
  model.
- **get_system_status** — time, memory, CPU, battery, active window/app
  (best-effort per OS; anything unobtainable reports `unavailable`).
- **web_search** — stub returning a placeholder; swap in a real backend in v2.

Multi-step tool use works: the model may call several tools per turn, each
result feeds back, until it produces a final answer. API failures (rate
limits, network, timeouts, malformed tool calls) print a clear error and the
loop continues to the next utterance. Gemini free-tier rate limits (HTTP 429)
are retried once with a 5s backoff.

---

## Configuration (`.env`)

Everything is config-driven, nothing is hardcoded:

| Variable | Default | Meaning |
|---|---|---|
| `EV_STT_MODEL` | `small` | whisper model: tiny/base/small/medium/large-v3 |
| `EV_STT_DEVICE` | `cpu` | `cpu` or `cuda` |
| `EV_STT_COMPUTE_TYPE` | `int8` | `int8` on CPU, `float16` on GPU |
| `EV_STT_LANGUAGE` | *(auto)* | force a language, e.g. `en` (recommended) |
| `EV_STT_VAD` | `false` | Silero VAD before transcription; `false` trusts the trigger's silence detection (Silero rejects the noisy RDP mic relay) |
| `EV_LLM_PROVIDER` | `gemini` | `gemini` (API) or `ollama` (local) |
| `EV_LLM_MODEL` | `gemma-4-31b-it` | hosted gemma ID, or ollama tag (`gemma4:e4b`, …) |
| `EV_GEMINI_THINKING` | `false` | enable HIGH thinking level (slower, deeper) |
| `EV_OLLAMA_BASE_URL` | `http://localhost:11434` | local Ollama endpoint |
| `EV_OLLAMA_MODEL` | `gemma4:e4b` | local model tag |
| `EV_LLM_MAX_TURNS` | `20` | rolling conversation window |
| `EV_PERSONA_FILE` | `persona.md` | personality/system prompt |
| `EV_TTS_PROVIDER` | `elevenlabs` | `elevenlabs` or `piper` |
| `EV_CONFIRM_SHELL` | `ask` | `ask` / `never` (refuse non-allowlisted) / `always` |
| `EV_SHELL_ALLOWLIST` | `ls,cat,head,...` | prefix allowlist for `run_shell_command` |
| `EV_TRIGGER` | `wakeword` | `wakeword` (default) or `ptt` |
| `EV_WAKE_WORDS` | `sara` | bundled openWakeWord models or .onnx paths |
| `EV_WAKE_WORD_WEIGHTS` | *(empty)* | custom trained classifier `.npz` (e.g. `./voices/sara_wake.npz`) — overrides the bundled models |
| `EV_WAKE_WORD_THRESHOLD` | `0.8` | higher = fewer false positives (0.3–0.7 bundled / 0.7–0.8 custom) |
| `EV_WAKE_GRACE_SECONDS` | `1.2` | pause allowed right after the wake word |
| `EV_WAKE_END_SILENCE_SECONDS` | `1.0` | silence this long ends the utterance |
| `EV_WAKE_PHRASES` | `sara` | leading phrase stripped from transcripts |
| `EV_PTT_KEY` | `space` | push-to-talk key (when `EV_TRIGGER=ptt`) |
| `EV_PRE_ROLL_SECONDS` | `0.3` | audio kept from before activation |
| `EV_LOG_LEVEL` | `INFO` | stage latency is logged here |

---

## Architecture & extension points

Each stage is a module with one entry point; swap them without touching
anything else:

- **`audio_input.py`** — `MicCapture` (continuous capture into a timestamped
  ring buffer, so triggers have zero start latency and pre-roll audio is
  available), `Trigger` ABC with `WakeWordTrigger` (openWakeWord, default) and
  `PushToTalk` (key hooks via pynput X11 / terminal toggle fallback).
- **`stt.py`** — `STTEngine.transcribe()` → `Transcription` (text, confidence,
  duration). Lazy model load.
- **`tools.py`** — `ToolRegistry` with `run_shell_command` (allowlist +
  confirmation), `get_system_status`, `web_search` (stub). Safety: any
  side-effect command outside the allowlist prompts (or is refused when
  `EV_CONFIRM_SHELL=never`).
- **`llm.py`** — `GeminiGemmaLLM` / `OllamaGemmaLLM` (pick via `build_llm()`);
  `stream_response()` yields tokens and runs the provider tool-calling loop
  internally; `Conversation` is a rolling in-memory window.
- **`tts.py`** — `TTSEngine` with `ElevenLabsTTS` and `PiperTTS`, plus
  `chunk_sentences()` — the seam for sentence-chunked streaming (start TTS on
  the first completed sentence, never wait for the full response).
- **`main.py`** — orchestration + CLI.
- **`wsl_bootstrap.py`** — WSL2-only: points the process at the rootless audio
  prefix (`~/.local/ev-audio`) and patches `ctypes.util.find_library` so
  sounddevice can find `libportaudio` outside the ldconfig cache.

### v2 roadmap (leave the seams open)

- **Wake-word tuning** — swap in custom-trained openWakeWord models via
  `EV_WAKE_WORDS`; tune `EV_WAKE_WORD_THRESHOLD` per room.
- **Barge-in** — capture already runs continuously; only the speak-stage
  scheduling in `main.py` needs work.
- **Streaming STT** — `STTEngine.transcribe_partial()` seam exists; whisper is
  currently full-utterance (the blocking call should move to a worker thread).
- **Persistent memory** — swap `Conversation` for a store-backed history.
- **More tools** — register a `Tool` in `tools.py`; the LLM loop handles
  chaining already (`_max_tool_iterations` caps runaway loops).

## Latency logging

`INFO` logs include per-stage timings: STT compute time, LLM time-to-first-token
and total time, tool round-trips (`ev.llm` lines). See where the seconds go with:

```bash
EV_LOG_LEVEL=INFO ./run.sh
```
