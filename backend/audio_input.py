"""Stage 1: microphone capture with a trigger (wake word by default, or
push-to-talk).

Pipeline position:  Mic Input -> [Trigger] -> STT -> ...

Design notes
------------
* Capture runs continuously from stream start into a TIMESTAMPED ring buffer,
  so the trigger has zero start latency and we can slice pre-roll audio (audio
  spoken just before activation). It also means the wake-word trigger can be
  dropped in with zero changes to capture or downstream stages.
* The ring buffer keeps ~ring_seconds of audio in memory (16 kHz float32 mono
  is ~64 KB/s — negligible).

Triggers
--------
* WakeWordTrigger (default): openWakeWord local CPU inference on every mic
  block. Activation fires when a wake word scores above the threshold;
  deactivation fires on trailing silence (with a grace period so a pause right
  after the wake word doesn't cut the request off).
* PushToTalk: hold a key to talk, release to send (see class docstring).

v2 extension points
-------------------
- Barge-in: while EV is speaking, keep the capture running and start a new
  utterance — the trigger + ring buffer already support this; only the
  speak-stage scheduling in main.py needs work.
- VAD-gated capture: a `Trigger` that activates on speech energy instead of a
  wake word is the same interface.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from pathlib import Path
from typing import Callable

import numpy as np

import wsl_bootstrap  # must precede sounddevice import (WSL2 audio prefix)

wsl_bootstrap.bootstrap()

import sounddevice as sd  # noqa: E402,F401  (re-exported for main.py --list-devices)

from config import AudioConfig  # noqa: E402

log = logging.getLogger("ev.audio")

_KeyCallback = Callable[[str], None]
_ScoreCallback = Callable[[float, float, float], None]  # timestamp, score, noise


# --------------------------------------------------------------------------- #
# Key hooks — a platform abstraction over "global keyboard press/release".
# pynput uses the X11 backend on Linux (works under WSLg); terminals without a
# global hook fall back to StdinKeyHook (toggle semantics — terminals cannot
# report key release).
# --------------------------------------------------------------------------- #
class KeyHook(ABC):
    """Abstract global keyboard hook. Implementations call on_press/on_release
    with a normalized key name (e.g. 'space', 'enter')."""

    on_press: _KeyCallback | None = None
    on_release: _KeyCallback | None = None

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...


class PynputKeyHook(KeyHook):
    """Global key hook via pynput (X11 on Linux, CoreGraphics on macOS, Win32
    hooks on Windows)."""

    def __init__(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as exc:  # pragma: no cover - platform dependent
            raise RuntimeError(
                "pynput not available; fall back to StdinKeyHook" 
            ) from exc
        self._keyboard = keyboard
        self._listener: keyboard.Listener | None = None

    @staticmethod
    def _normalize(key) -> str | None:
        try:
            return getattr(key, "name", None) or key.char
        except (AttributeError, ValueError):
            return None

    def start(self) -> None:
        def on_press(key) -> None:
            name = self._normalize(key)
            if name and self.on_press:
                self.on_press(name)

        def on_release(key) -> None:
            name = self._normalize(key)
            if name and self.on_release:
                self.on_release(name)

        self._listener = self._keyboard.Listener(
            on_press=on_press, on_release=on_release
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None


class StdinKeyHook(KeyHook):
    """Terminal fallback: reads raw stdin bytes in a thread. Terminals can't
    report key-up, so this is toggle-based: the target key flips active/inactive
    on each press. Space = start/stop. Enter = also accepted."""

    def __init__(self, key: str = "space") -> None:
        import termios

        self._key = key.encode()
        self._termios = termios
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._toggled = False

    def start(self) -> None:
        import sys

        fd = sys.stdin.fileno()
        self._old = self._termios.tcgetattr(fd)
        new = self._termios.tcgetattr(fd)
        new[3] &= ~(self._termios.ICANON | self._termios.ECHO)
        self._termios.tcsetattr(fd, self._termios.TCSANOW, new)
        self._thread = threading.Thread(
            target=self._run, args=(sys.stdin,), daemon=True, name="stdin-key"
        )
        self._thread.start()

    def _run(self, stdin) -> None:
        while not self._stop_event.is_set():
            try:
                ch = stdin.read(1)
            except (ValueError, OSError):
                break
            if not ch:
                continue
            if ch.encode() in (self._key, b"\n", b"\r"):
                self._toggled = not self._toggled
                if self._toggled and self.on_press:
                    self.on_press(ch)
                elif not self._toggled and self.on_release:
                    self.on_release(ch)

    def stop(self) -> None:
        import sys

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        try:
            self._termios.tcsetattr(
                sys.stdin.fileno(), self._termios.TCSANOW, self._old
            )
        except Exception:  # pragma: no cover
            pass


def default_key_hook(key: str = "space") -> KeyHook:
    """Prefer the global hook (hold-to-talk); fall back to the terminal toggle."""
    try:
        hook = PynputKeyHook()
        hook.start()
        return hook
    except Exception as exc:  # pragma: no cover - platform dependent
        log.warning("global key hook unavailable (%s); using terminal toggle", exc)
        hook = StdinKeyHook(key)
        hook.start()
        return hook


# --------------------------------------------------------------------------- #
# Trigger — the "when to listen" abstraction.
# --------------------------------------------------------------------------- #
class Trigger(ABC):
    """Who decides an utterance started and ended. v2: WakeWordTrigger implements
    the same contract and replaces PushToTalk at the call site in main.py."""

    @abstractmethod
    def wait_for_activation(self, timeout: float | None = None) -> bool:
        """Block until the user starts speaking. Returns True if activated, False on timeout."""

    @abstractmethod
    def wait_for_deactivation(self) -> None:
        """Block until the user stops speaking."""

    @property
    def activation_time(self) -> float:
        """Monotonic timestamp when the activation occurred."""
        return getattr(self, "_activation_ts", 0.0) or time.monotonic()

    def set_enabled(self, enabled: bool) -> None:  # noqa: ARG002 - base no-op
        """Ignore activations while disabled (EV busy)."""

    def quiet_until(self, until: float) -> None:  # noqa: ARG002
        """Temporarily mute wake detection until monotonic timestamp."""

    def continue_listening(self) -> None:
        """Keep listening without requiring a new wake trigger."""

    def press(self) -> None:
        """Manual / Web-triggered PTT press."""

    def release(self) -> None:
        """Manual / Web-triggered PTT release."""

    def reset_audio(self) -> None:  # noqa: ARG002 - base no-op
        """Reset internal frame buffers after speech output."""

    def close(self) -> None:  # optional cleanup
        pass


class PushToTalk(Trigger):
    """Hold the configured key to talk, release to send.

    With a global hook (X11/macOS/Windows) this is hold-to-talk. With the stdin
    fallback it degrades to press-to-toggle (terminals don't report key-up).
    """

    def __init__(self, hook: KeyHook, key: str = "space") -> None:
        self._hook = hook
        self._key = key
        self._active = False
        self._activation_ts = 0.0
        self._activated = threading.Event()
        self._deactivated = threading.Event()
        self._deactivated.set()  # start in the released state
        hook.on_press = self._on_press
        hook.on_release = self._on_release

    def quiet_until(self, until: float) -> None:  # noqa: ARG002
        pass

    def continue_listening(self) -> None:
        pass

    def press(self) -> None:
        """External software/web trigger press."""
        self._on_press(self._key)

    def release(self) -> None:
        """External software/web trigger release."""
        self._on_release(self._key)

    def _on_press(self, key: str) -> None:
        if key == self._key and not self._active:
            self._active = True
            self._activation_ts = time.monotonic()
            self._deactivated.clear()
            self._activated.set()
            log.debug("PTT activated")

    def _on_release(self, key: str) -> None:
        if key == self._key and self._active:
            self._active = False
            self._activated.clear()
            self._deactivated.set()
            log.debug("PTT deactivated")

    def wait_for_activation(self, timeout: float | None = None) -> bool:
        res = self._activated.wait(timeout=timeout)
        if res:
            self._activated.clear()
        return res

    def wait_for_deactivation(self) -> None:
        self._deactivated.wait()

    def close(self) -> None:
        self._hook.stop()


class WakeWordTrigger(Trigger):
    """Always-listening activation: openWakeWord runs on every mic block and
    fires when a wake word (default 'alexa') scores above the threshold.
    Deactivation is trailing silence: after a short grace period (so a pause
    right after the wake word isn't a false end), N quiet frames end the
    utterance. The max utterance duration is also enforced here.

    Feed it audio with `on_audio(timestamp, block)` — typically wired to
    `MicCapture(sink=...)` so it sees exactly what the ring buffer captures.
    """

    def __init__(self, config: AudioConfig, on_score: _ScoreCallback | None = None) -> None:
        try:
            from openwakeword.model import Model
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "openwakeword not installed — `pip install openwakeword` "
                "(or use EV_TRIGGER=ptt)"
            ) from exc

        self._on_score = on_score  # optional live telemetry hook (web HUD)

        models = config.wake_word_models or ("hey_jarvis",)
        paths: list[str] = []
        for name in models:
            path = Path(name)
            if path.is_file():
                paths.append(str(path))
                continue
            bundled_dir = (
                Path(__import__("openwakeword").__file__).parent
                / "resources" / "models"
            )
            matches = sorted(bundled_dir.glob(f"{name}*.onnx"))
            if matches:
                paths.append(str(matches[0]))
                continue
            if config.wake_word_weights:
                continue  # custom classifier below; bundled name may be nominal
            raise RuntimeError(f"wake word model not found: {name!r}")

        if config.wake_word_weights:
            self._model: object = _CustomWakeScorer(config.wake_word_weights)
            log.info("wake word: custom classifier %s", config.wake_word_weights)
        else:
            log.info("wake word models: %s", [Path(p).stem for p in paths])
            self._model: object = Model(wakeword_model_paths=paths)
        self._threshold = config.wake_word_threshold
        self._min_frames = max(1, config.wake_min_frames)
        self._silence_rms = config.wake_silence_rms
        frames = int(
            config.wake_end_silence_seconds * config.sample_rate / config.blocksize
        )
        self._end_silence_frames = max(1, frames)
        self._grace_seconds = config.wake_grace_seconds
        self._max_seconds = config.max_utterance_seconds

        self._activated = threading.Event()
        self._deactivated = threading.Event()
        self._deactivated.set()  # start in the "not listening" state
        self._listening = False
        self._listening_since = 0.0
        self._quiet_frames = 0
        self._lock = threading.Lock()
        # True while EV is busy (STT/LLM/TTS): wake words are ignored so a
        # user repeating "alexa" during the wait can't spam re-triggers
        self._enabled = True
        # (monotonic, best score) samples, newest last; diagnostics only
        self._score_history: deque[tuple[float, float]] = deque(maxlen=1200)
        # rolling wake-word window: score overlapping 1280-sample (80ms)
        # frames at 640-sample (40ms) hops. Empirical: feeding raw capture
        # blocks straight to the model's internal streaming buffer scores
        # ~10x lower than these tight overlapping frames.
        self._frame_hop = 640
        self._frame_size = 1280
        self._frame_buf: list[np.ndarray] = []  # pending float32 samples
        # consecutive frames >= threshold needed for a wake. Real 'Sara'
        # (v9 full-utterance classifier) sustains it for the whole word
        # (~12-18 frames); ambient noise spikes top out at 3 frames.
        self._consecutive = 0
        # ignore wake words until this monotonic timestamp (set after
        # noise-caused empty turns so the ambient can't re-trigger instantly)
        self._quiet_until = 0.0
        self._warmup_until = time.monotonic() + 1.2
        # rolling per-block RMS (last 30s) -> adaptive noise floor for the
        # end-of-utterance silence check (mic noise floors vary wildly)
        self._rms_history: deque[float] = deque(maxlen=int(30.0 / (config.blocksize / config.sample_rate)))
        self._noise_floor = 0.0

    def on_audio(self, timestamp: float, audio: np.ndarray) -> None:
        """Process one captured block. Called from the capture thread."""
        if audio.size == 0:
            return
        with self._lock:
            if not self._enabled:
                return
            if self._quiet_until and timestamp < self._quiet_until:
                return
            if self._listening:
                self._listen_state(timestamp, audio)
                return
            self._frame_buf.append(audio)
            pending = np.concatenate(self._frame_buf)
            while pending.size >= self._frame_size:
                frame = pending[: self._frame_size]
                pending = pending[self._frame_hop :]
                best = self._score_frame(frame)
                self._score_history.append((timestamp, best))
                if self._on_score is not None:
                    self._on_score(timestamp, best, self._noise_floor)
                
                if timestamp < self._warmup_until:
                    # Ignore trigger during stream warmup
                    self._consecutive = 0
                    continue

                self._consecutive = self._consecutive + 1 if best >= self._threshold else 0
                if self._consecutive >= self._min_frames:
                    self._consecutive = 0
                    self._listening = True
                    self._listening_since = timestamp
                    self._activation_ts = timestamp
                    self._quiet_frames = 0
                    self._noise_floor = float(np.median(self._rms_history)) if self._rms_history else 0.0
                    self._deactivated.clear()
                    self._activated.set()
                    log.info("wake word detected (score=%.3f) noise=%.4f", best, self._noise_floor)
                    break
            self._frame_buf = [pending] if pending.size else []
            self._rms_history.append(
                float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
            )

    def _score_frame(self, frame: np.ndarray) -> float:
        # openWakeWord expects int16 PCM; capture delivers float32 -1..1,
        # and feeding floats directly makes the mel-spectrogram see ~silence
        audio_i16 = np.clip(frame * 32767.0, -32768, 32767).astype(np.int16)
        scores = self._model.predict(audio_i16)
        return max(
            float(max(v)) if hasattr(v, "__len__") else float(v)
            for v in scores.values()
        )

    def _listen_state(self, timestamp: float, audio: np.ndarray) -> None:
        if timestamp - self._listening_since >= self._max_seconds:
            log.info("utterance reached %.1fs cap — ending", self._max_seconds)
            self._stop_listening()
            return
        if timestamp < self._listening_since + self._grace_seconds:
            return  # grace period: give the user time to start the request
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
        # Robust adaptive silence detection: triggers cleanly even with ambient mic hum
        threshold = max(self._silence_rms, self._noise_floor * 1.25 + 0.012, 0.03)
        if rms < threshold:
            self._quiet_frames += 1
            if self._quiet_frames >= self._end_silence_frames:
                self._stop_listening()
        else:
            self._quiet_frames = 0

    def _stop_listening(self) -> None:
        self._listening = False
        self._quiet_frames = 0
        self._consecutive = 0
        self._frame_buf = []  # drop stale wake-word audio so it can't re-trigger
        self._deactivated.set()

    def wait_for_activation(self, timeout: float | None = None) -> bool:
        res = self._activated.wait(timeout=timeout)
        if res:
            self._activated.clear()
        return res

    def wait_for_deactivation(self) -> None:
        self._deactivated.wait()

    def set_enabled(self, enabled: bool) -> None:
        """Ignore wake words while disabled (EV is processing a turn)."""
        with self._lock:
            self._enabled = enabled
            if not enabled:
                self._listening = False
                self._quiet_frames = 0
                self._consecutive = 0
                self._frame_buf = []
                self._deactivated.set()

    def set_threshold(self, value: float) -> None:
        """Adjust the wake-word acceptance threshold at runtime (web HUD)."""
        with self._lock:
            self._threshold = min(1.0, max(0.1, float(value)))

    def quiet_until(self, until: float) -> None:
        """Suppress wake-word firing until the given monotonic timestamp
        (used after a noise-caused empty turn)."""
        with self._lock:
            self._quiet_until = max(self._quiet_until, until)
            self._consecutive = 0

    def reset_audio(self) -> None:
        """Reset internal frame buffers and state after audio playback."""
        with self._lock:
            self._frame_buf = []
            self._quiet_frames = 0
            self._consecutive = 0

    def continue_listening(self) -> None:
        """Re-enter listening right after a wake, without requiring a new
        wake word. Used when the captured turn contained only the wake word
        (e.g. 'Sara' with the real request following a pause)."""
        with self._lock:
            if not self._enabled:
                return
            self._listening = True
            self._listening_since = time.monotonic()
            self._quiet_frames = 0
            self._consecutive = 0
            self._frame_buf = []
            self._deactivated.clear()
            self._activated.set()

    def press(self) -> None:
        """Manual / Web-triggered PTT press — force activation immediately."""
        with self._lock:
            if not self._enabled:
                return
            self._listening = True
            self._activation_ts = time.monotonic()
            self._listening_since = self._activation_ts
            self._quiet_frames = 0
            self._consecutive = 0
            self._frame_buf = []
            self._deactivated.clear()
            self._activated.set()
            log.info("WakeWordTrigger: manual web PTT press activated")

    def release(self) -> None:
        """Manual / Web-triggered PTT release — force deactivation and process speech."""
        with self._lock:
            if self._listening:
                self._listening = False
                self._activated.clear()
                self._quiet_frames = 0
                self._consecutive = 0
                self._frame_buf = []
                self._deactivated.set()
                log.info("WakeWordTrigger: manual web PTT release deactivated")

    def close(self) -> None:
        pass  # model objects are cheap; nothing to tear down


# --------------------------------------------------------------------------- #
# Capture
# --------------------------------------------------------------------------- #
class _CustomWakeScorer:
    """Trained 'Sara' wake-word classifier (train_sara.py output).

    Mirrors the openwakeword streaming pipeline (mel -> speech embedding ->
    classifier) but replaces the bundled phrase models with a logistic
    regression trained on user/TTS samples. `predict(frame_i16)` returns a
    {model: score} dict, matching the bundled Model() interface.
    """

    def __init__(self, weights_path: str) -> None:
        from openwakeword.utils import AudioFeatures

        path = Path(weights_path)
        if not path.is_absolute():
            path = Path(__file__).parent / path
        data = np.load(path)
        self._coef = data["coef"].astype(np.float32)
        self._intercept = float(data["intercept"][0])
        self._scale = data["scale"].astype(np.float32)
        self._mean = data["mean"].astype(np.float32)
        self._af = AudioFeatures()
        # v8 context feature: peak RMS over the last ~360ms (9 frames),
        # mirroring the training script's predecessor-energy dimension
        self._rms_hist: deque[float] = deque(maxlen=9)

    def predict(self, frame: np.ndarray) -> dict[str, np.float32]:
        self._af(frame)
        feats = self._af.get_features(16).reshape(-1).astype(np.float32)
        rms = float(np.sqrt(np.mean(frame.astype(np.float64) ** 2))) / 32767.0
        self._rms_hist.append(rms)
        if len(self._coef) == feats.size + 1:
            feats = np.append(feats, max(self._rms_hist))
        z = float(np.dot((feats - self._mean) / self._scale, self._coef) + self._intercept)
        return {"sara": np.float32(1.0 / (1.0 + np.exp(-z)))}


class MicCapture:
    """Continuous microphone capture into a timestamped ring buffer.

    Always-on by design (see module docstring). Call read_from(t0) to get every
    sample captured at or after the monotonic timestamp t0.
    """

    def __init__(self, config: AudioConfig, sink: Callable[[float, np.ndarray], None] | None = None) -> None:
        self._config = config
        self._sink = sink
        self._chunks: deque[tuple[float, np.ndarray]] = deque()
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    @property
    def sample_rate(self) -> int:
        return self._config.sample_rate

    def start(self) -> None:
        cfg = self._config
        device = None
        if cfg.input_device:
            device = _resolve_device(cfg.input_device, kind="input")
            if device is None:
                raise RuntimeError(f"input device not found: {cfg.input_device!r}")

        max_frames = int(cfg.ring_seconds * cfg.sample_rate)

        def callback(indata, frames, time_info, status) -> None:  # noqa: ARG001
            if status:
                log.debug("capture status: %s", status)
            ts = time.monotonic()
            chunk = indata.copy()
            if cfg.channels == 1:
                # flatten (frames, 1) -> (frames,) so sinks (wake word) and
                # read_from() consumers get plain 1D mono audio
                chunk = chunk.reshape(-1)
            with self._lock:
                self._chunks.append((ts, chunk))
                # drop chunks older than the ring window (timestamped, so
                # read_from() slicing is exact)
                oldest = ts - cfg.ring_seconds
                while self._chunks and self._chunks[0][0] < oldest:
                    self._chunks.popleft()
            if self._sink is not None:
                try:
                    self._sink(ts, chunk)
                except Exception:  # noqa: BLE001 - a sink bug must never kill capture
                    log.exception("capture sink failed")

        self._stream = sd.InputStream(
            samplerate=cfg.sample_rate,
            channels=cfg.channels,
            dtype="float32",
            blocksize=cfg.blocksize,
            device=device,
            callback=callback,
        )
        self._stream.start()
        log.debug(
            "capture started: %d Hz, %d ch, device=%r",
            cfg.sample_rate, cfg.channels, device,
        )

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def flush(self, until_monotonic: float | None = None) -> None:
        """Discard recorded audio chunks up to `until_monotonic` (or all chunks if None).
        Prevents audio output from speaker from leaking into subsequent microphone reads."""
        with self._lock:
            if until_monotonic is None:
                self._chunks.clear()
            else:
                while self._chunks and self._chunks[0][0] <= until_monotonic:
                    self._chunks.popleft()

    def read_from(self, start_monotonic: float) -> np.ndarray:
        """Concatenated float32 audio captured at/after `start_monotonic`.

        Returns an empty array when nothing was captured (e.g. a very short tap).
        """
        with self._lock:
            chunks = [c for t, c in self._chunks if t >= start_monotonic]
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(chunks)
        if self._config.channels == 1:
            return audio.reshape(-1)
        return audio


def _resolve_device(selector: str, kind: str) -> int | None:
    """Resolve a device by index or by name substring; None = not found."""
    del kind  # reserved for future output/input disambiguation
    try:
        idx = int(selector)
    except ValueError:
        idx = None
    devices = sd.query_devices()
    if idx is not None and 0 <= idx < len(devices):
        return idx
    needle = selector.lower()
    for i, dev in enumerate(devices):
        if needle in dev["name"].lower():
            return i
    return None


def list_devices() -> None:
    """Human-readable device listing for `main.py --list-devices`."""
    devices = sd.query_devices()
    print(sd.query_devices(device=None))  # noqa: T201
