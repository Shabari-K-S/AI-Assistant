"""Stage 2: speech-to-text via faster-whisper (local) or cloud STT (Gemini / Groq).

Pipeline position: ... -> [STT] -> LLM ...

Supports:
- provider="local": faster-whisper on desktop/WSL2
- provider="gemini": Google Gemini audio transcription (zero C++ dependencies, perfect for Termux/NetHunter/Android)
- provider="groq": Groq Whisper API (free, ultra-fast ~100ms)
- Automatic fallback: If local faster-whisper is not installed/working in NetHunter/Termux, automatically falls back to Gemini STT.
"""

from __future__ import annotations

import io
import logging
import time
import wave
from dataclasses import dataclass

import numpy as np

from config import STTConfig

log = logging.getLogger("ev.stt")


def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Convert float32 mono numpy array to 16-bit PCM WAV bytes in memory."""
    pcm16 = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


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
        self._provider = config.provider.lower()
        self._local_model = None
        self._gemini_client = None

    def _ensure_local_model(self):
        if self._local_model is None:
            t0 = time.perf_counter()
            log.info(
                "loading whisper model %r (%s/%s)...",
                self._config.model, self._config.device, self._config.compute_type,
            )
            from faster_whisper import WhisperModel

            self._local_model = WhisperModel(
                self._config.model,
                device=self._config.device,
                compute_type=self._config.compute_type,
            )
            log.info("model loaded in %.1fs", time.perf_counter() - t0)
        return self._local_model

    def _ensure_gemini_client(self):
        if self._gemini_client is None:
            from google import genai

            self._gemini_client = genai.Client(api_key=self._config.api_key)
        return self._gemini_client

    def _transcribe_gemini(self, audio: np.ndarray, sample_rate: int) -> Transcription:
        t0 = time.perf_counter()
        wav_bytes = _audio_to_wav_bytes(audio, sample_rate)
        client = self._ensure_gemini_client()
        from google.genai import types

        part = types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")
        prompt = (
            "Transcribe the exact spoken words in this audio recording. "
            "Return ONLY the plain transcribed text without quotes, formatting, or commentary."
        )

        candidate_models = []
        if "gemini" in self._config.model:
            candidate_models.append(self._config.model)
        candidate_models.extend(["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"])

        last_exc = None
        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[part, prompt],
                    config=types.GenerateContentConfig(
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                        temperature=0.0,
                    ),
                )
                text = (response.text or "").strip()
                elapsed = time.perf_counter() - t0
                log.info(
                    "gemini stt (%s): %.2fs audio -> %.2fs compute | text=%.60r",
                    model_name, audio.size / sample_rate, elapsed, text,
                )
                return Transcription(
                    text=text,
                    language="en",
                    confidence=0.0,
                    duration_s=audio.size / sample_rate,
                )
            except Exception as exc:
                last_exc = exc
                log.debug("Gemini STT model %s failed: %s; trying next candidate", model_name, exc)
                continue

        log.error("All Gemini STT candidate models failed: %s", last_exc)
        return Transcription("", None, -2.0, audio.size / sample_rate)

    def _transcribe_groq(self, audio: np.ndarray, sample_rate: int) -> Transcription:
        t0 = time.perf_counter()
        wav_bytes = _audio_to_wav_bytes(audio, sample_rate)
        import httpx

        try:
            files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
            data = {"model": "whisper-large-v3"}
            headers = {"Authorization": f"Bearer {self._config.api_key}"}
            res = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                files=files,
                data=data,
                headers=headers,
                timeout=15.0,
            )
            res.raise_for_status()
            text = str(res.json().get("text") or "").strip()
            elapsed = time.perf_counter() - t0
            log.info(
                "groq stt: %.2fs audio -> %.2fs compute | text=%.60r",
                audio.size / sample_rate, elapsed, text,
            )
            return Transcription(
                text=text,
                language="en",
                confidence=0.0,
                duration_s=audio.size / sample_rate,
            )
        except Exception:
            log.exception("Groq Whisper transcription failed")
            return Transcription("", None, -2.0, audio.size / sample_rate)

    def _transcribe_google_free(self, audio: np.ndarray, sample_rate: int) -> Transcription:
        t0 = time.perf_counter()
        wav_bytes = _audio_to_wav_bytes(audio, sample_rate)
        import speech_recognition as sr

        r = sr.Recognizer()
        try:
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio_data = r.record(source)
            lang = self._config.language or "en-US"
            text = r.recognize_google(audio_data, language=lang)
            text = str(text or "").strip()
            elapsed = time.perf_counter() - t0
            log.info(
                "google speech recognition: %.2fs audio -> %.2fs compute | text=%.60r",
                audio.size / sample_rate, elapsed, text,
            )
            return Transcription(
                text=text,
                language=lang,
                confidence=0.0,
                duration_s=audio.size / sample_rate,
            )
        except sr.UnknownValueError:
            # Audio was silence or unparseable
            return Transcription("", None, 0.0, audio.size / sample_rate)
        except Exception:
            log.exception("Google Speech Recognition failed")
            return Transcription("", None, -2.0, audio.size / sample_rate)

    def _transcribe_local(self, audio: np.ndarray, sample_rate: int) -> Transcription:
        model = self._ensure_local_model()
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
        for segment in segments:
            words.append(segment.text)
            logprobs.append(float(segment.avg_logprob))

        elapsed = time.perf_counter() - t0
        text = " ".join(words).strip()
        confidence = float(np.mean(logprobs)) if logprobs else 0.0
        log.info(
            "local stt: %.2fs audio -> %.2fs compute | text=%.60r conf=%.2f lang=%s",
            audio.size / sample_rate, elapsed, text, confidence, info.language,
        )
        return Transcription(
            text=text,
            language=info.language,
            confidence=confidence,
            duration_s=audio.size / sample_rate,
        )

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> Transcription:
        """Transcribe a float32 mono clip. Returns empty Transcription on silence."""
        if audio.size == 0:
            return Transcription("", None, 0.0, 0.0)

        # 1. Google Speech Recognition (100% Free, zero API key, zero C++ deps)
        if self._provider in ("google", "speechrecognition", "speech_recognition", "free"):
            return self._transcribe_google_free(audio, sample_rate)

        # 2. Google Gemini API
        if self._provider == "gemini":
            return self._transcribe_gemini(audio, sample_rate)

        # 3. Groq Whisper API
        if self._provider == "groq":
            return self._transcribe_groq(audio, sample_rate)

        # 4. Local faster-whisper with automatic fallback for NetHunter / Termux
        try:
            return self._transcribe_local(audio, sample_rate)
        except (ImportError, RuntimeError, OSError) as exc:
            log.warning(
                "Local faster-whisper unavailable (%s); attempting Google Free SpeechRecognition fallback",
                exc,
            )
            try:
                self._provider = "google"
                return self._transcribe_google_free(audio, sample_rate)
            except Exception:
                if self._config.api_key:
                    log.warning("Falling back to Gemini Cloud STT")
                    self._provider = "gemini"
                    return self._transcribe_gemini(audio, sample_rate)
                raise
