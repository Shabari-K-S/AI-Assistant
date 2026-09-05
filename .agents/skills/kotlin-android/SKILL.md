---
name: kotlin-android
description: >-
  Expert guidelines, build procedures, and architectural patterns for developing,
  refactoring, and compiling the Kotlin Jetpack Compose Android app in this repository.
  Use when the user asks to modify Android screens, Kotlin services, audio pipelines,
  or build and run the APK.
---

# Kotlin & Android Assistant Development Guide

This skill guides the architecture, development, compilation, and ADB deployment of the native Android application in `android-app/`.

For the complete guide, see [.agents/skills/android-development/SKILL.md](file:///home/shabari/projects/AI%20assistant/.agents/skills/android-development/SKILL.md).

## Quick Build & Deployment Reference

```bash
# Set build environment and compile:
cd "/home/shabari/projects/AI assistant/android-app"
export JAVA_HOME=/home/shabari/.local/jdk17
export PATH=$JAVA_HOME/bin:/home/shabari/.local/gradle-8.5/bin:$PATH
export ANDROID_HOME=/home/shabari/.local/android-sdk
./run_build.sh

# Sync artifacts:
cp -v app/build/outputs/apk/debug/app-debug.apk ../ATHENA-debug.apk
cp -v app/build/outputs/apk/debug/app-debug.apk /mnt/c/Users/shabari/Desktop/ATHENA-debug.apk

# Sideload & reverse port:
adb install -r ../ATHENA-debug.apk
adb reverse tcp:2027 tcp:2027
```
