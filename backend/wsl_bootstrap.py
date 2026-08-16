"""WSL2 audio bootstrap — must be imported BEFORE sounddevice (i.e. before
audio_input, which is imported first by main.py).

WSL2 exposes no ALSA cards; audio goes through WSLg's PulseAudio server at
`unix:/mnt/wslg/PulseServer`. There is no system libasound/libportaudio, so the
`scripts/setup_wsl2_audio.sh` script installs a ROOTLESS copy of the audio
stack into `$EV_AUDIO_PREFIX` (default ~/.local/ev-audio), and this module
teaches the running process how to find it.

Two mechanisms, both idempotent and harmless on normal systems:
  1. os.environ fixes for PULSE_SERVER / ALSA_CONFIG_PATH (read by alsa-lib /
     PortAudio when they open devices).
  2. ctypes.util.find_library patch so sounddevice can dlopen libportaudio
     from the prefix even though it is not in the system ldconfig cache.
     (LD_LIBRARY_PATH must be set at process start — run.sh does that; here we
     additionally preload the prefix libraries via ctypes so the process works
     even without run.sh.)
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import os
import platform
import sys

log = logging.getLogger("ev.wsl")

_DEFAULT_PREFIX = os.path.expanduser("~/.local/ev-audio")
_BOOTSTRAPPED = False


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft-standard-WSL2" in platform.release()
    except OSError:
        return False


def _lib_dir(prefix: str) -> str | None:
    cand = os.path.join(prefix, "usr", "lib", "x86_64-linux-gnu")
    return cand if os.path.isdir(cand) else None


def _preload(prefix: str) -> None:
    """dlopen the prefix's shared libraries in dependency order so dlopen() of
    libportaudio by its resolved path finds every transitive dependency already
    loaded, without needing LD_LIBRARY_PATH from a launcher script."""
    libdir = _lib_dir(prefix)
    if not libdir:
        return
    # dependency order matters; entries that don't exist are skipped.
    sonames = (
        "libgpg-error.so.0", "libgcrypt.so.20", "libsystemd.so.0",
        "libdbus-1.so.3", "libcap.so.2", "liblzma.so.5", "libzstd.so.1",
        "liblz4.so.1", "libffi.so.8", "libapparmor.so.1", "libasyncns.so.0",
        "libogg.so.0", "libvorbis.so.0", "libvorbisenc.so.2", "libopus.so.0",
        "libmpg123.so.0", "libmp3lame.so.0", "libFLAC.so.14", "libsndfile.so.1",
        "pulseaudio/libpulsecommon-17.0.so", "libpulse.so.0", "libjack.so.0",
        "libasound.so.2", "libportaudio.so.2",
    )
    for name in sonames:
        path = os.path.join(libdir, name)
        if not os.path.exists(path):
            continue
        try:
            ctypes.CDLL(path)
        except OSError as exc:  # e.g. a dep is missing; report once and carry on
            log.warning("could not preload %s: %s", path, exc)


def _patch_find_library(prefix: str) -> None:
    libdir = _lib_dir(prefix)
    if not libdir:
        return
    original = ctypes.util.find_library

    def find_library(name: str) -> str | None:
        resolved = original(name)
        if resolved is not None:
            return resolved
        # ctypes.util.find_library only consults the ldconfig cache; our prefix
        # isn't in it, so fall back to a direct path lookup.
        for soname in (f"lib{name}.so.2", f"lib{name}.so"):
            path = os.path.join(libdir, soname)
            if os.path.exists(path):
                return path
        return None

    ctypes.util.find_library = find_library


def bootstrap() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    if not _is_wsl():
        _BOOTSTRAPPED = True
        return

    prefix = os.environ.get("EV_AUDIO_PREFIX", _DEFAULT_PREFIX)
    os.environ.setdefault("PULSE_SERVER", "unix:/mnt/wslg/PulseServer")
    alsa_conf = os.path.join(prefix, "usr", "share", "alsa", "alsa.conf")
    if os.path.exists(alsa_conf):
        os.environ.setdefault("ALSA_CONFIG_PATH", alsa_conf)
    _preload(prefix)
    _patch_find_library(prefix)
    _BOOTSTRAPPED = True
    log.debug("WSL2 audio bootstrap active (prefix=%s)", prefix)
