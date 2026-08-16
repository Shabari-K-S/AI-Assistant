"""Stage 4: text-to-speech with sentence-chunked streaming.

Zero-cost Neural Edge-TTS + Piper (Local) + ElevenLabs (API).
Audio contract: All engines guarantee returning a 16 kHz float32 mono np.ndarray.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from abc import ABC, abstractmethod

import numpy as np

from config import TTSConfig

log = logging.getLogger("ev.tts")

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def chunk_sentences(text: str) -> list[str]:
    """Split text into sentences, keeping punctuation attached to each chunk."""
    parts = _SENTENCE_END.split(text.strip())
    return [p for p in parts if p]


class TTSEngine(ABC):
    """Synthesize text -> playable audio. One call per sentence chunk."""

    @abstractmethod
    def synthesize(self, text: str) -> np.ndarray:
        """Return audio for `text` (float32 mono ndarray at 16 kHz)."""

    @abstractmethod
    def close(self) -> None: ...


class EdgeTTS(TTSEngine):
    """Zero-cost, high-quality neural TTS via Microsoft Edge endpoints.

    No API key required. Streams neural audio and decodes in-memory to 16 kHz float32 mono.
    """

    def __init__(self, config: TTSConfig) -> None:
        self._config = config
        self._voice = config.edge_voice or "en-US-ChristopherNeural"
        self._rate = config.edge_rate or "+0%"
        self._pitch = config.edge_pitch or "+0Hz"
        self._volume = config.edge_volume or "+0%"
        log.info("EdgeTTS initialized with voice=%s, rate=%s", self._voice, self._rate)

    async def _synthesize_async(self, text: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=self._voice,
            rate=self._rate,
            pitch=self._pitch,
            volume=self._volume,
        )
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
        return b"".join(audio_chunks)

    def _decode_mp3_to_pcm16k(self, mp3_bytes: bytes) -> np.ndarray:
        if not mp3_bytes:
            return np.zeros(0, dtype=np.float32)
        try:
            import av

            container = av.open(io.BytesIO(mp3_bytes))
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
            audio_frames = []
            for frame in container.decode(stream):
                for resampled in resampler.resample(frame):
                    audio_frames.append(resampled.to_ndarray())
            if not audio_frames:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(audio_frames, axis=1).squeeze(0).astype(np.float32)
        except Exception:
            log.exception("failed to decode edge-tts audio stream via PyAV")
            return np.zeros(0, dtype=np.float32)

    def synthesize(self, text: str) -> np.ndarray:
        if not text.strip():
            return np.zeros(0, dtype=np.float32)
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    mp3_bytes = pool.submit(
                        asyncio.run, self._synthesize_async(text)
                    ).result()
            else:
                mp3_bytes = asyncio.run(self._synthesize_async(text))

            return self._decode_mp3_to_pcm16k(mp3_bytes)
        except Exception:
            log.exception("EdgeTTS synthesis failed")
            return np.zeros(0, dtype=np.float32)

    def close(self) -> None:
        pass


class ElevenLabsTTS(TTSEngine):
    """Streaming TTS via the ElevenLabs API (requires ELEVENLABS_API_KEY)."""

    def __init__(self, config: TTSConfig) -> None:
        from elevenlabs.client import ElevenLabs

        if not config.elevenlabs_api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not set (see .env / .env.example)"
            )
        self._config = config
        self._client = ElevenLabs(api_key=config.elevenlabs_api_key)

    def synthesize(self, text: str) -> np.ndarray:
        voice_id = self._config.voice_id or "21m00Tcm4TlvDq8ikWAM"  # default Rachel
        try:
            # Request raw 16kHz 16-bit PCM
            audio_stream = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_turbo_v2_5",
                output_format="pcm_16000",
            )
            raw = b"".join(audio_stream)
            if not raw:
                return np.zeros(0, dtype=np.float32)
            if len(raw) % 2 != 0:
                raw = raw[: -(len(raw) % 2)]
            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception:
            log.exception("ElevenLabs synthesis failed")
            return np.zeros(0, dtype=np.float32)

    def close(self) -> None:
        pass


class PiperTTS(TTSEngine):
    """Local TTS via Piper (set EV_PIPER_VOICE_PATH to an .onnx voice)."""

    def __init__(self, config: TTSConfig) -> None:
        if not config.piper_voice_path:
            raise RuntimeError("EV_PIPER_VOICE_PATH is not set (see .env)")
        from piper import PiperVoice

        self._config = config
        self._voice = PiperVoice.load(config.piper_voice_path)

    def synthesize(self, text: str) -> np.ndarray:
        parts = list(self._voice.synthesize(text))
        audio = np.concatenate([c.audio_float_array for c in parts])
        if audio.size == 0:
            return audio
        sr = parts[0].sample_rate if parts else self._voice.config.sample_rate
        if sr != 16000:
            x = np.linspace(0, len(audio) - 1, int(len(audio) * 16000 / sr))
            audio = np.interp(x, np.arange(len(audio)), audio).astype(np.float32)
        return audio

    def close(self) -> None:
        pass


def build_tts_engine(config: TTSConfig) -> TTSEngine:
    """Select the TTS provider from config (edge | piper | elevenlabs)."""
    provider = config.provider.lower()
    if provider == "edge":
        return EdgeTTS(config)
    if provider == "piper":
        return PiperTTS(config)
    if provider == "elevenlabs":
        return ElevenLabsTTS(config)
    raise ValueError(f"unknown TTS provider: {config.provider!r}")


async def list_edge_voices(language_prefix: str = "en") -> list[dict[str, str]]:
    """Query available edge-tts neural voices."""
    import edge_tts

    voices = await edge_tts.list_voices()
    return [
        {
            "name": v["ShortName"],
            "gender": v["Gender"],
            "locale": v["Locale"],
            "friendly_name": v.get("FriendlyName", ""),
        }
        for v in voices
        if not language_prefix or v["Locale"].startswith(language_prefix)
    ]
