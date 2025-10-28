"""
Jarvis main entry: wake-word loop, TTS, SR backends, command queue, reminders.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from typing import Optional
import subprocess

import pyttsx3
import speech_recognition as sr

from config import (
    ASSISTANT_NAME,
    WAKE_WORDS,
    LOG_PATH,
    PREFERRED_MIC_SUBSTRING,
    SD_INPUT_DEVICE,
    IDLE_PROMPT_SECONDS,
    TTS_RATE,
    TTS_VOLUME,
    TTS_VOICE_NAME,
    SR_DYNAMIC_ENERGY,
    SR_ENERGY_THRESHOLD,
    SR_PAUSE_THRESHOLD,
    SR_NON_SPEAKING_DURATION,
    SR_ADJUST_DURATION,
    SR_PHRASE_TIME_LIMIT,
    SR_MAX_TIMEOUTS_BEFORE_TEXT,
)
try:
    from gui import JarvisGUI
except Exception:
    JarvisGUI = None  # type: ignore
from database import init_db, get_due_reminders, mark_reminder_done
from jarvis_brain import SessionMemory, handle_command, greeting
import runtime_control as rt

# Optional fallback for audio capture when PyAudio is unavailable
try:
    import sounddevice as sd
    import numpy as np
except Exception:
    sd = None  # type: ignore
    np = None  # type: ignore

try:
    import winsound

    def beep(freq: int = 1000, dur_ms: int = 120) -> None:
        try:
            winsound.Beep(freq, dur_ms)
        except Exception:
            pass

except Exception:

    def beep(freq: int = 1000, dur_ms: int = 120) -> None:  # type: ignore
        pass

# COM initialization for Windows TTS (pyttsx3 SAPI5)
try:
    import pythoncom  # type: ignore
except Exception:
    pythoncom = None  # type: ignore

# Optional direct SAPI fallback via comtypes if pyttsx3 fails
try:
    from comtypes.client import CreateObject  # type: ignore
except Exception:
    CreateObject = None  # type: ignore


def setup_logging() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    # File logging only; console kept clean for chat-style output
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    root.addHandler(fh)


def create_tts_engine() -> pyttsx3.Engine:
    try:
        engine = pyttsx3.init(driverName="sapi5")
    except Exception:
        engine = pyttsx3.init()
    try:
        engine.setProperty("rate", int(TTS_RATE))
    except Exception:
        engine.setProperty("rate", 185)
    try:
        engine.setProperty("volume", float(TTS_VOLUME))
    except Exception:
        engine.setProperty("volume", 1.0)
    try:
        voices = engine.getProperty("voices")
        if voices:
            sel = None
            if TTS_VOICE_NAME:
                name_l = TTS_VOICE_NAME.lower()
                sel = next((v for v in voices if name_l in (v.name or "").lower()), None)
            if not sel:
                sel = next((v for v in voices if "english" in (v.name or "").lower()), None)
            engine.setProperty("voice", sel.id if sel else voices[0].id)
    except Exception:
        pass
    return engine


class TTSEngineThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.q: queue.Queue[str] = queue.Queue()
        self.engine: Optional[pyttsx3.Engine] = None
        self.fail_count: int = 0
        self._lock = threading.Lock()

    def _fallback_sapi_speak(self, text: str) -> bool:
        """Try speaking using direct SAPI if available as a last resort."""
        if CreateObject is None:
            return False
        try:
            # Ensure COM initialized in this thread
            if pythoncom is not None:
                try:
                    pythoncom.CoInitialize()
                except Exception:
                    pass
            # Create a fresh SAPI voice for robustness
            v = CreateObject("SAPI.SpVoice")
            v.Speak(text)
            return True
        except Exception:
            return False

    def _powershell_speak(self, text: str) -> bool:
        """Last-chance TTS using PowerShell System.Speech API (no extra deps)."""
        try:
            # Sanitize for PowerShell single-quoted string
            msg = text.replace("'", "''")
            ps_cmd = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Rate = 0; $s.Volume = 100; "
                f"$s.Speak('{msg}')"
            )
            # Try multiple invocations for reliability
            candidates = [
                "powershell",
                "powershell.exe",
                os.path.join(os.environ.get("SystemRoot", r"C:\\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
            ]
            for exe in candidates:
                try:
                    subprocess.run(
                        [exe, "-NoLogo", "-NonInteractive", "-NoProfile", "-Command", ps_cmd],
                        check=False,
                        creationflags=0x08000000 if os.name == 'nt' else 0,  # CREATE_NO_WINDOW
                    )
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def run(self) -> None:
        if pythoncom is not None:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass
        try:
            self.engine = create_tts_engine()
        except Exception:
            self.engine = None
        while True:
            text = self.q.get()
            if text == "__EXIT__":
                break
            # If forced robust TTS is enabled, use PowerShell path first
            try:
                if getattr(rt, "FORCE_POWERSHELL_TTS", False):
                    if self._powershell_speak(text):
                        self.fail_count = 0
                        continue
            except Exception:
                pass
            if self.engine is None:
                # Try to reinitialize if engine missing
                try:
                    self.engine = create_tts_engine()
                except Exception:
                    self.engine = None
                    # Try direct SAPI fallback if pyttsx3 engine can't be created
                    if self._fallback_sapi_speak(text):
                        self.fail_count = 0
                        continue
                    # Try PowerShell System.Speech as final fallback
                    if self._powershell_speak(text):
                        self.fail_count = 0
                        continue
                    continue
            try:
                # Ensure engine is in a clean state
                try:
                    self.engine.stop()
                except Exception:
                    pass
                self.engine.say(text)
                self.engine.runAndWait()
                self.fail_count = 0
            except Exception:
                # Attempt one reinit on failure and keep app responsive
                self.fail_count += 1
                if self.fail_count <= 2:
                    try:
                        self.engine = create_tts_engine()
                    except Exception:
                        self.engine = None
                else:
                    # Last resort: direct SAPI
                    if self._fallback_sapi_speak(text) or self._powershell_speak(text):
                        self.fail_count = 0
                    time.sleep(0.1)

    def enqueue(self, text: str) -> None:
        try:
            self.q.put_nowait(text)
        except Exception:
            pass


class Speaker:
    def __init__(self, tts_thread: TTSEngineThread, gui: Optional[object] = None) -> None:
        self.tts = tts_thread
        self.gui = gui

    def speak(self, text: str) -> None:
        logging.info(f"{ASSISTANT_NAME}: {text}")
        print(f"{ASSISTANT_NAME}: {text}")
        if self.gui is not None:
            try:
                self.gui.add_history(f"{ASSISTANT_NAME}: {text}")
            except Exception:
                pass
        # Send to the single TTS engine thread
        self.tts.enqueue(text)


def listen_once(recognizer: sr.Recognizer, timeout: float = 5.0, phrase_time_limit: float | None = None) -> Optional[str]:
    try:
        with sr.Microphone(device_index=rt.SR_MIC_DEVICE_INDEX) as source:
            try:
                dur = float(rt.SR_ADJUST_DURATION_OVERRIDE) if rt.SR_ADJUST_DURATION_OVERRIDE is not None else float(SR_ADJUST_DURATION)
                recognizer.adjust_for_ambient_noise(source, duration=dur)
            except Exception:
                pass
            pt = float(rt.SR_PHRASE_TIME_LIMIT_OVERRIDE) if (rt.SR_PHRASE_TIME_LIMIT_OVERRIDE is not None) else float(SR_PHRASE_TIME_LIMIT if phrase_time_limit is None else phrase_time_limit)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=pt)
    except Exception:
        raise
    try:
        text = recognizer.recognize_google(audio).strip()
        if text:
            print(f"You said: {text}")
            if UI_ADD_HISTORY:
                try:
                    UI_ADD_HISTORY(f"You said: {text}")
                except Exception:
                    pass
            return text.lower()
        return None
    except sr.UnknownValueError:
        return None
    except Exception:
        return None


def listen_once_sounddevice(
    recognizer: sr.Recognizer,
    *,
    samplerate: int = 16000,
    seconds: float = 3.0,
) -> Optional[str]:
    if sd is None or np is None:
        raise OSError("sounddevice not available")
    try:
        # Prefer runtime override, then config, then leave default
        idx = rt.SD_INPUT_DEVICE_INDEX if rt.SD_INPUT_DEVICE_INDEX is not None else SD_INPUT_DEVICE
        if idx is not None:
            try:
                out = sd.default.device[1] if isinstance(sd.default.device, (list, tuple)) else None
                sd.default.device = (idx, out)
            except Exception:
                sd.default.device = (idx, idx)
        frames = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1, dtype="int16")
        sd.wait()
        raw = frames.tobytes()
    except Exception:
        raise OSError("recording failed")
    audio = sr.AudioData(raw, samplerate, sample_width=2)
    try:
        text = recognizer.recognize_google(audio).strip()
        if text:
            print(f"You said: {text}")
            if UI_ADD_HISTORY:
                try:
                    UI_ADD_HISTORY(f"You said: {text}")
                except Exception:
                    pass
            return text.lower()
        return None
    except sr.UnknownValueError:
        return None
    except Exception:
        return None


def reminder_thread(stop_evt: threading.Event, speak: callable) -> None:
    while not stop_evt.is_set():
        try:
            now = int(time.time())
            for rid, text, when in get_due_reminders(now):
                speak(f"Reminder: {text}")
                mark_reminder_done(rid)
        except Exception:
            pass
        stop_evt.wait(30)


def run_assistant(gui: Optional[object] = None) -> None:
    setup_logging()
    init_db()

    # Initialize COM in this thread for SAPI5
    if pythoncom is not None:
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

    # Start dedicated TTS thread (COM-initialized inside)
    tts_thread = TTSEngineThread()
    tts_thread.start()
    speaker = Speaker(tts_thread, gui)
    speak = speaker.speak

    # Ensure reliable speech path by default; user can switch to normal later
    try:
        rt.set_force_powershell_tts(True)
    except Exception:
        pass

    # Greeting
    speak(f"{greeting()} I am {ASSISTANT_NAME}.")

    recognizer = sr.Recognizer()
    # Configure SR for noisy environments using config values
    recognizer.dynamic_energy_threshold = bool(rt.SR_DYNAMIC_ENERGY_OVERRIDE) if rt.SR_DYNAMIC_ENERGY_OVERRIDE is not None else bool(SR_DYNAMIC_ENERGY)
    if not recognizer.dynamic_energy_threshold:
        try:
            thr = int(rt.SR_ENERGY_THRESHOLD_OVERRIDE) if rt.SR_ENERGY_THRESHOLD_OVERRIDE is not None else int(SR_ENERGY_THRESHOLD)
            recognizer.energy_threshold = thr
        except Exception:
            pass
    try:
        recognizer.pause_threshold = float(rt.SR_PAUSE_THRESHOLD_OVERRIDE) if rt.SR_PAUSE_THRESHOLD_OVERRIDE is not None else float(SR_PAUSE_THRESHOLD)
        recognizer.non_speaking_duration = float(rt.SR_NON_SPEAKING_DURATION_OVERRIDE) if rt.SR_NON_SPEAKING_DURATION_OVERRIDE is not None else float(SR_NON_SPEAKING_DURATION)
    except Exception:
        pass

    # Choose audio backend
    voice_mode = True
    use_sounddevice = False
    mic_device_index = None
    try:
        # Prefer a specific microphone if configured
        if PREFERRED_MIC_SUBSTRING:
            names = sr.Microphone.list_microphone_names()
            for idx, name in enumerate(names):
                if PREFERRED_MIC_SUBSTRING.lower() in (name or "").lower():
                    mic_device_index = idx
                    break
        # Probe microphone availability (possibly with chosen device)
        with sr.Microphone(device_index=mic_device_index) as _:
            pass
    except Exception:
        if sd is not None and np is not None:
            use_sounddevice = True
            speak("I couldn't access the default microphone—I'll use an alternative recorder for now.")
            # Ensure robust speech if primary audio stack is flaky
            try:
                rt.set_force_powershell_tts(True)
                speak("I'll also use a more reliable speech system so you can hear me clearly.")
            except Exception:
                pass
        else:
            voice_mode = False
            speak("I couldn't access the microphone. You can type your commands instead.")

    # Apply initial runtime overrides so voice commands can adjust later
    rt.SR_MIC_DEVICE_INDEX = mic_device_index
    rt.USE_SOUNDDEVICE = use_sounddevice

    # Command queue and worker
    cmd_queue: queue.Queue[str] = queue.Queue()
    mem = SessionMemory()
    # GUI text input queue
    gui_input_queue: Optional[queue.Queue[str]] = queue.Queue() if gui is not None else None

    def worker() -> None:
        while True:
            cmd = cmd_queue.get()
            if cmd == "__EXIT__":
                break
            should_exit = handle_command(cmd, speak, mem)
            if should_exit:
                os._exit(0)
            cmd_queue.task_done()

    threading.Thread(target=worker, daemon=True).start()

    # If GUI present, wire text submit callback
    if gui is not None and hasattr(gui, "set_on_submit"):
        try:
            gui.set_on_submit(lambda text: gui_input_queue.put(text) if gui_input_queue is not None else None)
            # Start with typing disabled (voice mode)
            if hasattr(gui, "set_typing_enabled"):
                gui.set_typing_enabled(False)
        except Exception:
            pass

    # Reminders thread
    stop_evt = threading.Event()
    threading.Thread(target=reminder_thread, args=(stop_evt, speak), daemon=True).start()

    def _is_text_mode_command(s: str) -> bool:
        s = (s or "").strip().lower()
        return s in {
            "switch to typing", "switch to text mode", "go to text mode", "typing mode",
            "text mode", "stop listening", "type mode", "switch typing", "switch typing mode"
        }

    # Re-entrant loop: switch between voice and text modes without restart
    while True:
        if voice_mode:
            # Wake-word loop
            last_idle_prompt = 0.0
            alt_recorder_announced = False
            timeouts_in_a_row = 0
            while True:
                try:
                    # Allow runtime switching between backends
                    if rt.USE_SOUNDDEVICE is not None:
                        use_sounddevice = bool(rt.USE_SOUNDDEVICE)
                    # Switch to text mode on request
                    if getattr(rt, "SWITCH_TO_TEXT_MODE", False):
                        speak("Switching to typing mode. You can type your commands.")
                        voice_mode = False
                        # clear the request
                        rt.SWITCH_TO_TEXT_MODE = False
                        # Enable GUI typing if available
                        try:
                            if gui is not None and hasattr(gui, "set_typing_enabled"):
                                gui.set_typing_enabled(True)
                        except Exception:
                            pass
                        break
                    # Idle prompt at controlled interval
                    if IDLE_PROMPT_SECONDS and (time.time() - last_idle_prompt) >= max(5, IDLE_PROMPT_SECONDS):
                        if UI_SET_STATUS:
                            try:
                                UI_SET_STATUS("Waiting for your command…")
                            except Exception:
                                pass
                        # Only speak idle prompt if enough time has passed since last speech
                        # (keeps the console less chatty and avoids talking over task responses)
                        speak("Waiting for your command.")
                        last_idle_prompt = time.time()
                        # Small pause to avoid immediately capturing our own TTS
                        time.sleep(0.25)

                    heard = listen_once_sounddevice(recognizer) if use_sounddevice else listen_once(recognizer)
                    if not heard:
                        timeouts_in_a_row += 1
                        if SR_MAX_TIMEOUTS_BEFORE_TEXT and timeouts_in_a_row >= int(SR_MAX_TIMEOUTS_BEFORE_TEXT):
                            speak("It's quite noisy. I'll switch to typing mode so you can type your command.")
                            voice_mode = False
                            try:
                                if gui is not None and hasattr(gui, "set_typing_enabled"):
                                    gui.set_typing_enabled(True)
                            except Exception:
                                pass
                            break
                        continue
                    timeouts_in_a_row = 0
                    text = heard.lower()
                    # Find which wake word was used (support different lengths)
                    wake_used = None
                    for w in WAKE_WORDS:
                        if w in text:
                            wake_used = w
                    if not wake_used:
                        continue

                    # Extract trailing command in one-shot
                    last_idx = text.rfind(wake_used)
                    trailing = text[last_idx + len(wake_used):].strip() if last_idx >= 0 else ""

                    if trailing:
                        if UI_SET_STATUS:
                            try:
                                UI_SET_STATUS("Processing…")
                            except Exception:
                                pass
                        # If the command is to switch to typing, do it immediately
                        if _is_text_mode_command(trailing):
                            speak("Right away. Switching to typing mode.")
                            voice_mode = False
                            try:
                                rt.SWITCH_TO_TEXT_MODE = False
                            except Exception:
                                pass
                            try:
                                if gui is not None and hasattr(gui, "set_typing_enabled"):
                                    gui.set_typing_enabled(True)
                            except Exception:
                                pass
                            break
                        # Brief verbal acknowledgement for conversational feel
                        speak("On it.")
                        cmd_queue.put(trailing)
                        continue

                    # Two-step: acknowledge then listen
                    beep()
                    speak("Yes?")

                    if UI_SET_STATUS:
                        try:
                            UI_SET_STATUS("Listening…")
                        except Exception:
                            pass
                    # Avoid speaking here to prevent TTS from being captured by the mic
                    # Command window slightly longer than wake
                    # Respect runtime overrides for phrase time limit when possible
                    heard_cmd = (
                        listen_once_sounddevice(recognizer, seconds=7.0)
                        if use_sounddevice
                        else listen_once(recognizer, phrase_time_limit=(rt.SR_PHRASE_TIME_LIMIT_OVERRIDE or 12.0))
                    )
                    if not heard_cmd:
                        speak("Sorry, I didn't hear a command.")
                        continue
                    if UI_SET_STATUS:
                        try:
                            UI_SET_STATUS("Processing…")
                        except Exception:
                            pass
                    # If the command is to switch to typing, do it immediately
                    if _is_text_mode_command(heard_cmd):
                        speak("Right away. Switching to typing mode.")
                        voice_mode = False
                        try:
                            rt.SWITCH_TO_TEXT_MODE = False
                        except Exception:
                            pass
                        try:
                            if gui is not None and hasattr(gui, "set_typing_enabled"):
                                gui.set_typing_enabled(True)
                        except Exception:
                            pass
                        break
                    # Short acknowledgement before processing
                    speak("On it.")
                    cmd_queue.put(heard_cmd)

                except KeyboardInterrupt:
                    speak("Goodbye.")
                    return
                except Exception:
                    # Try fallback switch if available
                    if not use_sounddevice and sd is not None and np is not None:
                        use_sounddevice = True
                        # Persist runtime choice to avoid flip-flop
                        try:
                            rt.USE_SOUNDDEVICE = True
                        except Exception:
                            pass
                        if not alt_recorder_announced:
                            speak("Switching to an alternative recorder for your microphone.")
                            try:
                                rt.set_force_powershell_tts(True)
                                speak("I'll also use a more reliable speech system so you can hear me clearly.")
                            except Exception:
                                pass
                            alt_recorder_announced = True
                        # Small backoff to avoid tight loop
                        time.sleep(0.2)
                        continue
                    speak("I lost access to audio input. Switching to text mode.")
                    voice_mode = False
                    break
            # Loop back to check mode
            continue
        else:
            # Text mode
            while True:
                try:
                    if gui_input_queue is not None:
                        # Wait for input from GUI entry
                        cmd = gui_input_queue.get()
                    else:
                        cmd = input("Type a command (or 'exit' to quit; type 'voice mode' to switch back)> ").strip()
                    if not cmd:
                        continue
                    low = cmd.lower()
                    if low in {"voice mode", "switch to voice", "start listening", "voice", "back to voice"}:
                        try:
                            rt.request_voice_mode()
                        except Exception:
                            pass
                        speak("Switching to voice mode. Say 'Hey Jarvis' when you're ready.")
                        # clear text-mode request flag if any
                        rt.SWITCH_TO_TEXT_MODE = False
                        voice_mode = True
                        # Disable GUI typing if available
                        try:
                            if gui is not None and hasattr(gui, "set_typing_enabled"):
                                gui.set_typing_enabled(False)
                        except Exception:
                            pass
                        break
                    cmd_queue.put(cmd)
                except KeyboardInterrupt:
                    speak("Goodbye.")
                    return
            # Loop back to check mode
            continue


# Simple UI hooks populated when GUI is available
UI_SET_STATUS = None  # type: ignore
UI_ADD_HISTORY = None  # type: ignore


def main() -> None:
    gui = None
    if JarvisGUI is not None:
        try:
            from config import GUI_ENABLED
            if GUI_ENABLED:
                gui = JarvisGUI()
        except Exception:
            gui = None

    global UI_SET_STATUS, UI_ADD_HISTORY
    if gui is not None:
        UI_SET_STATUS = gui.set_status
        UI_ADD_HISTORY = gui.add_history
        # Run assistant in a worker thread, GUI in main thread
        t = threading.Thread(target=run_assistant, args=(gui,), daemon=True)
        t.start()
        gui.set_status("Starting…")
        gui.add_history(f"{ASSISTANT_NAME} is online.")
        gui.run()
    else:
        # No GUI, run assistant directly
        def _set_status(_):
            pass
        def _add_hist(msg):
            pass
        UI_SET_STATUS = _set_status
        UI_ADD_HISTORY = _add_hist
        run_assistant(None)


if __name__ == "__main__":
    main()
