# S.A.R.A. — Holographic Voice & Reasoning HUD

A **JARVIS-style sci-fi holographic command deck** for S.A.R.A. (Synthesized Artificial Reasoning Agent) — arc-reactor core, live oscilloscope waveform, wake sensitivity meter, terminal uplink console, and telemetry streams. Built with **React 19 + Vite 8 + Tailwind CSS 4**, served at **http://localhost:2026**.

## Quick Start

```bash
npm install
npm run dev        # -> http://localhost:2026
npm run build      # production build to dist/
npm run typecheck  # tsc -b --noEmit
npm run lint       # oxlint
```

## Architecture & Integration

The web HUD connects to the Python voice engine (`ai-assisstent/evbridge.py` on `:2027`) via a built-in reverse proxy at `/bridge`:

- `GET /stream` (SSE): Real-time 4Hz telemetry snapshots + discrete event logs (`transcript`, `reply`, `error`, `log`).
- `POST /config`: Interactive calibration for wake threshold (`{"threshold": 0.8}`) and speech mute (`{"muted": true}`).
- `POST /prompt`: Direct terminal command uplink (`{"text": "check system status"}`).

```
src/
  App.tsx                 Main HUD layout & sector distribution
  types.ts                Snapshot / LogLine / Phase definitions
  lib/
    soundFx.ts            Procedural Web Audio sci-fi sound effects engine
  hooks/
    useAssistant.ts       Persistent SSE telemetry stream & control dispatcher
  components/
    AmbientCanvas.tsx     Canvas holo-mote particle field (pauses when hidden)
    CoreOrb.tsx           Multi-layer arc-reactor core with Anime.js rotation
    AudioWaveform.tsx     Real-time canvas audio oscilloscope & spectrum visualizer
    CommandDeck.tsx       Interactive terminal uplink input with quick action chips
    TelemetryGauges.tsx   Realtime telemetry gauges (Wake, RMS, Brain, Voice)
    WakeMeter.tsx         48-segment spectrum wake sensitivity meter
    SensorPanel.tsx       Sensory calibration & system matrix panel
    FeedPanel.tsx         Inbound transmissions & telemetry event stream
    StatusBar.tsx         Top HUD: phase indicators, sound FX toggle, clock
```

## Features

- **Multi-phase Arc-Reactor Core**: Dynamic rotational speed, energy pulsing, and color grading (`standby` cyan, `listening` blue, `processing` purple, `speaking` amber).
- **Interactive Command Deck**: Direct typed prompt uplink with quick action chips ("System Status", "CPU & Load", "Self Diagnostic").
- **Live Oscilloscope & Spectrum Analyzer**: Canvas waveform reacting to wake score, speech activity, and noise floors.
- **Procedural Sound FX**: Web Audio sci-fi clicks, wake sweeps, transmission pings, and error buzzes.
- **Sensor Calibration**: Live wake word sensitivity slider and voice audio mute toggle.
- **Telemetry Event Log**: Timestamped transcription history with copy-to-clipboard actions.
