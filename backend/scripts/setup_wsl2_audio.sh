#!/usr/bin/env bash
# Install a ROOTLESS audio stack (ALSA -> Pulse -> WSLg) for EV on WSL2.
#
# Why: WSL2 exposes no ALSA sound cards. Windows audio reaches Linux through
# WSLg's PulseAudio daemon (unix:/mnt/wslg/PulseServer), but Ubuntu's WSL2
# image ships no audio libraries at all. This script downloads the needed
# .debs and extracts them into $EV_AUDIO_PREFIX (default ~/.local/ev-audio),
# which run.sh points the process at — no sudo required.
#
# If you have sudo, the equivalent one-liner is:
#   sudo apt install -y libasound2t64 libasound2-plugins libportaudio2
#
# Usage: bash scripts/setup_wsl2_audio.sh
set -euo pipefail

PREFIX="${EV_AUDIO_PREFIX:-$HOME/.local/ev-audio}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PACKAGES=(
    libasound2t64 libasound2-plugins libpulse0 libportaudio2 libsndfile1
    libsystemd0 libcap2 libdbus-1-3 liblzma5 libzstd1 liblz4-1 libapparmor1
    libgcrypt20 libgpg-error0 libffi8 libjack-jackd2-0 libasyncns0
    libflac14 libvorbis0a libvorbisenc2 libopus0 libogg0 libmpg123-0t64
    libmp3lame0 alsa-ucm-conf
)

APT_OPTS=(
    -o "Dir::State::Lists=$WORK/lists"
    -o "Dir::Cache=$WORK/cache"
    -o "Dir::State::status=$WORK/status"
)

mkdir -p "$WORK/lists" "$WORK/cache" "$WORK/debs"

echo ">> apt update (rootless, into $WORK)"
apt-get update "${APT_OPTS[@]}" >/dev/null

echo ">> downloading ${#PACKAGES[@]} packages"
cd "$WORK/debs"
apt-get download "${APT_OPTS[@]}" "${PACKAGES[@]}" >/dev/null

echo ">> extracting into $PREFIX"
mkdir -p "$PREFIX"
for f in "$WORK"/debs/*.deb; do
    dpkg-deb -x "$f" "$PREFIX"
done

# the main ALSA config is not shipped by any Ubuntu package — install the
# canonical one from the alsa-lib release and point it at our prefix.
echo ">> installing ALSA master config"
curl -fsSL https://raw.githubusercontent.com/alsa-project/alsa-lib/v1.2.15/src/conf/alsa.conf \
    | sed \
        -e "s|/var/lib/alsa/conf.d|$PREFIX/usr/share/alsa/alsa.conf.d|g" \
        -e "s|/usr/etc/alsa/conf.d|$PREFIX/usr/share/alsa/alsa.conf.d|g" \
        -e "s|/etc/alsa/conf.d|$PREFIX/usr/share/alsa/alsa.conf.d|g" \
        -e "s|/alsa/asoundrc|$PREFIX/usr/share/alsa/asoundrc|g" \
    > "$PREFIX/usr/share/alsa/alsa.conf"

# route the ALSA default device to PulseAudio so sounddevice/PortAudio "just works"
if [ ! -f "$HOME/.asoundrc" ]; then
    echo ">> writing $HOME/.asoundrc (ALSA default -> Pulse)"
    cat > "$HOME/.asoundrc" <<EOF
pcm.!default {
    type pulse
    hint { show on description "PulseAudio via WSLg" }
}
ctl.!default {
    type pulse
}
EOF
fi

echo ">> done. Verify with: ./run.sh --list-devices"
