# A.T.H.E.N.A. — Backend Engine Architecture

The core python backend for **A.T.H.E.N.A.** (*Adaptive Thinking Hands-free Engine for Neural Assistance*). Implements an end-to-end voice and reasoning pipeline, autonomous background engines, Model Context Protocol (MCP) servers, and real-time SSE telemetry bridge.

```
Mic Input → Wake Word (openWakeWord) → STT (faster-whisper) → LLM (Gemma 4 / Gemini API) → TTS (Edge-TTS / Piper) → Speaker
                                      ↳ SSE Telemetry Bridge (:2027) ⮀ Frontend HUD (:2026)
```

---

## 🧩 Pipeline Modules & Engine Architecture

| Stage / Module | Source File | Description |
| :--- | :--- | :--- |
| **Stage 1: Audio Input & Wake Word** | `audio_input.py` | Continuous ring buffer, pre-roll audio slicing, openWakeWord neural inference (`"A.T.H.E.N.A."`). |
| **Stage 2: Neural STT** | `stt.py` | High-speed local transcription via `faster-whisper` (`int8`/`float16`), Silero VAD. |
| **Stage 3: LLM Brain & Tools** | `llm.py`, `tools.py` | Multi-round tool chaining loop, Gemini API client, local Ollama client, safety validation. |
| **Stage 4: Neural TTS** | `tts.py` | Zero-cost Edge-TTS neural streaming, local Piper ONNX, ElevenLabs, PyAV in-memory decoding. |
| **Autonomous Deep Research** | `deep_research.py` | 8-vector query decomposition, 10–12+ verified source harvesting (DuckDuckGo + ArXiv + Wikipedia), parallel scraping, isolated model cascade, and college project research paper synthesis. |
| **Markdown Notes Vault** | `notes_mcp_server.py` | Personal notes & deep research vault (`backend/data/notes/`), YAML frontmatter, automatic indexing, to-dos. |
| **Smart Timers & Pomodoro** | `timer_engine.py` | Background countdown timers, Pomodoro focus/break sessions, natural language parsing, spoken alerts. |
| **Executive Daily Briefings** | `briefing_engine.py` | Morning briefings and evening debriefs with live weather, tasks, news, and telemetry. |
| **MCP Orchestrator** | `mcp_client.py` | stdio JSON-RPC 2.0 multi-server manager for dynamic tool discovery and execution. |
| **Telemetry Event Bridge** | `evbridge.py` | Real-time Server-Sent Events (SSE) and REST bridge on port `2027`. |

---

## 🔬 Autonomous Deep Research Engine

The Deep Research Engine runs autonomously in a dedicated background worker thread:

1. **Decomposition:** Generates 8 orthogonal academic and technical query vectors covering theory, literature review (2024–2026), architecture, benchmarks, case studies, bottlenecks, and scholarly publications.
2. **Multi-Source Harvesting:** Queries DuckDuckGo, ArXiv Scholarly API, and Wikipedia Technical Encyclopedia to harvest 25+ candidates with domain balancing.
3. **Concurrent Scraping:** Scrapes up to 20 candidate URLs simultaneously with `ThreadPoolExecutor` (6.0s timeout per worker).
4. **Source Verification:** Enforces a strict minimum threshold of **10 to 12 verified high-quality sources**.
5. **Isolated Model Synthesis Cascade:**
   - Dedicated synthesis fallback chain:
     $$\text{Gemini 3.7 Flash Lite / 2.5 Flash} \longrightarrow \text{Gemini Flash tiers} \longrightarrow \text{Gemini Pro} \longrightarrow \text{Local Ollama Gemma 26B} \longrightarrow \text{Local Academic Synthesizer}$$
   - Primary chat/voice conversations remain untouched on `gemma-4-31b-it`.
6. **Publication-Grade Document Structure:** Generates a structured academic project paper with formal Abstract, 8 analytical sections, Markdown comparison tables, and an Annotated Bibliography with numbered citations `[1]` to `[N]`.
7. **Storage & Voice Alert:** Automatically writes to `data/notes/deep-research/{slug}.md`, rebuilds the vault index, and interrupts with a spoken voice summary.

---

## 🛠️ Built-in MCP Servers (JSON-RPC 2.0 stdio)

| MCP Server | Script | Provided Tools |
| :--- | :--- | :--- |
| `notes-memory` | `notes_mcp_server.py` | `add_note`, `read_note`, `list_notes`, `search_notes`, `edit_note`, `delete_note`, `list_todos`, `add_todo`, `toggle_todo`, `remove_todo` |
| `duckduckgo-search` | `duckduckgo_mcp_server.py` | `duckduckgo_search` (Web + ArXiv + Wikipedia), `duckduckgo_news` |
| `web-scraper` | `web_scraper_mcp_server.py` | `scrape_web_page`, `extract_page_links` |
| `opencode-tools` | `opencode_mcp_server.py` | `view_workspace_file`, `write_workspace_file`, `edit_workspace_file`, `list_workspace_files`, `workspace_git_status` |

---

## ⚙️ Environment Configuration (`.env`)

```ini
# --- Google AI Studio / Gemini API ---
GOOGLE_API_KEY=your_google_api_key_here

# --- LLM Brain Configuration ---
EV_LLM_PROVIDER=gemini              # gemini | ollama
EV_LLM_MODEL=gemma-4-31b-it         # primary chat model
EV_LLM_MAX_TOKENS=2048
EV_LLM_TEMPERATURE=0.7
EV_LLM_MAX_TURNS=20
EV_GEMINI_THINKING=false

# --- Local Ollama Fallback ---
EV_OLLAMA_BASE_URL=http://localhost:11434
EV_OLLAMA_MODEL=gemma4:e4b

# --- Speech-to-Text (STT) ---
EV_STT_PROVIDER=local               # local (faster-whisper) | google | gemini
EV_STT_MODEL=small                  # tiny | base | small | medium | large-v3
EV_STT_DEVICE=cpu                   # cpu | cuda
EV_STT_COMPUTE_TYPE=int8            # int8 on CPU, float16 on GPU
EV_STT_LANGUAGE=en
EV_STT_VAD=true

# --- Text-to-Speech (TTS) ---
EV_TTS_PROVIDER=edge                # edge | piper | gtts | elevenlabs
EV_EDGE_VOICE=en-US-AriaNeural
EV_EDGE_RATE=+0%
EV_EDGE_PITCH=+0Hz

# --- Wake Word & Audio ---
EV_TRIGGER=wakeword                 # wakeword | ptt
EV_WAKE_WORDS=athena
EV_WAKE_WORD_THRESHOLD=0.35
EV_WAKE_GRACE_SECONDS=1.2
EV_WAKE_END_SILENCE_SECONDS=1.0

# --- Safety & Shell Gates ---
EV_CONFIRM_SHELL=ask                # ask | always | never
EV_SHELL_ALLOWLIST=ls,cat,head,tail,df,uptime,pwd,echo,date,whoami,uname

# --- Telemetry Bridge ---
EV_BRIDGE_PORT=2027
```

---

## 🚀 Running the Backend

### Standard Run
```bash
cd backend
source .venv/bin/activate
./run.sh          # Linux / WSL2
# or: python3 main.py
```

### CLI Command Options
```bash
python3 main.py                      # Standard interactive voice assistant loop
python3 main.py --text "hi Athena"   # Skip microphone; send direct text query
python3 main.py --once               # Single voice turn, then exit
python3 main.py transcribe           # Run STT engine only (audio debug)
python3 main.py --list-devices       # List all system audio input/output devices
```

### Running Test Suites
```bash
python3 scripts/test_deep_research_sources.py   # Test 10-12+ source deep research & paper synthesis
```
