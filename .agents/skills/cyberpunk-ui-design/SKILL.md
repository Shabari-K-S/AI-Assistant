---
name: cyberpunk-ui-design
description: >-
  Design guidelines, color tokens, typography rules, and component recipes for building
  tactical sci-fi holographic interfaces across the React Web HUD and Jetpack Compose Android app.
  Use whenever modifying screens, dashboards, canvas visualizers, or UI components.
---

# Cyberpunk Holographic UI Design Guide

This skill guides the construction of visual components for A.T.H.E.N.A. across both the Web HUD and the Android native client.

## 1. Core Color Palette & Dynamic Phase States

### Primary Colors
- **Void Backgrounds:** `#03070b` (Web) / `#06080D` (Android `VoidBlack`)
- **Panel Surfaces:** `#09141d` (Web `PanelDark`) / `#0C131F` (Android `PanelDarkSolid`)
- **Primary Electric Cyan:** `#00F2FE` / `#41e6ff` (Glow: `rgba(0, 242, 254, 0.3)`)
- **Panel Stroke:** 1px `rgba(65, 230, 255, 0.14)` (Web) / `0x3300F2FE` (Android)

### Universal HUD Reactor Phase Mapping
All visual indicators (orbs, reactor cores, lighting, borders) MUST reflect system state:
| Assistant Phase | Color Name | Hex Code | Visual Behavior |
| :--- | :--- | :--- | :--- |
| **Standby** | Neon Cyan | `#00F2FE` | Calm breathing pulse (2s period) |
| **Listening** | Electric Blue | `#0066FF` / `#4FACFE` | Solid bright illumination + active audio waveform |
| **Processing / Deep Research** | Cosmic Purple | `#8A2BE2` | Rapid rotation, orbital wave oscillation |
| **Alert / Recon / Security** | Alert Crimson | `#FF0033` / `#EF4444` | High-frequency warning strobe / pulse |
| **Speaking / Audio Playback** | Warm Amber | `#FFB800` / `#F59E0B` | Radiant warm glow, harmonic audio ripple |

---

## 2. Typography Hierarchy

- **Display / Headers / Sector Labels:**
  - Font: `Orbitron`, uppercase, letter-spacing `0.18em` to `0.25em`.
  - Use for badges, section titles, protocol tags (e.g. `[SYS.READY]`, `SECTOR 01`).
- **Body & Chat Content:**
  - Font: `Rajdhani` or clean neutral sans-serif (14px - 15px, relaxed line height).
- **Metrics / Numbers / Code / Terminals:**
  - Font: Monospace (`SF Mono`, `Cascadia Mono`, Consolas).
  - Cyan text glow: `text-shadow: 0 0 8px rgba(65, 230, 255, 0.55)`.

---

## 3. Web Implementation Recipes (React 19 + Tailwind)

### HUD Panel with Corner Brackets
```tsx
<div className="hud-panel corners p-4">
  <span className="tl" /><span className="tr" />
  <span className="bl" /><span className="br" />
  <div className="hud-label text-xs mb-2">SYSTEM TELEMETRY</div>
  <div className="hud-num text-2xl">98.4%</div>
</div>
```

### Background Blueprint Grid & Scanlines
- Apply `.hud-grid` to full-screen containers for the radial-masked 46px blueprint grid.
- Apply `.scanlines` as a non-interactive pointer-events-none overlay for CRT texture.

---

## 4. Android Implementation Recipes (Jetpack Compose)

### Holographic Container (`HudCard`)
```kotlin
HudCard(
    modifier = Modifier.fillMaxWidth(),
    borderColor = PanelStroke,
    backgroundColor = PanelDarkSolid
) {
    Text(
        text = "NEURAL STATUS",
        fontFamily = FontFamily.Monospace,
        color = NeonCyan,
        fontSize = 12.sp
    )
}
```

### Dot Matrix Background (`DotMatrixBackground`)
Wrap full screens in `DotMatrixBackground { ... }` to automatically draw the 24dp cyan matrix dots.

---

## 5. Visual Anti-Patterns (Strictly Avoid)
- ❌ Never use generic, unstyled buttons or default Material 3 purple/grey palettes.
- ❌ Never use pure white backgrounds (`#FFFFFF`).
- ❌ Never render raw text without proper HUD typography classes or monospace counters.
- ❌ Never omit corner brackets or glow accents on major dashboard cards.
