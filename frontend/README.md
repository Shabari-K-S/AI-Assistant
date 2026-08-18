# S.A.R.A. — Holographic Voice & Reasoning HUD

A **JARVIS-style sci-fi holographic command deck** for S.A.R.A. (Synthesized Artificial Reasoning Agent) — arc-reactor core, live oscilloscope waveform, wake sensitivity meter, terminal uplink console, personal Markdown notes vault, active timers, briefing modal, MCP server manager, and telemetry streams. Built with **React 19 + Vite + Tailwind CSS**, served at **http://localhost:2026**.

---

## 🚀 Quick Start

```bash
npm install
npm run dev        # -> http://localhost:2026
npm run build      # production build to dist/
npm run typecheck  # tsc -b --noEmit
npm run lint       # oxlint
```

---

## 🏗️ Architecture & Bridge Integration

The web HUD connects to the Python voice & engine backend (`evbridge.py` on `:2027`) via a built-in reverse proxy at `/bridge`:

- `GET /stream` (SSE): Real-time 4Hz telemetry snapshots + discrete event logs (`transcript`, `reply`, `deep_research_progress`, `deep_research_completed`, `timer_tick`, `briefing_ready`).
- `GET /notes`: Fetch all indexed notes, categories, and deep research papers.
- `GET /notes/read?target=...`: Read full markdown note content and YAML frontmatter.
- `POST /notes/save` & `POST /notes/delete`: Create, update, or remove markdown notes in the vault.
- `GET /timers` & `POST /timers/cancel`: Manage active countdown timers and Pomodoro sessions.
- `POST /config`: Interactive calibration for wake threshold (`{"threshold": 0.35}`) and speech mute.
- `POST /prompt`: Direct terminal command uplink (`{"text": "Sara, run deep research on quantum computing"}`).

```
src/
  App.tsx                 Main HUD layout & sector distribution
  types.ts                Snapshot, LogLine, VaultNote, Timer, Briefing definitions
  lib/
    soundFx.ts            Procedural Web Audio sci-fi sound effects engine
  hooks/
    useAssistant.ts       Persistent SSE telemetry stream & event dispatcher
    useNotes.ts           Markdown notes vault data fetching & CRUD hooks
  components/
    NotesVaultPanel.tsx   Personal Markdown Notes & Deep Research Vault Reader/Editor
    ActiveTimersBar.tsx   Live active countdown timers & Pomodoro focus bar
    BriefingModal.tsx     Morning & Evening Executive Briefing Modal
    McpConfigPanel.tsx    Model Context Protocol (MCP) Server Manager & Tool Catalog
    AmbientCanvas.tsx     Canvas holo-mote particle field (pauses when hidden)
    CoreOrb.tsx           Multi-layer arc-reactor core with Anime.js rotation
    AudioWaveform.tsx     Real-time canvas audio oscilloscope & spectrum visualizer
    CommandDeck.tsx       Interactive terminal uplink input with voice hold-to-talk & quick action chips
    TelemetryGauges.tsx   Realtime telemetry gauges (Wake, RMS, Brain, Voice)
    WakeMeter.tsx         48-segment spectrum wake sensitivity meter
    SensorPanel.tsx       Sensory calibration & system matrix panel
    FeedPanel.tsx         Inbound transmissions & telemetry event stream
    StatusBar.tsx         Top HUD: phase indicators, sound FX toggle, clock
```

---

## 🌟 Key Features

- **Multi-Phase Arc-Reactor Core**: Dynamic rotational speed, energy pulsing, and color grading (`standby` cyan, `listening` blue, `processing` purple, `speaking` amber).
- **Markdown Notes Vault**: Interactive document viewer with support for GitHub-flavored markdown, comparison tables, task toggles, code blocks, and **citation reference pills** (`[1]`, `[2]`).
- **Autonomous Deep Research Viewer**: Dedicated **"COLLEGE PROJECT PAPER"** badge, source counter (`📚 12 VERIFIED SOURCES`), model badges, and quick **"COPY MD"** action.
- **Active Timers & Pomodoro Bar**: Real-time progress bars for active focus countdowns and break sessions.
- **Executive Daily Briefing Modal**: Detailed morning/evening summaries with weather metrics, tasks, and headlines.
- **MCP Server Visual Config**: Enable/disable MCP tool servers and browse live tool declarations.
- **Interactive Command Deck**: Direct typed prompt uplink with voice hold-to-talk recognition and quick action chips.
- **Procedural Sound FX Engine**: Web Audio sci-fi clicks, wake sweeps, transmission pings, and completion chimes.
