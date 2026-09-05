# ⚡ A.T.H.E.N.A. — Adaptive Thinking Hands-free Engine for Neural Assistance

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20--%203.14-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Android 8.0+](https://img.shields.io/badge/Android-API%2026--34-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://developer.android.com/)
[![Kotlin / Compose](https://img.shields.io/badge/Kotlin-Jetpack%20Compose-7F52FF?style=for-the-badge&logo=kotlin&logoColor=white)](https://developer.android.com/jetpack/compose)
[![React 19](https://img.shields.io/badge/Frontend-React%2019%20+%20Vite-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![MCP Spec](https://img.shields.io/badge/MCP-2024--11--05%20Compliant-FF6B6B?style=for-the-badge&logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/License-MIT-00F2FF?style=for-the-badge)](LICENSE)

> **A.T.H.E.N.A.** is a state-of-the-art, local-first autonomous AI operating ecosystem. It bridges a multi-model neural voice and reasoning engine, a native Android Default Digital Assistant with floating Perplexity-style HUD overlay, an interactive React 19 Cyberpunk Web Telemetry HUD with integrated PTY terminal, 9 Model Context Protocol (MCP) servers, an autonomous 8-vector academic deep research engine, long-term semantic vector memory, autonomous background sub-agents, and proactive cybersecurity auditing.

---

## 📑 Table of Contents

- [🌟 Core Capabilities & Highlights](#-core-capabilities--highlights)
  - [1. Native Android Assistant & Cyberpunk Mobile App](#1-native-android-assistant--cyberpunk-mobile-app)
  - [2. Real-Time Neural Voice & Speech Pipeline](#2-real-time-neural-voice--speech-pipeline)
  - [3. Autonomous Multi-Source Deep Research Engine](#3-autonomous-multi-source-deep-research-engine)
  - [4. Complete Model Context Protocol (MCP) Ecosystem (9 Servers)](#4-complete-model-context-protocol-mcp-ecosystem-9-servers)
  - [5. Long-Term Semantic Vector Memory & Knowledge Graph](#5-long-term-semantic-vector-memory--knowledge-graph)
  - [6. Modular Autonomous Sub-Agents & Skills Engine](#6-modular-autonomous-sub-agents--skills-engine)
  - [7. Interactive Terminal Bridge & WebSocket PTY](#7-interactive-terminal-bridge--websocket-pty)
  - [8. Proactive Security Watchdog & Lab Co-Pilot](#8-proactive-security-watchdog--lab-co-pilot)
  - [9. Ambient RGB Lighting Sync Engine](#9-ambient-rgb-lighting-sync-engine)
  - [10. Cyberpunk Holographic Web HUD](#10-cyberpunk-holographic-web-hud)
- [🏗️ System Architecture](#️-system-architecture)
- [📁 Repository & Directory Structure](#-repository--directory-structure)
- [🚀 Quick Start & Installation](#-quick-start--installation)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Backend Setup](#2-backend-setup)
  - [3. Frontend Web HUD Setup](#3-frontend-web-hud-setup)
  - [4. Android App Setup & Installation](#4-android-app-setup--installation)
  - [5. On-Device LLM via llama.cpp (Android Termux / Linux)](#5-on-device-llm-via-llamacpp-android-termux--linux)
- [⚙️ Configuration Reference (`backend/.env`)](#️-configuration-reference-backendenv)
- [⚡ Slash Commands & Skills Reference](#-slash-commands--skills-reference)
- [🛠️ Bundled MCP Servers & Tool Inventory](#️-bundled-mcp-servers--tool-inventory)
- [🛡️ Security, Sandboxing & Ethics](#️-security-sandboxing--ethics)
- [📄 License](#-license)

---

## 🌟 Core Capabilities & Highlights

### 1. Native Android Assistant & Cyberpunk Mobile App
The Android client (`android-app/`) is a full-fledged native application written in **Kotlin** with **Jetpack Compose (Material 3)**.

- **System Default Digital Assistant:**
  - Implements `AthenaVoiceInteractionService` and `AthenaRecognitionService` with `BIND_VOICE_INTERACTION` permissions.
  - Can be registered as the **Default Digital Assistant** in Android System Settings (replacing Google Assistant / Gemini).
  - Triggers via standard Android OS gestures: long-pressing the home button, corner swipe-up gestures, or hardware power-button shortcuts (`ASSIST` intent).
- **Perplexity-Style Floating HUD Overlay (`AssistantOverlayActivity`):**
  - Instant, non-intrusive floating transparent overlay launching above any running app without stealing app focus.
  - Features an animated multi-ring neural Arc Reactor orb (`OrbView.kt`), real-time microphone audio waveform visualizer (`AudioWaveformView.kt`), and hold-to-talk voice capture.
  - Structured chat bubble formatting with user query replay, assistant thought process, and Markdown stream rendering.
- **6-Tab Cyberpunk Mobile Dashboard (`CyberpunkAppShell`):**
  - ⚛️ **Core Dashboard (`DASHBOARD`):** Animated arc reactor, connection status to backend `:2027`, hardware telemetry, quick launcher for overlay HUD, and assistant setup guide.
  - 💬 **Sessions Chat (`CHAT`):** Multi-turn conversation viewer, session management (create, switch, rename, delete sessions), and slash command support.
  - 📚 **Notes Vault (`NOTES`):** Categorized Markdown notes browser (`deep-research`, `work`, `ideas`, `todos`), YAML frontmatter parser, and in-app document editor.
  - 🧩 **MCP Manager (`MCP`):** Live status monitor for all 9 MCP servers, tool introspection with JSON input schemas, and direct tool execution testing.
  - 🧠 **Skills & Tools (`SKILLS`):** Procedural skills catalog (`~/.athena/skills/`), background sub-agent dispatcher, and real-time task status tracking.
  - ⚙️ **Customization Hub (`SETTINGS`):** Dynamic network configuration (toggle between Android Emulator `10.0.2.2` and LAN host IP `192.168.x.x`), persona selector, and STT mode toggle.
- **On-Device Hybrid Audio & Speech Engine:**
  - Offline local Whisper TFLite transcription (`WhisperOfflineTranscriber.kt`) with zero network dependencies.
  - Native Android `SpeechRecognizer` integration for zero-latency multilingual recognition.
  - Native Android TTS engine with automatic **Tamil** (`ta-IN`) language detection and voice switching.
  - Hardware Acoustic Echo Cancellation (AEC) and TTS self-echo protection.
- **Pre-Compiled Standalone APK:**
  - Includes a production-ready signed debug APK: [`ATHENA-debug.apk`](file:///home/shabari/projects/AI%20assistant/ATHENA-debug.apk) (~77 MB) ready for instant sideloading via ADB.

---

### 2. Real-Time Neural Voice & Speech Pipeline
An ultra-low latency, 4-stage neural pipeline optimized for desktop, WSL2, Linux servers, and Android Termux:

```
[Microphone Audio]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: Continuous Ring Buffer & openWakeWord         │
│ • Pre-roll audio slicing (1.5s sliding window)         │
│ • Custom acoustic models ("A.T.H.E.N.A." / "S.A.R.A.") │
│ • Dynamic noise floor tracking & anti-spike gating     │
└───────────────────────────────────┬────────────────────┘
                                    │ Wake Hit
                                    ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Fast Neural Speech-to-Text (STT)              │
│ • faster-whisper (CTranslate2 int8 / float16)          │
│ • Optional Silero VAD noise suppression & anti-halluc. │
│ • Multi-model Gemini Cloud STT fallback for mobile web │
└───────────────────────────────────┬────────────────────┘
                                    │ User Transcript
                                    ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: LLM Brain Engine & Multi-Round Tool Chaining  │
│ • Primary: Google Gemini 2.5 / 2.0 Flash, Gemma-4-31B  │
│ • Local Offline: Ollama (gemma4:e4b) & llama.cpp server│
│ • AST-evaluated math sandbox & operator shell gating   │
└───────────────────────────────────┬────────────────────┘
                                    │ Streamed Response / Tool Call
                                    ▼
┌────────────────────────────────────────────────────────┐
│ Stage 4: High-Fidelity Neural Speech Synthesis (TTS)   │
│ • Zero-cost Edge-TTS neural streaming with PyAV decode │
│ • Local offline Piper ONNX neural voices               │
│ • Client-side Android TTS mode (ANDROID_TTS_MODE=true) │
└───────────────────────────────────┬────────────────────┘
                                    │ Audio Playback
                                    ▼
[Speaker Output / Android Client]
```

- **Acoustic Self-Echo Suppression:** Flushes audio buffers and blocks microphone input during assistant speech playback to prevent self-interruption.
- **Operator Confirmation Gating:** Dangerous terminal commands require operator confirmation (`ask` / `always` / `never`).

---

### 3. Autonomous Multi-Source Deep Research Engine
Designed for in-depth academic, technical, and architectural investigations (`backend/deep_research.py`):

- **8-Vector Academic & Technical Search Strategy:**
  Decomposes any complex research query into 8 orthogonal vectors:
  1. Foundational Theory & Mathematical Principles
  2. Contemporary Literature Review (2024–2026)
  3. Technical Architecture, System Models & Methodology
  4. Empirical Benchmarks & Performance Metrics
  5. Real-World Applications & Industrial Case Studies
  6. Critical Bottlenecks, Open Challenges & Failure Modes
  7. Academic Repositories, Codebases & Datasets
  8. Future Paradigms & Open Research Directions
- **Multi-Engine Harvesting & Concurrent Scraping:**
  - Queries **DuckDuckGo Web Search**, **ArXiv Scholarly Research API**, and **Wikipedia Technical Encyclopedia**.
  - Multi-threaded parallel crawler via `ThreadPoolExecutor` fetching up to 20 candidate URLs simultaneously with strict 6.0s timeouts.
  - Enforces a strict minimum quality bar of **10 to 12 verified high-quality sources**.
- **College-Project / Publication-Grade Research Paper Synthesis:**
  Outputs an analyst-grade, publication-ready research paper formatted in Markdown:
  - 📑 **Formal Abstract** (250–350 words)
  - 📌 **1. Introduction & Problem Formulation**
  - 📚 **2. Theoretical Foundations & Literature Survey** (inline citations `[1]`, `[2]`)
  - ⚙️ **3. Technical Architecture, System Models & Methodology**
  - 📊 **4. Empirical Evaluation, Benchmarks & Markdown Comparative Tables**
  - 🌍 **5. Real-World Applications & Industrial Case Studies**
  - ⚠️ **6. Critical Challenges, Bottlenecks & Limitations**
  - 🔮 **7. Future Outlook & Open Research Questions**
  - 🎯 **8. Conclusion & Project Summary**
  - 🔗 **References & Annotated Bibliography** (Numbered list of all 10–12+ sources with active URLs and analytical summaries).
- **Isolated Model Fallback Cascade:**
  $$\text{Gemini 3.7 Flash Lite / 2.5 Flash} \longrightarrow \text{Gemini Flash tiers} \longrightarrow \text{Gemini Pro} \longrightarrow \text{Local Ollama Gemma 26B} \longrightarrow \text{Local Academic Synthesizer}$$
  Handles API rate limits (HTTP 429) gracefully without freezing or degrading the main voice conversation model.
- **Automatic Vault Persistence & Voice Alerts:**
  Automatically saves reports into `backend/data/notes/deep-research/{slug}.md`, regenerates the search index (`notes_index.json`), and announces completion via spoken voice alert.

---

### 4. Complete Model Context Protocol (MCP) Ecosystem (9 Servers)
Full compliance with the **Anthropic Model Context Protocol (MCP 2024-11-05 spec)** over stdio JSON-RPC 2.0 (`backend/mcp_client.py` and `backend/mcp_servers.json`):

| MCP Server | Script | Description & Key Tooling |
| :--- | :--- | :--- |
| `notes-memory` | `notes_mcp_server.py` | Personal Markdown vault, YAML frontmatter, indexing, note CRUD, and interactive To-Do task management. |
| `duckduckgo-search` | `duckduckgo_mcp_server.py` | Multi-engine live search across DuckDuckGo Web, ArXiv academic papers, Wikipedia, and DuckDuckGo News. |
| `web-scraper` | `web_scraper_mcp_server.py` | Safe concurrent webpage content extraction, Markdown conversion, and hyperlink crawler. |
| `opencode` | `opencode_mcp_server.py` | Sandboxed repository code editing, AST analysis, file tree navigation, and Git tracking. |
| `security-audit` | `security_mcp_server.py` | SAST code scanner (secrets, SQLi, command injection), offline CVE searchsploit, passive subdomain recon via crt.sh, HTTP security header auditing, and scoped port scanning. |
| `android-termux` | `termux_mcp_server.py` | Hardware control via Termux API: battery status, flashlight/torch, vibration, clipboard sync, notifications, camera photo capture with multimodal vision analysis, and GPS location. |
| `robot-qa` | `robot_mcp_server.py` | Robot Framework automated test discovery, suite runner with custom tags, XML result parsing, and failure diagnosis context generation. |
| `git-copilot` | `git_mcp_server.py` | Autonomous Git operations: branch creation, diff inspection, patch application, conventional commit generation, and automated QA repair loops. |
| `dummy-demo` | `dummy_mcp_server.py` | Diagnostic reference implementation for MCP testing, ping verification, and echo payloads. |

---

### 5. Long-Term Semantic Vector Memory & Knowledge Graph
Local, zero-latency vector memory database running on SQLite (`backend/memory_engine.py`):
- Persistent storage at `backend/data/memory/memory.db`.
- **Semantic Ontology Expansion:** Built-in ontology mapping concepts (e.g., `typescript` -> `frontend`, `code`, `js`) with stopword stripping and token frequency weighting.
- **Automatic Episodic Learning:** Indexes user preferences, hardware environments, code styles, and habit patterns.
- **Context Injection:** Injects relevant memory chunks into LLM reasoning turns without overflowing token windows.

---

### 6. Modular Autonomous Sub-Agents & Skills Engine
Orchestrates parallel background execution and extensible procedural capabilities:
- **Sub-Agent Parallel Dispatcher (`backend/multi_agent_dispatcher.py`):**
  - Spins up dedicated background worker threads configured in `.athena/agents/<agent_name>.json`.
  - **Pre-Configured Specialized Agents:**
    - `recon_specialist`: DAST scanner, CVE advisories, SSL inspector, sensitive file auditor.
    - `deep_researcher`: Multi-vector research harvester and academic paper writer.
    - `code_architect`: Git inspection, refactoring, code generation, and test execution.
    - `termux_sysadmin`: Android Termux package manager, toolchain auditor, and hardware telemetry.
    - `ctf_copilot`: Active lab milestone logger, hash decoder, and walkthrough dossier generator.
- **Extensible Skills Engine (`backend/skills_engine.py`):**
  - Discovers and executes skills defined in `~/.athena/skills/<skill_name>/SKILL.md`.
  - **Multi-Mode `/learn` Command:**
    - **URL Mode:** Scrapes online documentation and transforms it into a structured skill playbook.
    - **Search Mode:** Searches DuckDuckGo for best practices, crawls top results, and generates a structured skill.
    - **Direct Rule Mode:** Formats user rules and workflows into an executable skill.

---

### 7. Interactive Terminal Bridge & WebSocket PTY
Full bidirectional pseudo-terminal bridge (`backend/terminal_bridge.py` on port `:2028`):
- Connects the React Web HUD (`IntegratedTerminal.tsx`) directly to host bash/zsh or Android Termux shell.
- Full ANSI color rendering, escape sequence processing, and terminal resizing (`TIOCSWINSZ`).
- Supports interactive terminal utilities: `htop`, `vim`, `nano`, `git log`, `tmux`, and shell scripts.

---

### 8. Proactive Security Watchdog & Lab Co-Pilot
- **Autonomous Background Scheduler (`backend/scheduler_engine.py`):**
  - Cron expression and interval-based task scheduler using `croniter`.
  - **Security Watchdog:** Periodically queries the **OSV (Open Source Vulnerabilities)** API for watched dependencies (e.g. `faster-whisper`, `google-genai`, `httpx`, `robotframework`, `mcp`).
  - Automatically raises spoken voice alerts and generates incident notes in the vault on critical CVEs.
- **CTF & Cybersecurity Lab Toolkit (`backend/lab_copilot.py`):**
  - Multi-format payload decoder (Base64, URL-safe, Hex, JWT, HTML entities, Rot13, binary).
  - Hash identifier with Hashcat (`-m`) and John the Ripper format mappings.
  - Educational CVE mentor (root cause explanations and defensive hints without spoiling flags).
  - Automated Lab Dossier Manager generating clean Markdown walkthroughs in `data/notes/lab-dossiers/`.
- **DAST Web Security Scanner (`backend/web_security_scanner.py`):**
  - Scans targets for SQL Injection error heuristics, reflected XSS, sensitive file leaks (`.env`, `.git/HEAD`, `backup.sql`, `swagger.json`), and open redirects.

---

### 9. Ambient RGB Lighting Sync Engine
Synchronizes real-world smart lighting (`backend/rgb_sync.py`) with assistant HUD phases via **WLED**, **OpenRGB**, or **Home Assistant / Philips Hue** webhooks:
- 🩵 **Standby:** Cyan Arc Reactor Pulse (`#00F2FF`)
- 💙 **Listening:** Electric Blue Solid Glow (`#0066FF`)
- 💜 **Processing / Deep Research:** Cosmic Purple Wave (`#8A2BE2`)
- 🔴 **Cybersecurity / Recon Mode:** Alert Crimson Pulse (`#FF0033`)
- 💛 **Speaking:** Warm Amber Radiant Glow (`#FFB800`)

---

### 10. Cyberpunk Holographic Web HUD
A sci-fi holographic interface built with **React 19, Vite, and Tailwind CSS** (`frontend/`):
- Served on `http://localhost:2026` or embedded directly from the backend `:2027`.
- **Arc-Reactor Core (`CoreOrb.tsx`):** Multi-ring SVG reactor animated with Anime.js responding to engine phases.
- **Canvas Audio Oscilloscope (`AudioWaveform.tsx`):** 60 FPS real-time audio wave rendering.
- **Interactive Markdown Notes Reader & Editor (`NotesVaultPanel.tsx`):** GitHub-flavored markdown viewer with code blocks, task toggles, and citation reference pills (`[1]`, `[2]`).
- **Live Timers & Pomodoro Bar (`ActiveTimersBar.tsx`):** Real-time countdown tracking with sound effects.
- **MCP Server Manager Panel (`McpConfigPanel.tsx`):** Interactive toggle switches, JSON tool schemas, and testing console.
- **Web Audio Procedural Sound Effects (`soundFx.ts`):** Sci-fi UI clicks, radar sweeps, and chimes synthesized entirely in Web Audio API.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph Clients [Client Interfaces]
        Android[Native Android Assistant App\n• Jetpack Compose Material 3\n• Default Digital Assistant Service\n• Floating Perplexity-Style HUD Overlay\n• Offline Whisper TFLite + Android TTS]
        WebHUD[Holographic Web HUD :2026\n• React 19 + Vite + Tailwind CSS\n• Anime.js Arc Reactor Core\n• Canvas Audio Oscilloscope\n• Notes Vault & MCP Config Panel]
        TermWeb[Integrated Web PTY Terminal\n• WebSocket ANSI Console]
    end

    subgraph Bridge_Layer [Network & Telemetry Bridge Layer]
        SSEBridge[evbridge.py :2027\n• Real-Time SSE Stream (4Hz)\n• REST API Endpoints\n• Static Web HUD Hosting]
        TermBridge[terminal_bridge.py :2028\n• Bidirectional WebSocket PTY Server]
    end

    subgraph Audio_Pipeline [Real-Time Audio & Speech Pipeline]
        Mic[Microphone Input] --> OWW[openWakeWord Engine\nCustom Athena Acoustic Models]
        OWW --> STT[faster-whisper STT Engine\nint8 / float16 + Silero VAD]
        STT --> Brain[LLM Brain Engine\nGemini 2.5/2.0 • Gemma-4 • Ollama • llama.cpp]
        Brain --> TTS[Neural TTS Synthesis\nEdge-TTS • Piper ONNX • Android TTS Mode]
        TTS --> Speaker[Speaker / Android Playback]
    end

    subgraph Core_Engines [Autonomous Background Engines]
        Brain <--> DeepRes[Deep Research Engine\n8 Vectors • 10-12+ Verified Sources]
        Brain <--> Timers[Smart Timers & Pomodoro Engine]
        Brain <--> Briefing[Daily Briefing Engine\nWeather • News • Tasks • Telemetry]
        Brain <--> Scheduler[Scheduler & OSV Security Watchdog]
        Brain <--> Memory[Semantic Vector Memory & SQLite Graph]
        Brain <--> LabCo[CTF Lab Co-Pilot & Payload Decoder]
        Brain <--> Agents[Sub-Agent Dispatcher & Skills Engine]
        Brain <--> RGBSync[Ambient RGB Lighting Sync Engine]
    end

    subgraph MCP_Layer [Model Context Protocol Ecosystem - 9 Servers]
        Brain <--> MCPClient[MCP Client Manager\nJSON-RPC 2.0 stdio]
        MCPClient <--> M_Notes[notes-memory]
        MCPClient <--> M_Search[duckduckgo-search]
        MCPClient <--> M_Scrape[web-scraper]
        MCPClient <--> M_OpenCode[opencode]
        MCPClient <--> M_Sec[security-audit]
        MCPClient <--> M_Termux[android-termux]
        MCPClient <--> M_Robot[robot-qa]
        MCPClient <--> M_Git[git-copilot]
        MCPClient <--> M_Dummy[dummy-demo]
    end

    %% Connections
    Android <-->|REST & SSE /ask| SSEBridge
    WebHUD <-->|REST & SSE /stream| SSEBridge
    TermWeb <-->|WebSocket| TermBridge
    TermBridge <--> HostShell[Host Linux / Termux Bash Shell]
    SSEBridge <--> Audio_Pipeline
    SSEBridge <--> Core_Engines
```

---

## 📁 Repository & Directory Structure

```
AI-Assistant/
├── ATHENA-debug.apk                 # Ready-to-install signed Android debug APK
├── README.md                        # Master documentation (this file)
│
├── android-app/                     # Native Android Digital Assistant
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── AndroidManifest.xml  # System voice interaction & assist services
│   │   │   ├── java/com/assistant/athena/
│   │   │   │   ├── MainActivity.kt               # Jetpack Compose Cyberpunk Dashboard
│   │   │   │   ├── AssistantOverlayActivity.kt   # Floating Perplexity-style HUD overlay
│   │   │   │   ├── AthenaVoiceInteractionService.kt # Android Default Assistant service
│   │   │   │   ├── data/
│   │   │   │   │   ├── Models.kt                 # Data classes & serialization
│   │   │   │   │   └── NetworkClient.kt          # OkHttp bridge client & SSE streaming
│   │   │   │   ├── ui/
│   │   │   │   │   ├── CyberpunkNavigation.kt    # 6-tab cyberpunk navigation bar
│   │   │   │   │   ├── OrbView.kt                # Custom multi-ring canvas reactor orb
│   │   │   │   │   ├── AudioWaveformView.kt      # Real-time microphone audio visualizer
│   │   │   │   │   ├── screens/                  # Compose UI screens
│   │   │   │   │   │   ├── SessionsChatScreen.kt     # Multi-turn chat & session manager
│   │   │   │   │   │   ├── NotesVaultScreen.kt       # Markdown notes & research browser
│   │   │   │   │   │   ├── McpManagerScreen.kt       # MCP server monitor & tool tester
│   │   │   │   │   │   ├── SkillsToolsScreen.kt      # Procedural skills & sub-agent runner
│   │   │   │   │   │   └── CustomizationHubScreen.kt # IP/port & persona configuration
│   │   │   │   └── whisper/
│   │   │   │       └── WhisperOfflineTranscriber.kt  # On-device Whisper TFLite transcriber
│   │   │   └── res/                              # Drawables, layouts, styles, and XML configs
│   │   └── build.gradle.kts                      # Android build configuration (compileSdk 34)
│   ├── athena.keystore                           # APK signing keystore
│   └── run_build.sh                              # Standalone APK compilation script
│
├── backend/                         # Python Voice & Autonomous Reasoning Backend
│   ├── main.py                      # Primary entry point & voice pipeline loop
│   ├── config.py                    # Environment parser and dataclass settings
│   ├── evbridge.py                  # SSE & REST bridge server (default port :2027)
│   ├── terminal_bridge.py           # WebSocket PTY server for interactive shell (:2028)
│   ├── audio_input.py               # Audio ring buffer, pre-roll, & openWakeWord
│   ├── stt.py                       # faster-whisper neural STT & Silero VAD
│   ├── llm.py                       # LLM reasoning loop (Gemini, Ollama, llama.cpp)
│   ├── tts.py                       # Edge-TTS, Piper ONNX, and PyAV decoding
│   ├── tools.py                     # Built-in tool definitions & AST math evaluator
│   ├── deep_research.py             # 8-vector autonomous deep research paper engine
│   ├── memory_engine.py             # SQLite semantic vector memory & knowledge graph
│   ├── multi_agent_dispatcher.py    # Background sub-agent thread manager
│   ├── skills_engine.py             # Modular skills parser, runner, and /learn synthesizer
│   ├── session_manager.py           # Multi-session conversation SQLite database
│   ├── briefing_engine.py           # Morning briefings & evening debriefs
│   ├── timer_engine.py              # Countdown timers & Pomodoro focus sessions
│   ├── scheduler_engine.py          # Cron jobs & OSV vulnerability security watchdog
│   ├── lab_copilot.py               # CTF toolkit (hash ID, payload decoder, CVE mentor)
│   ├── web_security_scanner.py      # DAST web scanner (SQLi, XSS, sensitive files)
│   ├── rgb_sync.py                  # WLED, OpenRGB, & Home Assistant lighting sync
│   ├── mcp_client.py                # Stdio JSON-RPC 2.0 MCP multi-server orchestrator
│   ├── mcp_servers.json             # Registry of active MCP servers
│   ├── notes_mcp_server.py          # Notes Vault & To-Do MCP server
│   ├── duckduckgo_mcp_server.py     # Web, ArXiv, and Wikipedia MCP server
│   ├── web_scraper_mcp_server.py    # Clean web scraping MCP server
│   ├── opencode_mcp_server.py       # Codebase inspection & editing MCP server
│   ├── security_mcp_server.py       # SAST audit, CVE search, & recon MCP server
│   ├── termux_mcp_server.py         # Android Termux hardware superpowers MCP server
│   ├── robot_mcp_server.py          # Robot Framework automated QA MCP server
│   ├── git_mcp_server.py            # Autonomous Git copilot & repair MCP server
│   ├── requirements.txt             # Python package dependencies
│   ├── run.sh                       # Quick launch script
│   ├── scripts/                     # Test suites, health checks, & setup helpers
│   └── data/                        # SQLite databases, Markdown notes, & task queues
│
└── frontend/                        # Cyberpunk Holographic Web HUD
    ├── src/
    │   ├── App.tsx                  # Main HUD container & layout grid
    │   ├── index.css                # Sci-fi cyberpunk design system & tokens
    │   ├── components/              # React components
    │   │   ├── CoreOrb.tsx              # Multi-ring arc reactor (Anime.js)
    │   │   ├── AudioWaveform.tsx        # 60 FPS HTML5 Canvas audio visualizer
    │   │   ├── NotesVaultPanel.tsx      # Markdown vault reader/editor & citation pills
    │   │   ├── McpConfigPanel.tsx       # MCP server toggle & tool inspector
    │   │   ├── IntegratedTerminal.tsx   # WebSocket PTY terminal console
    │   │   ├── ActiveTimersBar.tsx      # Countdown & Pomodoro progress bar
    │   │   ├── BriefingModal.tsx        # Daily executive intelligence briefing
    │   │   ├── CyberReconPanel.tsx      # DAST security scanner HUD panel
    │   │   └── CommandDeck.tsx          # Terminal prompt uplink & voice trigger
    │   └── lib/soundFx.ts           # Web Audio procedural sound effects engine
    ├── package.json                 # Node dependencies (React 19, Vite, Tailwind CSS)
    └── vite.config.ts               # Vite bundler configuration & reverse proxy
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- **Operating System:** Linux (Ubuntu 22.04+ recommended), WSL2 on Windows, or Android Termux.
- **Python:** Version **3.10** to **3.14**
- **Node.js:** Version **18+** with npm
- **Audio Subsystem:** PortAudio / PulseAudio (or WSLg audio)
- **Optional for Android Development:** Android SDK 34 / JDK 17 / ADB

---

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment keys
cp .env.example .env
# Edit .env and supply your GOOGLE_API_KEY (free from https://aistudio.google.com/apikey)
```

Launch the voice assistant backend:
```bash
./run.sh
# or directly:
python3 main.py
```

CLI execution options:
```bash
python3 main.py                      # Interactive voice assistant loop
python3 main.py --text "hi Athena"   # Direct text query without microphone
python3 main.py --once               # Process a single voice interaction and exit
python3 main.py transcribe           # STT audio diagnostic mode
python3 main.py --list-devices       # Display all audio input/output devices
```

---

### 3. Frontend Web HUD Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start the Vite development server (runs at http://localhost:2026)
npm run dev
```

*Note: The backend (`evbridge.py`) automatically serves the pre-compiled `frontend/dist/` bundle at `http://localhost:2027` if npm is not running!*

---

### 4. Android App Setup & Installation

#### Option A: Quick Sideload (Pre-Built APK)
Connect your Android device via USB with USB Debugging enabled, or boot an Android Emulator, then run:
```bash
adb install -r ATHENA-debug.apk
```

#### Option B: Build From Source
```bash
cd android-app
chmod +x run_build.sh
./run_build.sh
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

#### Setting Athena as the Android Default Assistant:
1. Open Android **Settings** on your phone.
2. Search for **Default digital assistant app** (or go to *Apps* -> *Default apps* -> *Digital assistant app*).
3. Select **A.T.H.E.N.A.**.
4. In the ATHENA app, open the **Config** tab and set the **Backend IP**:
   - If using the **Android Emulator**: `http://10.0.2.2:2027`
   - If using a **physical device on local Wi-Fi**: `http://<YOUR_PC_LAN_IP>:2027` (e.g. `http://192.168.1.50:2027`)
5. Swipe up from the bottom corner or hold the home button to activate the **Perplexity-style Floating HUD Overlay** from anywhere!

---

### 5. On-Device LLM via `llama.cpp` (Android Termux / Linux)
Run local, private, zero-cost neural models on edge hardware without external cloud APIs:

1. **Setup & Download Model (Termux / Linux):**
   ```bash
   bash backend/scripts/setup_llama_android.sh
   ```
   *Downloads Qwen 2.5 1.5B Instruct Q4_K_M (~1.1 GB, fast on mobile CPUs).*

2. **Start llama-server:**
   ```bash
   bash backend/scripts/run_llama_server.sh
   ```

3. **Configure `backend/.env`:**
   ```ini
   EV_LLM_PROVIDER=llama_cpp
   EV_LLAMA_CPP_BASE_URL=http://127.0.0.1:8080
   EV_LLAMA_CPP_MODEL=qwen2.5-1.5b-instruct
   ```

---

## ⚙️ Configuration Reference (`backend/.env`)

| Environment Variable | Default | Allowed Values | Description |
| :--- | :--- | :--- | :--- |
| `GOOGLE_API_KEY` | `""` | API Key string | Google AI Studio key for Gemini / Gemma models |
| `ELEVENLABS_API_KEY`| `""` | API Key string | Optional key for ElevenLabs neural voice synthesis |
| `EV_LLM_PROVIDER` | `gemini` | `gemini`, `rest`, `ollama`, `llama_cpp` | Primary LLM inference engine |
| `EV_LLM_MODEL` | `gemma-4-31b-it` | Model identifier string | Primary chat reasoning model |
| `EV_LLM_MAX_TOKENS` | `2048` | Integer | Maximum generation token budget |
| `EV_LLM_TEMPERATURE`| `0.7` | Float (0.0 - 1.0) | Sampling temperature |
| `EV_GEMINI_THINKING`| `false` | `true`, `false` | Enables deep internal reasoning thoughts |
| `EV_OLLAMA_BASE_URL`| `http://localhost:11434` | URL string | Local Ollama endpoint |
| `EV_OLLAMA_MODEL` | `gemma4:e4b` | Model tag string | Local Ollama fallback model |
| `EV_LLAMA_CPP_BASE_URL` | `http://127.0.0.1:8080` | URL string | Local `llama-server` endpoint |
| `EV_LLAMA_CPP_MODEL`| `qwen2.5-1.5b-instruct` | Model tag string | Local GGUF model identifier |
| `EV_STT_PROVIDER` | `local` | `local`, `google`, `gemini` | Speech transcription engine |
| `EV_STT_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3` | faster-whisper model weight tier |
| `EV_STT_DEVICE` | `cpu` | `cpu`, `cuda` | Hardware accelerator for STT |
| `EV_STT_COMPUTE_TYPE`| `int8` | `int8`, `float16` | Quantization precision |
| `EV_STT_VAD` | `false` | `true`, `false` | Silero Voice Activity Detector |
| `EV_TTS_PROVIDER` | `edge` | `edge`, `piper`, `gtts`, `elevenlabs` | Neural TTS audio synthesizer |
| `EV_EDGE_TTS_VOICE` | `en-US-AriaNeural` | Voice identifier string | Edge-TTS neural voice preset |
| `ANDROID_TTS_MODE` | `false` | `true`, `false` | Mutes backend speaker; delegates TTS to Android |
| `EV_TRIGGER` | `web` | `wakeword`, `ptt`, `web` | Audio trigger mode (`web` leaves mic free for HUD) |
| `EV_WAKE_WORDS` | `athena` | Comma-separated strings | Target wake phrases (`athena`, `sara`, `jarvis`) |
| `EV_WAKE_WORD_THRESHOLD` | `0.35` | Float (0.1 - 1.0) | Neural wake word detection sensitivity |
| `EV_CONFIRM_SHELL` | `ask` | `ask`, `always`, `never` | Security policy for shell command execution |
| `EV_BRIDGE_PORT` | `2027` | Integer | SSE & REST telemetry bridge port |

---

## ⚡ Slash Commands & Skills Reference

Commands can be triggered via voice, typed in the **Command Deck** (`/prompt`), or entered in the **Android Chat**:

| Slash Command | Syntax & Parameters | Description |
| :--- | :--- | :--- |
| `/help` | `/help` | Displays interactive reference guide for all commands. |
| `/learn` | `/learn <url \| topic \| rule>` | Synthesizes an agentic skill from web docs, searches, or rules into `~/.athena/skills/`. |
| `/skill` | `/skill [list \| show <name> \| run <name>]` | Inspects, reads, or triggers a procedural skill. |
| `/agent` | `/agent [list \| dispatch <name> <task> \| status \| cancel <id>]` | Launches and manages specialized background sub-agents. |
| `/research` | `/research <topic>` | Executes 8-vector academic deep research with paper generation. |
| `/recon` | `/recon <target_ip_or_domain>` | Runs DAST web security scans, sensitive file checks, and header audits. |
| `/goal` | `/goal <objective_statement>` | Enters autonomous execution loop toward an objective. |
| `/schedule` | `/schedule <time/cron> <task>` | Schedules one-shot reminders or recurring cron jobs. |
| `/briefing` | `/briefing [morning \| evening]` | Generates structured executive intelligence briefing. |
| `/clear` | `/clear` | Clears telemetry log history and transcript feed. |

---

## 🛠️ Bundled MCP Servers & Tool Inventory

All 9 MCP servers are configured in [`backend/mcp_servers.json`](file:///home/shabari/projects/AI%20assistant/backend/mcp_servers.json):

### 1. `notes-memory` (`notes_mcp_server.py`)
- `add_note`: Creates a Markdown note with frontmatter in the vault.
- `read_note`: Reads full note content and YAML metadata.
- `list_notes`: Lists all notes by category with frontmatter metadata.
- `search_notes`: Performs full-text keyword search across the vault.
- `edit_note`: Modifies existing note body or appends content.
- `delete_note`: Removes a note from the vault.
- `list_todos`: Fetches task items with status and priority tags.
- `add_todo`: Creates a new To-Do item.
- `toggle_todo`: Toggles completion checkbox status.
- `remove_todo`: Deletes a To-Do item.

### 2. `duckduckgo-search` (`duckduckgo_mcp_server.py`)
- `duckduckgo_search`: Multi-engine web search with ArXiv and Wikipedia aggregation.
- `duckduckgo_news`: Live news headlines and journalism queries.

### 3. `web-scraper` (`web_scraper_mcp_server.py`)
- `scrape_web_page`: Extracts clean, readable text content from URLs.
- `extract_page_links`: Crawls and discovers hyperlinks across domains.

### 4. `opencode` (`opencode_mcp_server.py`)
- `view_workspace_file`: Inspects files within allowlisted workspace boundaries.
- `write_workspace_file`: Creates or modifies code files.
- `edit_workspace_file`: Applies precise surgical edits to code.
- `list_workspace_files`: Generates recursive workspace file trees.
- `workspace_git_status`: Displays Git branch and modified file states.

### 5. `security-audit` (`security_mcp_server.py`)
- `security_cve_search`: Queries local Exploit-DB and vulnerability databases.
- `security_passive_recon`: Subdomain discovery via certificate transparency logs (crt.sh).
- `security_header_audit`: Validates CSP, HSTS, CORS, and cookie flags.
- `security_code_audit`: SAST scanner for hardcoded secrets, SQLi, and injection flaws.
- `security_port_scan`: Scoped TCP port scanner for allowlisted targets.
- `security_report_export`: Exports audit dossiers directly to the Markdown vault.

### 6. `android-termux` (`termux_mcp_server.py`)
- `termux_battery_status`: Queries battery percentage, temperature, and charging health.
- `termux_torch_control`: Toggles the device flashlight on/off.
- `termux_vibrate`: Triggers custom haptic vibration patterns.
- `termux_clipboard_sync`: Reads or writes the Android system clipboard.
- `termux_send_notification`: Displays native Android tray notifications.
- `termux_camera_capture`: Takes photos via front/back camera and performs vision analysis.
- `termux_location_query`: Retrieves GPS coordinates for local context.
- `termux_ping_host`: Verifies network latency and host reachability.

### 7. `robot-qa` (`robot_mcp_server.py`)
- `robot_list_suites`: Discovers all `.robot` test suites and tags.
- `robot_run_suite`: Executes automated test runs via Robot Framework.
- `robot_parse_output`: Parses `output.xml` to isolate test failures and keywords.

### 8. `git-copilot` (`git_mcp_server.py`)
- `git_status`: Inspects branch state, staged/unstaged changes, and untracked files.
- `git_diff`: Generates unified diffs between branches or working tree.
- `git_create_branch`: Creates and switches to bugfix/feature branches.
- `git_apply_patch`: Applies unified patches cleanly.
- `git_commit`: Creates structured conventional commits.
- `qa_auto_repair_loop`: Automated loop linking test execution, patch generation, and re-testing.

### 9. `dummy-demo` (`dummy_mcp_server.py`)
- `dummy_echo`: Echoes input text for protocol latency calibration.
- `dummy_calculate`: AST calculation test.
- `dummy_ping`: Simple MCP liveness probe.

---

## 🛡️ Security, Sandboxing & Ethics

1. **Strict Workspace Jailing:** All workspace file access tools (`opencode`, `git-copilot`) are locked to the configured repository directory. Path traversal (`../`) outside the repository is strictly blocked.
2. **Operator Command Confirmation:** Shell execution defaults to `EV_CONFIRM_SHELL=ask`, prompting the operator before executing shell actions.
3. **Safe Mathematical Evaluation:** Calculations use a pure AST parser (`ast.parse`) with strict node validation—never `eval()` or arbitrary code execution.
4. **Authorized Security Scoping:** The `security-audit` server enforces a strict network allowlist (`SECURITY_TARGET_ALLOWLIST`), defaulting exclusively to `localhost`, `127.0.0.1`, and RFC1918 private subnets.
5. **Origin-Gated Telemetry:** WebSocket and SSE endpoints enforce origin headers to mitigate cross-site hijacking.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
