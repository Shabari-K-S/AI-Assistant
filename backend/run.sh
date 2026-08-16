#!/usr/bin/env bash
# EV launcher for WSL2 / headless Linux.
#
# WSL2 has no system audio libs; scripts/setup_wsl2_audio.sh installs a
# ROOTLESS copy of the audio stack (ALSA -> PulseAudio -> WSLg) into
# $EV_AUDIO_PREFIX (default ~/.local/ev-audio). This script points the process
# at it and then runs EV normally.
#
# On a regular Linux/macOS/Windows install you don't need this script —
# just `python main.py`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${EV_AUDIO_PREFIX:-$HOME/.local/ev-audio}"

if [ -d "$PREFIX/usr/lib/x86_64-linux-gnu" ]; then
    export LD_LIBRARY_PATH="$PREFIX/usr/lib/x86_64-linux-gnu:$PREFIX/usr/lib/x86_64-linux-gnu/pulseaudio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export ALSA_CONFIG_PATH="${ALSA_CONFIG_PATH:-$PREFIX/usr/share/alsa/alsa.conf}"
fi
export PULSE_SERVER="${PULSE_SERVER:-unix:/mnt/wslg/PulseServer}"

exec "$HERE/.venv/bin/python" "$HERE/main.py" "$@"
