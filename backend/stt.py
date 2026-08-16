"""Stage 2: speech-to-text via faster-whisper (local, CPU/GPU-capable).

Pipeline position: ... -> [STT] -> LLM ...

Latency note
------------
Whisper transcription is CPU-bound and BLOCKS the calling thread. That is fine
for the v1 push-to-talk loop, but when we add wake-word or barge-in the
transcribe() call should move to a worker thread so the capture/trigger stays
responsive (see main.py's `--once` path for the seam).

v2 extension points
-------------------
- transcribe_partial(): incremental transcription of an in-progress utterance.
  faster-whisper can emit partial segments; the low-latency scheme is to
  transcribe overlapping windows and keep the stable prefix (start the LLM
  before the user finishes speaking).
- ASR swap: this class is the only place faster-whisper is imported, so a
  different engine (e.g. an API STT) can replace it behind the same
  `transcribe()` contract.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from config import STTConfig

log = logging.getLogger("ev.stt")


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str | None
    confidence: float  # mean per-token log-probability across segments (<= 0.0)
    duration_s: float  # seconds of audio transcribed

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class STTEngine:
    def __init__(self, config: STTConfig) -> None:
        self._config = config
        self._model = None  # loaded lazily so --list-devices stays fast

    def _ensure_model(self):
        if self._model is None:
            t0 = time.perf_counter()
            log.info(
                "loading whisper model %r (%s/%s)...",
                self._config.model, self._config.device, self._config.compute_type,
            )
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self._config.model,
                device=self._config.device,
                compute_type=self._config.compute_type,
            )
            log.info(
                "model loaded in %.1fs", time.perf_counter() - t0,
            )
        return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> Transcription:
        """Transcribe a float32 mono clip. Returns empty Transcription on silence."""
        model = self._ensure_model()
        if audio.size == 0:
            return Transcription("", None, 0.0, 0.0)

        t0 = time.perf_counter()
        segments, info = model.transcribe(
            audio,
            language=self._config.language,
            beam_size=self._config.beam_size,
            vad_filter=self._config.vad_filter,
            without_timestamps=True,
        )
        words: list[str] = []
        logprobs: list[float] = []
        for segment in segments:  # segments is a generator — iterating runs the model
            words.append(segment.text)
            logprobs.append(float(segment.avg_logprob))

        elapsed = time.perf_counter() - t0
        text = " ".join(words).strip()
        confidence = float(np.mean(logprobs)) if logprobs else 0.0
        log.info(
            "stt: %.2fs audio -> %.2fs compute | text=%.60r conf=%.2f lang=%s",
            audio.size / sample_rate, elapsed, text, confidence, info.language,
        )
        return Transcription(
            text=text,
            language=info.language,
            confidence=confidence,
            duration_s=audio.size / sample_rate,
        )
