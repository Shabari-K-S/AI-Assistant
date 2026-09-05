---
name: android-development
description: >-
  Comprehensive guide and runbook for developing, debugging, building, and deploying
  the Kotlin Jetpack Compose Android app in this repository. Use when modifying Android
  screens, voice services, audio pipelines, Gradle builds, or running ADB commands.
---

# Android & Kotlin Development Guide

This skill guides the architecture, development, compilation, and ADB deployment of the native Android application in `android-app/`.

## 1. Environment Variables & Compilation

The project requires specific toolchain paths:
- **Compile SDK:** 34 | **Target SDK:** 34 | **Min SDK:** 26 (Android 8.0+)
- **Kotlin Compiler Extension:** 1.5.8 | **Java Target:** JDK 17

### Build Commands
Always use `run_build.sh` or export the required environment variables:

```bash
cd "/home/shabari/projects/AI assistant/android-app"
export JAVA_HOME=/home/shabari/.local/jdk17
export PATH=$JAVA_HOME/bin:/home/shabari/.local/gradle-8.5/bin:$PATH
export ANDROID_HOME=/home/shabari/.local/android-sdk

# Execute compilation:
./run_build.sh
```

### Artifact Distribution Sync
After compiling, sync the output binary:
```bash
cp -v android-app/app/build/outputs/apk/debug/app-debug.apk ATHENA-debug.apk
cp -v android-app/app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/shabari/Desktop/ATHENA-debug.apk
```

---

## 2. ADB Deployment & Testing Runbook

```bash
# Sideload APK
adb install -r ATHENA-debug.apk

# Forward port 2027 over USB (allows app to connect to localhost:2027 without Wi-Fi setup)
adb reverse tcp:2027 tcp:2027

# Set Athena as the System Default Digital Assistant via ADB
adb shell settings put secure assistant com.assistant.athena/com.assistant.athena.AthenaVoiceInteractionService
adb shell settings put secure voice_interaction_service com.assistant.athena/com.assistant.athena.AthenaVoiceInteractionService

# Trigger the Assistant Overlay via intent
adb shell am start -a android.intent.action.ASSIST
```

---

## 3. Core Android Architecture & Services

### Default Digital Assistant (`AthenaVoiceInteractionService.kt`)
- Binds to `android.service.voice.VoiceInteractionService` with `BIND_VOICE_INTERACTION` permission.
- Pairs with `AthenaVoiceSessionService.kt` and `AthenaRecognitionService.kt`.

### Floating Perplexity-Style HUD Overlay (`AssistantOverlayActivity.kt`)
- Launched on system assist gesture or power-button shortcut.
- Must maintain isolated task affinity in `AndroidManifest.xml`:
  ```xml
  android:launchMode="singleInstance"
  android:taskAffinity=""
  android:excludeFromRecents="true"
  android:noHistory="true"
  android:theme="@style/Theme.Athena.AssistantOverlay"
  android:windowSoftInputMode="adjustResize"
  ```

### Cyberpunk Dashboard (`CyberpunkAppShell.kt`)
- 6 Navigation tabs:
  1. `DASHBOARD` (`Core`): Arc reactor animation & connection status.
  2. `CHAT` (`SessionsChatScreen.kt`): Multi-turn session messaging & slash commands.
  3. `NOTES` (`NotesVaultScreen.kt`): Categorized Markdown notes browser & editor.
  4. `MCP` (`McpManagerScreen.kt`): Model Context Protocol server inspector & tool tester.
  5. `SKILLS` (`SkillsToolsScreen.kt`): Background sub-agents & procedural skill execution.
  6. `SETTINGS` (`CustomizationHubScreen.kt`): Dynamic backend host IP/port config.

---

## 4. Audio, STT & TTS Conventions

- **Offline STT:** `WhisperOfflineTranscriber.kt` uses TensorFlow Lite (`tflite-runtime`). Keep `.tflite` assets uncompressed in Gradle (`androidResources { noCompress("tflite", "bin") }`).
- **Multilingual TTS:** `AssistantOverlayActivity` dynamically detects Tamil Unicode characters (`\u0B80-\u0BFF`) to switch `Locale` to `ta-IN`.
- **Acoustic Echo Cancellation:** Always attach `AcousticEchoCanceler` to `AudioRecord` sessions to prevent assistant speech playback from triggering self-input.

---

## 5. Network Bridge Integration (`NetworkClient.kt`)

- Connects to Python backend (`evbridge.py` on `:2027`):
  - `GET /state`: Connection health check
  - `POST /ask`: Synchronous assistant reasoning response
  - `POST /transcribe`: Remote Gemini audio STT
  - `/notes/*`: Markdown vault CRUD operations
  - `/mcp/*`: Server status and toggle
  - `GET /stream`: Real-time SSE telemetry
- In the Android Emulator, use `http://10.0.2.2:2027`.
- Over USB with `adb reverse`, use `http://127.0.0.1:2027`.
- Over local Wi-Fi, use the machine's LAN IP `http://192.168.x.x:2027`.
