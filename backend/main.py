"""EV — local, voice-first AI assistant.

Milestone 2 (this build): stages 1-3 wired — always-on mic capture with a wake
word (openWakeWord, 'alexa' by default), faster-whisper transcription,
then Gemma 4 (with tool use) streaming its reply to the console. Stage 4 (TTS)
is next.

Usage
-----
    python main.py                        # wake word -> transcribe -> Gemma -> print
    python main.py assistant              # same as above (explicit)
    python main.py transcribe             # stages 1-2 only: just print what it hears
    python main.py --text "say hello"     # skip the mic, feed text straight to Gemma
    python main.py --once                 # single utterance, then exit
    python main.py --list-devices         # show audio devices, then exit

Controls
--------
    Say "Hey Jarvis" then your request; EV listens until you stop speaking.
    (EV_TRIGGER=ptt restores hold-SPACE-to-talk.)
    Ctrl+C to quit.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time

import wsl_bootstrap  # must precede sounddevice import (audio_input)

wsl_bootstrap.bootstrap()

from audio_input import (  # noqa: E402
    MicCapture,
    PushToTalk,
    WakeWordTrigger,
    default_key_hook,
    list_devices,
)
from config import load_config  # noqa: E402
from stt import STTEngine  # noqa: E402
from tts import TTSEngine, build_tts_engine  # noqa: E402

import evbridge  # noqa: E402  (web HUD — optional, never blocks the loop)

log = logging.getLogger("ev.main")

_PROMPT_WAKE = 'Say "sara" to talk (Ctrl+C to quit)...'
_PROMPT_PTT = 'Hold Space or tap Hold-To-Talk in Web HUD to speak (Ctrl+C to quit)...'
_WAKE_REQUIRED_HINT = "you have to say my name first — try \"sara, ...\""
_SILENCE_RETRY_HINT_WAKE = "didn't catch that — say \"sara, ...\" and try again"
_SILENCE_RETRY_HINT_PTT = "didn't catch that — try speaking into your microphone or hold-to-talk button again"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


# --------------------------------------------------------------------------- #
# Shared audio plumbing
# --------------------------------------------------------------------------- #
def _start_audio(cfg, on_score=None):
    """Start capture + trigger (wake word, push-to-talk, or web mode). Returns (mic, trigger)."""
    if cfg.audio.trigger in ("web", "none", "ui"):
        log.info(
            "Audio trigger is %r: running in pure Web HUD mode (no local microphone bound).",
            cfg.audio.trigger,
        )
        return None, None
    try:
        if cfg.audio.trigger == "ptt":
            mic = MicCapture(cfg.audio)
            hook = default_key_hook(cfg.audio.ptt_key)
            trigger = PushToTalk(hook, key=cfg.audio.ptt_key)
        else:
            trigger = WakeWordTrigger(cfg.audio, on_score=on_score)
            mic = MicCapture(cfg.audio, sink=trigger.on_audio)
        mic.start()
    except (OSError, RuntimeError) as exc:
        print(f"audio error: {exc}", file=sys.stderr)
        print("run `python main.py --list-devices` to inspect your audio setup", file=sys.stderr)
        return None, None
    return mic, trigger


def _capture_utterance(mic, trigger, cfg, bus=None, timeout: float | None = None) -> tuple[bool, bytes | None]:
    """Wait for activation (up to timeout). Returns (activated, audio_buffer).
    If not activated within timeout, returns (False, None)."""
    if not trigger.wait_for_activation(timeout=timeout):
        return False, None
    if bus is not None:
        bus.set(phase="listening")
        bus.log("INFO", ">>> listening...")
    act_ts = getattr(trigger, "activation_time", time.monotonic())
    start_monotonic = act_ts - cfg.audio.pre_roll_seconds
    print(">>> listening...", flush=True)

    trigger.wait_for_deactivation()
    audio = mic.read_from(start_monotonic)

    if audio.size < cfg.audio.sample_rate * 0.2:
        print(f"(too short: {audio.size / cfg.audio.sample_rate:.1f}s)", flush=True)
        print(_SILENCE_RETRY_HINT, flush=True)
        if bus is not None:
            bus.set(phase="standby")
            bus.log("INFO", "(too short — retry)")
        return True, None
    return True, audio


def _wake_regex(phrase: str) -> re.Pattern:
    """Match the wake phrase as a word, tolerating speech variations (e.g. sara, sarah, s.a.r.a., saara, sa ra, case or a, que sera, etc.)."""
    base = phrase.lower().strip()
    if base in ("sara", "sarah"):
        # Match sara, sarah, s.a.r.a., saara, sahra, sera, serah, zara, zarah, sa ra, saa raa, case or a, que sera, k sara
        pattern = r"\b(s\.?a\.?r\.?a\.?|sarah?|saara|sahra|sera|serah|zara|zarah|sa\s+ra|saa\s+raa|s\s+a\s+r\s+a|case\s+or\s+a|k\s+sara|que\s+sera|say\s+ra|cera)\b"
        return re.compile(pattern, re.IGNORECASE)
    return re.compile(rf"\b{re.escape(base)}(?:h)?\b", re.IGNORECASE)


def _strip_wake_phrase(text: str, phrases: tuple[str, ...]) -> str:
    """Remove the wake phrase from the transcript so the LLM only sees the actual request."""
    text = text.strip()
    for phrase in phrases:
        text = _wake_regex(phrase).sub(" ", text)
    text = re.sub(r"^\s*[,.:;]\s*", "", text)
    text = re.sub(r"\b(?:hey|ok|okay|hi|hello|uh|um)\s*[,.:;]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip().strip(" ,;:.")


def _has_wake_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    """True when the transcript contains the wake phrase or its phonetic variants."""
    lowered = text.lower()
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", lowered)
    for p in phrases:
        if _wake_regex(p).search(lowered) or _wake_regex(p).search(cleaned):
            return True
    return False


def _transcribe(mic, stt, cfg, audio, bus=None) -> str | None:
    """Transcribe audio; prints hints on failure/silence. None = retry turn."""
    silence_hint = (
        _SILENCE_RETRY_HINT_WAKE if cfg.audio.trigger == "wakeword" else _SILENCE_RETRY_HINT_PTT
    )
    try:
        result = stt.transcribe(audio, mic.sample_rate)
    except Exception as exc:  # noqa: BLE001 - keep the loop alive on STT failure
        log.exception("transcription failed")
        print(f"transcription error: {exc}", flush=True)
        if bus is not None:
            bus.event("error", msg=f"transcription error: {exc}")
        return None
    if result.is_empty:
        print(silence_hint, flush=True)
        if bus is not None:
            bus.set(phase="standby")
            bus.log("WARN", silence_hint)
        return None
    if result.confidence < -1.1:  # whisper hallucination on noise, not real speech
        log.info("low-confidence transcript (%.2f) — treating as silence", result.confidence)
        print(silence_hint, flush=True)
        if bus is not None:
            bus.set(phase="standby")
            bus.log("WARN", f"low-confidence transcript ({result.confidence:.2f}) — treating as silence")
        return None
    text = result.text.strip()
    print(f"[you] {text}", flush=True)
    if bus is not None:
        bus.set(transcript=text)
        bus.event("transcript", text=text, confidence=result.confidence)
    return text


def clean_for_speech(text: str) -> str:
    """Strip markdown/LaTeX/thought tags so the reply reads (and speaks) like speech."""
    if not text:
        return text
    t = re.sub(r"<think>.*?</think>", " ", text, flags=re.S | re.IGNORECASE)
    t = re.sub(r"<thought>.*?</thought>", " ", text, flags=re.S | re.IGNORECASE)
    t = re.sub(r"```.*?```", " ", t, flags=re.S)        # fenced code
    t = re.sub(r"`[^`]*`", " ", t)                          # inline code
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)        # links/images
    t = re.sub(r"\$\$.*?\$\$", " ", t, flags=re.S)          # $$ math $$
    t = re.sub(r"\\\(.*?\\\)|\\\[.*?\\\]", " ", t, flags=re.S)
    t = re.sub(r"\$[^$\n]*\$", " ", t)                      # $inline math$
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)            # headers
    t = re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", t, flags=re.M)  # list markers
    t = re.sub(r"^\s*\|.*\|\s*$", " ", t, flags=re.M)       # table rows
    t = re.sub(r"^\s*\|.*$", " ", t, flags=re.M)            # stray table pipes
    t = re.sub(r"[-*_]{2,}|~~", " ", t)                     # emphasis, rules
    t = re.sub(r"\s+", " ", t)                              # collapse whitespace
    return t.strip()


def _is_self_echo(user_text: str, last_reply: str) -> bool:
    """Detect if the transcribed speech is an acoustic echo/bleed from the assistant's own speaker output."""
    if not user_text or not last_reply:
        return False
    u = re.sub(r"[^a-z0-9\s]", "", user_text.lower()).strip()
    r = re.sub(r"[^a-z0-9\s]", "", last_reply.lower()).strip()
    if not u or not r:
        return False

    # 1. Exact substring or reverse containment
    if len(u) > 15 and (u in r or r in u):
        return True

    # 2. Token overlap ratio (word intersection)
    u_words = set(u.split())
    r_words = set(r.split())
    if len(u_words) >= 3:
        overlap = len(u_words & r_words) / len(u_words)
        if overlap >= 0.60:
            return True

    # 3. Fuzzy sequence similarity
    import difflib

    ratio = difflib.SequenceMatcher(None, u, r).ratio()
    return ratio >= 0.55


# --------------------------------------------------------------------------- #
# Stage 3: Claude + tools
# --------------------------------------------------------------------------- #
def _speak(
    tts: TTSEngine | None,
    text: str,
    bus=None,
    muted: bool = False,
    mic=None,
    trigger=None,
) -> None:
    """Synthesize and play a reply through the speaker with acoustic echo flushing."""
    if bus is not None:
        bus.set(phase="speaking")
    if trigger is not None:
        trigger.set_enabled(False)
    try:
        if tts is None:
            return
        import sounddevice as sd

        audio = tts.synthesize(text)
        if audio is None or len(audio) == 0:
            return
        if bus is not None:
            bus.log("INFO", "speaking…" if not muted else "speaking… (muted)")
        if not muted:
            sd.play(audio, 16000)
            sd.wait()
            # Speaker reverb decay pause (350ms) to let room acoustics settle
            time.sleep(0.35)

        # Discard any audio frames buffered during speaker playback
        if mic is not None:
            mic.flush(time.monotonic())
        if trigger is not None:
            if hasattr(trigger, "reset_audio"):
                trigger.reset_audio()
            trigger.quiet_until(time.monotonic() + 0.8)
    except Exception:  # noqa: BLE001 - speaking must never break the loop
        log.exception("tts failed")
    finally:
        if trigger is not None:
            trigger.set_enabled(True)
        if bus is not None:
            bus.set(phase="standby")


_AFFIRMATIVE_WORDS = {
    "yes", "yeah", "yup", "sure", "proceed", "go ahead", "okay", "ok",
    "run it", "do it", "confirm", "confirmed", "yep", "affirmative", "correct", "y", "please do", "execute",
}

_NEGATIVE_WORDS = {
    "no", "nah", "nope", "stop", "cancel", "don't", "dont", "abort",
    "never mind", "decline", "n", "refuse", "negative", "do not",
}


def _confirm_terminal(prompt: str) -> bool:
    """y/N confirmation prompt used by the tool layer for side-effect tools."""
    try:
        reply = input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return reply in {"y", "yes"}


def _make_voice_or_terminal_confirm(context_holder: dict) -> Callable[[str], bool]:
    """Creates an interactive voice confirmation handler that speaks modifying action requests
    out loud and listens for the user's voice reply (with web HUD & terminal fallback)."""

    def confirm_action(prompt: str) -> bool:
        bus = context_holder.get("bus")
        tts = context_holder.get("tts")
        mic = context_holder.get("mic")
        trigger = context_holder.get("trigger")
        stt = context_holder.get("stt")
        cfg = context_holder.get("cfg")
        muted = context_holder.get("muted", {"on": False})

        # Formulate human-friendly spoken sentence
        if "command:" in prompt:
            m = re.search(r"command:\s*['\"]?(.*?)['\"]?$", prompt)
            cmd_snippet = m.group(1) if m else prompt
            spoken_text = f"I need your confirmation to execute the modifying command: {cmd_snippet}. Should I proceed?"
        else:
            spoken_text = f"I need your confirmation to {prompt}. Should I proceed?"

        log.info("Requesting user confirmation: %s", prompt)
        print(f"\n⚠️  [CONFIRMATION REQUIRED]: {prompt}", flush=True)
        print("   Listening for voice ('yes'/'proceed'/'no') or input (8s timeout)...", flush=True)

        if bus is not None:
            bus.set(phase="speaking", reply=spoken_text)
            bus.log("WARN", f"Confirmation required: {prompt}")
            bus.event("confirmation_request", prompt=prompt, spoken=spoken_text)

        # 1. Speak the confirmation request out loud
        _speak(tts, spoken_text, bus=bus, muted=muted.get("on", False), mic=mic, trigger=trigger)

        if bus is not None:
            bus.set(phase="listening", transcript="[Listening for Voice Confirmation...]")

        confirmed = None

        # 2. Listen for voice response if microphone & STT are available
        if mic is not None and trigger is not None and stt is not None and cfg is not None:
            mic.flush(time.monotonic())
            if hasattr(trigger, "reset_audio"):
                trigger.reset_audio()

            activated, audio = _capture_utterance(mic, trigger, cfg, bus=bus, timeout=7.0)
            if activated and audio is not None:
                transcription = _transcribe(mic, stt, cfg, audio, bus=bus)
                if transcription:
                    user_reply = transcription.strip().lower()
                    print(f"[voice confirmation response]: '{user_reply}'", flush=True)
                    if bus is not None:
                        bus.log("INFO", f"Voice confirmation answer: '{user_reply}'")

                    words = set(re.findall(r"\b\w+\b", user_reply))
                    if words & _AFFIRMATIVE_WORDS or any(w in user_reply for w in _AFFIRMATIVE_WORDS):
                        confirmed = True
                    elif words & _NEGATIVE_WORDS or any(w in user_reply for w in _NEGATIVE_WORDS):
                        confirmed = False

        # 3. Check for web HUD prompt if voice not definitive
        if confirmed is None and bus is not None:
            injected = bus.get_injected_prompt(timeout=0.5)
            if injected:
                inj_lower = injected.strip().lower()
                if any(w in inj_lower for w in _AFFIRMATIVE_WORDS):
                    confirmed = True
                elif any(w in inj_lower for w in _NEGATIVE_WORDS):
                    confirmed = False

        # 4. Terminal fallback if in interactive terminal
        if confirmed is None and sys.stdin.isatty():
            try:
                import select
                print(f"{prompt} [y/N]: ", end="", flush=True)
                r, _, _ = select.select([sys.stdin], [], [], 2.0)
                if r:
                    reply = sys.stdin.readline().strip().lower()
                    if reply in ("y", "yes", "proceed"):
                        confirmed = True
                    else:
                        confirmed = False
            except Exception:
                pass

        # Conclude and feedback
        if confirmed is True:
            log.info("Action confirmed by user.")
            if bus is not None:
                bus.log("INFO", "Action confirmed by user.")
                bus.set(phase="processing")
            _speak(tts, "Confirmed. Proceeding with execution.", bus=bus, muted=muted.get("on", False), mic=mic, trigger=trigger)
            return True
        else:
            log.warning("Action declined or timed out.")
            if bus is not None:
                bus.log("WARN", "Action declined or confirmation timed out.")
                bus.set(phase="standby")
            _speak(tts, "Action cancelled.", bus=bus, muted=muted.get("on", False), mic=mic, trigger=trigger)
            return False

    return confirm_action


def _llm_error_message(exc) -> str:
    """Map LLM provider exceptions to a one-line, operator-facing message."""
    try:
        from google.genai import errors as genai_errors
    except ImportError:
        genai_errors = None

    if genai_errors is not None and isinstance(exc, genai_errors.ClientError):
        if exc.code == 429:
            return "Gemma 4 free tier is rate-limited right now — wait a moment and try again."
        return f"Gemma 4 returned an error (HTTP {exc.code})."
    if isinstance(exc, RuntimeError) and "ollama" in str(exc).lower():
        return f"{exc} (is `ollama serve` running and the model pulled?)"
    import httpx

    if isinstance(exc, httpx.TimeoutException):
        return "the request timed out — network issues? try again."
    if isinstance(exc, httpx.ConnectError):
        return "couldn't reach the LLM endpoint — check your network."
    return f"unexpected LLM error: {type(exc).__name__}: {exc}"


def _build_agent(cfg, confirm_fn: Callable[[str], bool] | None = None):
    """Assemble Conversation + ToolRegistry + MCPManager + LLM engine. Returns (conv, engine,
    registry, mcp_manager) or exits with code 2 when the setup is incomplete."""
    from llm import Conversation, build_llm
    from mcp_client import MCPManager
    from tools import ToolRegistry

    registry = ToolRegistry(cfg.tools, confirm=confirm_fn or _confirm_terminal)
    mcp_manager = MCPManager()
    mcp_manager.set_registry(registry)
    try:
        mcp_manager.start_servers()
        mcp_count = mcp_manager.register_into_tool_registry(registry)
        if mcp_count > 0:
            log.info("MCP subsystem online: %d dynamic tools registered", mcp_count)
    except Exception:
        log.exception("Failed initializing MCP servers")

    conversation = Conversation(max_turns=cfg.llm.max_turns)
    try:
        engine = build_llm(cfg.llm, tool_executor=registry.execute)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        print(
            "or set EV_LLM_PROVIDER=ollama to use a local Ollama server "
            "(see .env.example).",
            file=sys.stderr,
        )
        if mcp_manager:
            mcp_manager.close()
        return None, None, None, None
    return conversation, engine, registry, mcp_manager


def _run_assistant(cfg, once: bool, text: str | None) -> int:
    bus = evbridge.get_bus()
    muted = {"on": False}

    context_holder = {"cfg": cfg, "bus": bus, "muted": muted}
    confirm_handler = _make_voice_or_terminal_confirm(context_holder)

    conversation, engine, registry, mcp_manager = _build_agent(cfg, confirm_fn=confirm_handler)
    if engine is None:
        return 2

    if mcp_manager:
        bus.set_mcp_manager(mcp_manager)

    def _set_muted(value: bool) -> None:
        muted["on"] = bool(value)

    bus.on_control("threshold", lambda v: trigger.set_threshold(v) if trigger else None)
    bus.on_control("muted", _set_muted)
    bus.on_control("ptt_press", lambda _: trigger.press() if trigger else None)
    bus.on_control("ptt_release", lambda _: trigger.release() if trigger else None)
    if cfg.webui.enabled:
        evbridge.start(cfg.webui.port)
    bus.set(
        online=True,
        phase="standby",
        threshold=cfg.audio.wake_word_threshold,
        wake_word=",".join(cfg.audio.wake_phrases) or cfg.audio.wake_word_models[0],
        stt_model=cfg.stt.model,
        llm_model=cfg.llm.model if cfg.llm.provider == "gemini" else cfg.llm.ollama_model,
        tts=cfg.tts.provider,
        since=time.time(),
        muted=False,
    )
    bus.log("INFO", "core online — awaiting wake word")

    mic = trigger = stt = tts = None
    if text is None:
        if cfg.audio.trigger in ("web", "none", "ui"):
            print(
                "Web HUD Mode Active — speak or type via http://localhost:2026 (Ctrl+C to quit)...",
                flush=True,
            )
        else:
            mic, trigger = _start_audio(
                cfg,
                on_score=lambda _ts, score, noise: bus.set(wake_score=score, noise_floor=noise),
            )
            if mic is None:
                return 2
            stt = STTEngine(cfg.stt)
            prompt_str = _PROMPT_PTT if cfg.audio.trigger == "ptt" else _PROMPT_WAKE
            print(prompt_str, flush=True)
    try:
        tts = build_tts_engine(cfg.tts)
        log.info("tts provider: %s", cfg.tts.provider)
    except Exception as exc:  # noqa: BLE001 - text output still works without TTS
        log.warning("tts unavailable (text only): %s", exc)

    # Attach live audio objects into confirmation context
    context_holder.update({
        "mic": mic,
        "trigger": trigger,
        "stt": stt,
        "tts": tts,
    })

    try:
        relisten_count = 0
        last_reply = ""
        while True:
            if text is not None:
                user_text = text
            else:
                # Check for injected text prompt from the web HUD terminal
                injected = bus.get_injected_prompt()
                if injected:
                    user_text = injected
                    print(f"[uplink] {user_text}", flush=True)
                    bus.set(transcript=user_text)
                    bus.event("transcript", text=user_text, confidence=1.0)
                elif mic is None:
                    # In web mode without local microphone binding, wait for web prompts
                    time.sleep(0.05)
                    continue
                else:
                    activated, audio = _capture_utterance(mic, trigger, cfg, bus=bus, timeout=0.2)
                    if not activated:
                        # Timeout on activation — keep/reset to standby
                        if bus is not None and bus.get().get("phase") != "standby":
                            bus.set(phase="standby")
                        continue
                    if audio is None:
                        if bus is not None:
                            bus.set(phase="standby")
                        if trigger is not None:
                            trigger.quiet_until(time.monotonic() + cfg.audio.wake_empty_cooldown)
                        if once:
                            return 0
                        continue
                    if bus is not None:
                        bus.set(phase="processing")
                    user_text = _transcribe(mic, stt, cfg, audio, bus=bus)
                    if user_text is None:
                        if bus is not None:
                            bus.set(phase="standby")
                        if trigger is not None:
                            trigger.quiet_until(time.monotonic() + cfg.audio.wake_empty_cooldown)
                        if once:
                            return 0
                        continue
                    is_wakeword_mode = cfg.audio.trigger == "wakeword"
                    if is_wakeword_mode and cfg.audio.wake_phrase_required and not _has_wake_phrase(user_text, cfg.audio.wake_phrases):
                        print(_WAKE_REQUIRED_HINT, flush=True)
                        if bus is not None:
                            bus.set(phase="standby")
                            bus.log("WARN", _WAKE_REQUIRED_HINT)
                        if trigger is not None:
                            trigger.quiet_until(time.monotonic() + cfg.audio.wake_empty_cooldown)
                        if once:
                            return 0
                        continue
                    user_text = _strip_wake_phrase(user_text, cfg.audio.wake_phrases)
                    if not user_text:
                        if trigger is not None and is_wakeword_mode and relisten_count < cfg.audio.wake_relisten_max:
                            relisten_count += 1
                            print("(wake word only — listening for the request…)", flush=True)
                            if bus is not None:
                                bus.set(phase="listening")
                                bus.log("INFO", "wake word only — listening for the request…")
                            trigger.continue_listening()
                            continue
                        if trigger is not None:
                            trigger.quiet_until(time.monotonic() + cfg.audio.wake_empty_cooldown)
                        silence_hint = (
                            _SILENCE_RETRY_HINT_WAKE if is_wakeword_mode else _SILENCE_RETRY_HINT_PTT
                        )
                        print(silence_hint, flush=True)
                        if bus is not None:
                            bus.set(phase="standby")
                            bus.log("WARN", silence_hint)
                        if once:
                            return 0
                        continue

            # Check for acoustic speaker bleed / self-echo before invoking LLM
            if last_reply and _is_self_echo(user_text, last_reply):
                log.warning("Discarded acoustic self-echo from speaker: %r", user_text)
                if bus is not None:
                    bus.set(phase="standby")
                    bus.log("WARN", "Acoustic speaker echo filtered out")
                if trigger is not None:
                    trigger.quiet_until(time.monotonic() + 1.2)
                continue

            # ignore wake words while processing (LLM + speech are slow)
            relisten_count = 0
            if trigger is not None:
                trigger.set_enabled(False)
            conversation.add_user(user_text)
            if bus is not None:
                bus.set(phase="processing")
                bus.log("INFO", "processing…")
            reply_parts: list[str] = []
            try:
                tools = registry.schemas(
                    format="gemini" if cfg.llm.provider == "gemini" else "openai"
                )
                for token in engine.stream_response(
                    conversation, tools, cfg.llm.system_prompt
                ):
                    if token:
                        reply_parts.append(token)
            except Exception as exc:  # noqa: BLE001 - degrade, never crash the loop
                print("\n[error] " + _llm_error_message(exc), flush=True)
                log.exception("llm stream failed")
                conversation.pop_last_user()  # roll back the failed turn
                if bus is not None:
                    bus.event("error", msg=_llm_error_message(exc))
                    bus.set(phase="standby")
                if trigger is not None:
                    trigger.set_enabled(True)
                if once:
                    return 1
            reply = clean_for_speech("".join(reply_parts))
            last_reply = reply
            print(f"[EV] {reply}", flush=True)
            if bus is not None:
                bus.set(reply=reply)
                bus.event("reply", text=reply)
            _speak(tts, reply, bus=bus, muted=muted["on"], mic=mic, trigger=trigger)
            if once or text is not None:
                return 0
    except KeyboardInterrupt:
        print("\nbye", flush=True)
        return 0
    finally:
        if mcp_manager is not None:
            mcp_manager.close()
        if mic is not None:
            mic.stop()
        if trigger is not None:
            trigger.close()
        if tts is not None:
            tts.close()


def _run_transcribe_loop(cfg, once: bool) -> int:
    mic, trigger = _start_audio(cfg)
    if mic is None:
        return 2
    stt = STTEngine(cfg.stt)
    prompt_str = _PROMPT_PTT if cfg.audio.trigger == "ptt" else _PROMPT_WAKE
    print(prompt_str, flush=True)
    try:
        while True:
            activated, audio = _capture_utterance(mic, trigger, cfg)
            if not activated or audio is None:
                if once and activated:
                    return 0
                continue
            user_text = _transcribe(mic, stt, cfg, audio)
            if user_text is None:
                if once:
                    return 0
                continue
            if once:
                return 0
    except KeyboardInterrupt:
        print("\nbye", flush=True)
        return 0
    finally:
        mic.stop()
        trigger.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ev", description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        default="assistant",
        choices=["assistant", "transcribe"],
        help="assistant = stages 1-3 (default); transcribe = stages 1-2 only",
    )
    parser.add_argument("--once", action="store_true", help="single utterance, then exit")
    parser.add_argument(
        "--text", default=None,
        help="skip the mic; send this text straight to the LLM (testing without audio)",
    )
    parser.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    args = parser.parse_args(argv)

    if args.list_devices:
        list_devices()
        return 0

    cfg = load_config()
    _setup_logging(cfg.log_level)

    if args.mode == "assistant":
        return _run_assistant(cfg, once=args.once, text=args.text)
    return _run_transcribe_loop(cfg, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
