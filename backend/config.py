"""EV — central configuration.

Loads `.env` (via python-dotenv) and exposes typed, frozen dataclasses so every
stage can be swapped or reconfigured without touching code. Keys are read
lazily where they're secrets so a missing key only breaks the stage that needs it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if minimum is not None:
        value = max(value, minimum)
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv_tuple(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class AudioConfig:
    """Stage 1: mic capture + trigger settings."""

    sample_rate: int = 16000
    channels: int = 1
    blocksize: int = 1600  # 100 ms frames — small enough for future streaming STT
    input_device: str | None = None  # None = system default (see `main.py --list-devices`)
    pre_roll_seconds: float = 0.3  # audio kept from before the trigger fired
    max_utterance_seconds: float = 60.0
    ring_seconds: float = 70.0  # timestamped history kept for slicing / wake-word (v2)
    ptt_key: str = "space"
    trigger: str = "wakeword"  # wakeword | ptt
    wake_word_models: tuple[str, ...] = ("alexa",)  # bundled names or .onnx paths
    wake_word_weights: str = ""  # custom trained classifier (.npz) overrides models
    wake_word_threshold: float = 0.35  # higher = fewer false positives
    wake_grace_seconds: float = 1.2  # pause allowed right after the wake word
    wake_end_silence_seconds: float = 1.0  # silence this long = utterance over
    wake_silence_rms: float = 0.02  # RMS below this counts as silence (16 kHz float32)
    wake_min_frames: int = 4  # consecutive >=threshold frames to accept a wake (anti-spike gate)
    wake_empty_cooldown: float = 8.0  # after an empty/silent turn, ignore wake this long (s)
    wake_relisten_max: int = 2  # keep listening after a wake-word-only turn (no new wake needed)
    wake_response_cooldown: float = 4.0  # after a response, ignore wake this long (s) so standby shows
    wake_phrases: tuple[str, ...] = ("alexa",)  # stripped from transcripts
    wake_phrase_required: bool = True  # transcript must contain the wake phrase (false = one wake word, then just talk)


@dataclass(frozen=True)
class STTConfig:
    """Stage 2: STT settings (google free, local faster-whisper, or cloud gemini/groq)."""

    provider: str = "local"  # google (Free SpeechRecognition) | local (faster-whisper) | gemini | groq
    model: str = "small"  # tiny/base/small/medium/large-v3 for local; gemini-2.5-flash / gemini-3.5-flash for gemini
    api_key: str = ""  # optional API key for cloud STT
    device: str = "cpu"  # cpu | cuda (see .env)
    compute_type: str = "int8"  # int8 on CPU, float16 on GPU
    language: str | None = None  # None = auto-detect
    beam_size: int = 5
    vad_filter: bool = True  # Silero VAD — trims silence from the captured clip


@dataclass(frozen=True)
class LLMConfig:
    """Stage 3: Gemma 4 settings (gemini API by default, ollama local fallback)."""

    api_key: str  # GOOGLE_API_KEY for the gemini provider
    provider: str = "gemini"  # gemini | ollama
    model: str = "gemma-4-31b-it"
    max_tokens: int = 2048  # gemma-4-31b reasons first, so leave headroom
    temperature: float = 0.7
    max_turns: int = 20  # rolling conversation window, in user turns
    timeout_s: int = 60  # request timeout
    gemini_thinking: bool = False  # expose reasoning text / request HIGH thinking
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e4b"
    llama_cpp_base_url: str = "http://127.0.0.1:8080"
    llama_cpp_model: str = "qwen2.5-1.5b-instruct"
    llama_cpp_ctx_size: int = 16384
    llama_cpp_threads: int = 4
    system_prompt: str = "You are EV, a dry, witty local voice assistant."


@dataclass(frozen=True)
class TTSConfig:
    """Stage 4: TTS settings (edge | gtts | piper | elevenlabs)."""

    provider: str = "edge"  # edge | gtts (Free Google TTS) | piper | elevenlabs
    edge_voice: str = "en-US-AriaNeural"
    edge_rate: str = "+0%"
    edge_pitch: str = "+0Hz"
    edge_volume: str = "+0%"
    elevenlabs_api_key: str = ""
    voice_id: str = ""  # empty = ElevenLabs default voice
    piper_voice_path: str = ""  # path to a piper .onnx voice model
    piper_rate: float = 1.0
    android_tts_mode: bool = False  # If true, python backend skips local audio playback so client/Android can speak


@dataclass(frozen=True)
class ToolsConfig:
    """Tool-calling safety settings (stage 3)."""

    enabled: bool = True  # set false for pure ultra-fast voice chat with small models
    dynamic: bool = True  # dynamically inject only relevant tools based on user prompt intent
    confirm_shell: str = "ask"  # ask | never | always
    shell_timeout_seconds: int = 30
    shell_allowlist: tuple[str, ...] = (
        "ls", "cat", "head", "tail", "df", "uptime",
        "pwd", "echo", "date", "whoami", "uname",
    )


@dataclass(frozen=True)
class WebUIConfig:
    """Live web HUD bridge (evbridge.py)."""

    enabled: bool = True
    port: int = 2027


@dataclass(frozen=True)
class TerminalConfig:
    """Integrated PTY WebSocket Terminal Bridge (terminal_bridge.py)."""

    enabled: bool = True
    port: int = 2028
    shell: str = ""  # auto-detected if blank


@dataclass(frozen=True)
class RGBConfig:
    """Ambient Smart RGB lighting synchronization."""
    enabled: bool = True
    backend: str = "mock"  # mock | wled | openrgb | webhook
    target: str = "127.0.0.1"  # IP address or webhook URL
    brightness: int = 200  # 0-255


@dataclass(frozen=True)
class Config:
    audio: AudioConfig
    stt: STTConfig
    llm: LLMConfig
    tts: TTSConfig
    tools: ToolsConfig
    webui: WebUIConfig = WebUIConfig()
    terminal: TerminalConfig = TerminalConfig()
    rgb: RGBConfig = RGBConfig()
    log_level: str = "INFO"


def _load_persona(provider: str = "gemini") -> str:
    """System prompt precedence: persona file (persona.md or persona_compact.md for local) -> env var."""
    default_file = "persona_compact.md" if provider in ("llama_cpp", "llamacpp", "ollama") else "persona.md"
    file_env = _env("EV_PERSONA_FILE")
    target_name = file_env if file_env else default_file
    path = Path(target_name)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    # Fallback to standard persona.md if compact missing
    fallback_path = ROOT_DIR / "persona.md"
    if fallback_path.is_file():
        return fallback_path.read_text(encoding="utf-8").strip()
    prompt = _env("EV_PERSONA_PROMPT")
    if prompt:
        return prompt
    return "You are A.T.H.E.N.A., an intelligent and concise voice assistant."


def load_config() -> Config:
    allowlist = _env("EV_SHELL_ALLOWLIST", "").replace(",", " ").split()
    return Config(
        audio=AudioConfig(
            sample_rate=_env_int("EV_SAMPLE_RATE", 16000, minimum=8000),
            channels=_env_int("EV_AUDIO_CHANNELS", 1, minimum=1),
            blocksize=_env_int("EV_BLOCKSIZE", 1600, minimum=160),
            input_device=_env("EV_AUDIO_INPUT_DEVICE") or None,
            pre_roll_seconds=_env_float("EV_PRE_ROLL_SECONDS", 0.3),
            max_utterance_seconds=_env_float("EV_MAX_UTTERANCE_SECONDS", 60.0),
            ptt_key=_env("EV_PTT_KEY", "space"),
            trigger=_env("EV_TRIGGER", "wakeword").lower(),
            wake_word_models=_csv_tuple("EV_WAKE_WORDS", ("athena", "alexa")),
            wake_word_weights=_env("EV_WAKE_WORD_WEIGHTS"),
            wake_word_threshold=_env_float("EV_WAKE_WORD_THRESHOLD", 0.5),
            wake_grace_seconds=_env_float("EV_WAKE_GRACE_SECONDS", 1.2),
            wake_end_silence_seconds=_env_float("EV_WAKE_END_SILENCE_SECONDS", 1.0),
            wake_silence_rms=_env_float("EV_WAKE_SILENCE_RMS", 0.01),
            wake_min_frames=int(_env_float("EV_WAKE_MIN_FRAMES", 4)),
            wake_empty_cooldown=_env_float("EV_WAKE_EMPTY_COOLDOWN", 8.0),
            wake_relisten_max=int(_env_float("EV_WAKE_RELISTEN_MAX", 2)),
            wake_response_cooldown=_env_float("EV_WAKE_RESPONSE_COOLDOWN", 4.0),
            wake_phrases=_csv_tuple("EV_WAKE_PHRASES", ("athena", "hey athena", "alexa")),
            wake_phrase_required=_env_bool("EV_WAKE_PHRASE_REQUIRED", False),
        ),
        stt=STTConfig(
            provider=_env("EV_STT_PROVIDER", "local").lower(),
            model=_env("EV_STT_MODEL", "small"),
            api_key=_env("EV_STT_API_KEY", _env("GOOGLE_API_KEY", _env("GEMINI_API_KEY", _env("GROQ_API_KEY")))),
            device=_env("EV_STT_DEVICE", "cpu"),
            compute_type=_env("EV_STT_COMPUTE_TYPE", "int8"),
            language=_env("EV_STT_LANGUAGE") or None,
            beam_size=_env_int("EV_STT_BEAM_SIZE", 5, minimum=1),
            vad_filter=_env_bool("EV_STT_VAD", True),
        ),
        llm=LLMConfig(
            provider=_env("EV_LLM_PROVIDER", "gemini").lower(),
            api_key=_env("GOOGLE_API_KEY", _env("GEMINI_API_KEY")),
            model=_env("EV_LLM_MODEL", "gemma-4-31b-it"),
            max_tokens=_env_int("EV_LLM_MAX_TOKENS", 1024, minimum=64),
            temperature=_env_float("EV_LLM_TEMPERATURE", 0.7),
            max_turns=_env_int("EV_LLM_MAX_TURNS", 20, minimum=2),
            timeout_s=_env_int("EV_LLM_TIMEOUT", 60, minimum=5),
            gemini_thinking=_env_bool("EV_GEMINI_THINKING", False),
            ollama_base_url=_env("EV_OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=_env("EV_OLLAMA_MODEL", "gemma4:e4b"),
            llama_cpp_base_url=_env("EV_LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080"),
            llama_cpp_model=_env("EV_LLAMA_CPP_MODEL", "qwen2.5-1.5b-instruct"),
            llama_cpp_ctx_size=_env_int("EV_LLAMA_CPP_CTX_SIZE", 16384, minimum=512),
            llama_cpp_threads=_env_int("EV_LLAMA_CPP_THREADS", 4, minimum=1),
            system_prompt=_load_persona(provider=_env("EV_LLM_PROVIDER", "gemini").lower()),
        ),
        tts=TTSConfig(
            provider=_env("EV_TTS_PROVIDER", "edge").lower(),
            edge_voice=_env("EV_EDGE_TTS_VOICE", "en-US-AriaNeural"),
            edge_rate=_env("EV_EDGE_TTS_RATE", "+0%"),
            edge_pitch=_env("EV_EDGE_TTS_PITCH", "+0Hz"),
            edge_volume=_env("EV_EDGE_TTS_VOLUME", "+0%"),
            elevenlabs_api_key=_env("ELEVENLABS_API_KEY"),
            voice_id=_env("EV_TTS_VOICE_ID"),
            piper_voice_path=(
                str(ROOT_DIR / _env("EV_PIPER_VOICE_PATH"))
                if _env("EV_PIPER_VOICE_PATH") and not Path(_env("EV_PIPER_VOICE_PATH")).is_absolute()
                else _env("EV_PIPER_VOICE_PATH")
            ),
            piper_rate=_env_float("EV_PIPER_VOICE_RATE", 1.0),
            android_tts_mode=_env_bool("ANDROID_TTS_MODE", _env_bool("EV_ANDROID_TTS_MODE", False)),
        ),
        tools=ToolsConfig(
            enabled=_env_bool("EV_TOOLS_ENABLED", True),
            dynamic=_env_bool("EV_DYNAMIC_TOOLS", True),
            confirm_shell=_env("EV_CONFIRM_SHELL", "ask"),
            shell_timeout_seconds=_env_int("EV_SHELL_TIMEOUT_SECONDS", 30, minimum=1),
            shell_allowlist=tuple(allowlist) if allowlist else ToolsConfig.shell_allowlist,
        ),
        webui=WebUIConfig(
            enabled=_env_bool("EV_WEBUI_ENABLED", True),
            port=_env_int("EV_WEBUI_PORT", 2027, minimum=1024),
        ),
        terminal=TerminalConfig(
            enabled=_env_bool("EV_TERMINAL_ENABLED", True),
            port=_env_int("EV_TERMINAL_PORT", 2028, minimum=1024),
            shell=_env("EV_TERMINAL_SHELL", ""),
        ),
        rgb=RGBConfig(
            enabled=_env_bool("EV_RGB_ENABLED", True),
            backend=_env("EV_RGB_BACKEND", "mock").lower(),
            target=_env("EV_RGB_TARGET", "127.0.0.1"),
            brightness=_env_int("EV_RGB_BRIGHTNESS", 200),
        ),
        log_level=_env("EV_LOG_LEVEL", "INFO").upper(),
    )
