"""
Voice Assistant
---------------
A simple Python voice assistant that listens for commands, responds with speech,
and handles time/date queries, Wikipedia searches, opening websites, playing music,
and telling jokes.

Requirements (install via requirements.txt):
- SpeechRecognition
- pyttsx3
- wikipedia
- pyjokes

Notes:
- Microphone input requires PyAudio. On Windows, consider:
    pip install pipwin
    pipwin install pyaudio
- If a microphone is not available, this script falls back to text input mode.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import re
import subprocess
import time
import webbrowser
from urllib.parse import quote_plus

import pyttsx3
import speech_recognition as sr
import wikipedia
from wikipedia import exceptions as wiki_exc
import pyjokes

# Optional fallback for audio capture when PyAudio is unavailable
try:
    import sounddevice as sd
    import numpy as np
except Exception:
    sd = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

# -----------------------------
# Text-to-Speech (pyttsx3)
# -----------------------------
try:
    # Force Windows SAPI5 for better reliability on Windows
    _engine = pyttsx3.init(driverName='sapi5')
except Exception:
    _engine = pyttsx3.init()
_engine.setProperty("rate", 185)  # Adjust speaking speed if desired
_engine.setProperty("volume", 1.0)
try:
    # Try to pick a voice that says the assistant's name clearly (optional)
    voices = _engine.getProperty('voices')
    if voices:
        # Prefer English voices; fallback to first
        en_voice = next((v for v in voices if 'english' in (v.name or '').lower()), None)
        _engine.setProperty('voice', en_voice.id if en_voice else voices[0].id)
except Exception:
    pass


def speak(text: str) -> None:
    """Speak the given text aloud and also print it for visibility."""
    print(f"Assistant: {text}")
    try:
        _engine.say(text)
        _engine.runAndWait()
    except Exception:
        # If the TTS engine errors (e.g., no audio output), just print.
        pass


# Assistant identity and wake word
ASSISTANT_NAME = "Jarvis"
WAKE_WORDS = [
    f"hey {ASSISTANT_NAME.lower()}",
    f"hi {ASSISTANT_NAME.lower()}",
    f"ok {ASSISTANT_NAME.lower()}",
    f"okay {ASSISTANT_NAME.lower()}",
]

try:
    import winsound
    def beep(freq: int = 1000, dur_ms: int = 120) -> None:
        try:
            winsound.Beep(freq, dur_ms)
        except Exception:
            pass
except Exception:
    def beep(freq: int = 1000, dur_ms: int = 120) -> None:  # type: ignore[no-redef]
        pass


# -----------------------------
# Command handlers
# -----------------------------

def tell_time() -> None:
    now = _dt.datetime.now().strftime("%I:%M %p").lstrip("0")
    speak(f"The time is {now}.")


def tell_date() -> None:
    today = _dt.datetime.now().strftime("%A, %B %d, %Y")
    speak(f"Today is {today}.")


def open_youtube() -> None:
    try:
        webbrowser.open("https://www.youtube.com", new=2)
        speak("Opening YouTube.")
    except Exception:
        speak("Sorry, I couldn't open YouTube.")


def open_google() -> None:
    try:
        webbrowser.open("https://www.google.com", new=2)
        speak("Opening Google.")
    except Exception:
        speak("Sorry, I couldn't open Google.")


def open_website(name: str) -> None:
    """Open a popular website by name, with a sensible fallback to .com."""
    sites = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "stackoverflow": "https://stackoverflow.com",
        "gmail": "https://mail.google.com",
        "maps": "https://maps.google.com",
        "news": "https://news.google.com",
        "weather": "https://www.google.com/search?q=weather",
        "whatsapp": "https://web.whatsapp.com",
        "spotify": "https://open.spotify.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "x": "https://twitter.com",
        "facebook": "https://www.facebook.com",
        "instagram": "https://www.instagram.com",
    }
    url = sites.get(name.lower())
    if not url:
        # fallback to .com
        url = f"https://{name}.com"
    try:
        webbrowser.open(url, new=2)
        speak(f"Opening {name}.")
    except Exception:
        speak(f"Sorry, I couldn't open {name}.")


def play_music() -> None:
    """Try to open Spotify app; fall back to the web player."""
    # Try Windows app via URI or os.startfile
    if platform.system() == "Windows":
        try:
            os.startfile("spotify:")  # type: ignore[attr-defined]
            speak("Opening Spotify.")
            return
        except Exception:
            pass
    # Try generic URI via webbrowser
    try:
        opened = webbrowser.open("spotify:", new=2)
        if opened:
            speak("Opening Spotify.")
            return
    except Exception:
        pass
    # Fallback to web player
    try:
        webbrowser.open("https://open.spotify.com", new=2)
        speak("Opening Spotify on the web.")
    except Exception:
        speak("Sorry, I couldn't open a music player.")


def open_calculator() -> None:
    try:
        subprocess.Popen(["calc.exe"])  # Windows Calculator
        speak("Opening Calculator.")
    except Exception:
        speak("Sorry, I couldn't open Calculator.")


def open_notepad() -> None:
    try:
        subprocess.Popen(["notepad.exe"])  # Windows Notepad
        speak("Opening Notepad.")
    except Exception:
        speak("Sorry, I couldn't open Notepad.")


def open_file_explorer(path: str | None = None) -> None:
    try:
        if path:
            subprocess.Popen(["explorer.exe", path])
        else:
            subprocess.Popen(["explorer.exe"])  # Opens This PC
        speak("Opening File Explorer.")
    except Exception:
        speak("Sorry, I couldn't open File Explorer.")


def tell_joke() -> None:
    try:
        joke = pyjokes.get_joke()
        speak(joke)
    except Exception:
        speak("Sorry, I couldn't fetch a joke right now.")


def search_wikipedia(topic: str) -> None:
    if not topic:
        speak("Please tell me what to search for on Wikipedia.")
        return
    try:
        # Try with strict options first to reduce ambiguity
        summary = wikipedia.summary(topic, sentences=2, auto_suggest=False, redirect=True)
        speak(summary)
    except wiki_exc.DisambiguationError as e:
        # Pick the first option if available
        option = e.options[0] if e.options else None
        if option:
            try:
                summary = wikipedia.summary(option, sentences=2, auto_suggest=True)
                speak(summary)
                return
            except Exception:
                pass
        speak("That topic is ambiguous. Please be more specific.")
    except wiki_exc.PageError:
        speak("I couldn't find a Wikipedia page for that topic.")
    except Exception:
        speak("I had trouble reaching Wikipedia. Please check your internet connection.")


def search_google(query: str) -> None:
    if not query:
        speak("Please tell me what to search for on Google.")
        return
    try:
        url = "https://www.google.com/search?q=" + quote_plus(query)
        webbrowser.open(url, new=2)
        speak(f"Searching Google for {query}.")
    except Exception:
        speak("Sorry, I couldn't open Google search.")


# -----------------------------
# Speech recognition utilities
# -----------------------------

def listen_once(recognizer: sr.Recognizer, timeout: float = 5.0, phrase_time_limit: float = 8.0) -> str | None:
    """Listen for a single utterance and return lowercased text, or None on failure."""
    print("Listening...")
    try:
        with sr.Microphone() as source:
            # Adjust for ambient noise for better accuracy
            try:
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
            except Exception:
                # Non-fatal
                pass
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except OSError:
        # Microphone not available
        raise
    except sr.WaitTimeoutError:
        print("(No speech detected within timeout)")
        return None

    try:
        text = recognizer.recognize_google(audio)
        text = text.strip()
        if text:
            print(f"You said: {text}")
            return text.lower()
        return None
    except sr.UnknownValueError:
        speak("Sorry, I didn't understand that. Can you repeat?")
        return None
    except sr.RequestError:
        speak("I couldn't reach the speech service. Please check your internet.")
        return None
    except Exception:
        speak("Something went wrong while recognizing speech.")
        return None


def listen_once_sounddevice(
    recognizer: sr.Recognizer, *, samplerate: int = 16000, seconds: float = 6.0
) -> str | None:
    """Record audio using sounddevice as a PyAudio-free fallback and recognize it.

    Note: Without VAD, we record a fixed window. Keep prompts short.
    """
    if sd is None or np is None:
        raise OSError("sounddevice fallback not available")

    print("Listening...")
    try:
        # Record mono 16-bit PCM for a fixed window
        frames = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1, dtype="int16")
        sd.wait()
        raw = frames.tobytes()
    except Exception:
        raise OSError("Recording failed")

    audio = sr.AudioData(raw, samplerate, sample_width=2)
    try:
        text = recognizer.recognize_google(audio)
        text = text.strip()
        if text:
            print(f"You said: {text}")
            return text.lower()
        return None
    except sr.UnknownValueError:
        speak("Sorry, I didn't understand that. Can you repeat?")
        return None
    except sr.RequestError:
        speak("I couldn't reach the speech service. Please check your internet.")
        return None
    except Exception:
        speak("Something went wrong while recognizing speech.")
        return None


def handle_command(cmd: str) -> bool:
    """Handle a recognized command. Return True to exit the program."""
    c = cmd.lower().strip()

    # Exit commands
    if any(p in c for p in ["exit", "quit", "goodbye", "good bye"]):
        speak("Goodbye!")
        return True

    # Time
    if any(p in c for p in ["what time is it", "tell me the time", "time"]):
        tell_time()
        return False

    # Date
    if any(p in c for p in ["what is the date", "today's date", "todays date", "date"]):
        tell_date()
        return False

    # Open sites
    if "open youtube" in c:
        open_youtube()
        return False
    if "open google" in c:
        open_google()
        return False
    # Generic open <site>
    m_site = re.search(r"open\s+([a-z0-9 ._-]+)$", c)
    if m_site:
        name = m_site.group(1).strip().replace(" ", "")
        if name and name not in ("youtube", "google"):
            open_website(name)
            return False

    # Play music
    if "play music" in c or "open spotify" in c:
        play_music()
        return False

    # Joke
    if "tell me a joke" in c or c == "joke" or "joke" in c:
        tell_joke()
        return False

    # Wikipedia search (e.g., "search wikipedia for alan turing")
    m = re.search(r"search\s+wikipedia\s+for\s+(.+)", c)
    if m:
        topic = m.group(1).strip()
        search_wikipedia(topic)
        return False

    # Google search
    m = re.search(r"search\s+google\s+for\s+(.+)", c)
    if m:
        query = m.group(1).strip()
        search_google(query)
        return False

    # Windows apps
    if "open calculator" in c or "calculator" in c:
        open_calculator()
        return False
    if "open notepad" in c or "notepad" in c:
        open_notepad()
        return False
    if "open file explorer" in c or "open explorer" in c or c == "explorer":
        open_file_explorer()
        return False

    # Small talk
    if any(p in c for p in ["what is your name", "what's your name", "who are you"]):
        speak("I'm your voice assistant. Ready when you are.")
        return False

    # Unknown command
    speak("Sorry, I didn't understand that. Can you repeat?")
    return False


# -----------------------------
# Main application loop
# -----------------------------

def main() -> None:
    speak(f"Hello! I am {ASSISTANT_NAME}, your voice assistant. How can I help you?")

    recognizer = sr.Recognizer()

    # Try voice mode first; fall back to text mode if microphone is not available
    voice_mode = True
    use_sounddevice = False
    try:
        # Probe microphone availability (uses PyAudio)
        with sr.Microphone() as _:
            pass
    except (OSError, AttributeError):
        # If PyAudio/mic is unavailable, try sounddevice fallback
        if sd is not None and np is not None:
            use_sounddevice = True
            print("PyAudio not available. Using sounddevice fallback for recording.")
            speak("Microphone driver is unavailable. I'll try an alternative recording method.")
        else:
            voice_mode = False
            print("Microphone or PyAudio not available. Falling back to text input mode.")
            speak("I couldn't access the microphone. You can type your commands instead.")

    if voice_mode:
        # Wake-word-driven flow: listen for "hey jarvis"; then parse command
        while True:
            try:
                # 1) Listen for wake word (no TTS to avoid feedback)
                print("Listening for wake word...")
                if use_sounddevice:
                    heard = listen_once_sounddevice(recognizer)
                else:
                    heard = listen_once(recognizer)
                if not heard:
                    continue

                text = heard.lower()
                if not any(w in text for w in WAKE_WORDS):
                    # Ignore phrases without wake word
                    continue

                # Beep and acknowledge
                beep()
                speak("Yes?")

                # Extract any trailing command after the last occurrence of the wake phrase
                last_idx = max((text.rfind(w) for w in WAKE_WORDS), default=-1)
                trailing = text[last_idx + len("hey jarvis"):].strip() if last_idx >= 0 else ""

                # If the user said the command in the same utterance, use it; else listen for the command
                if trailing:
                    if handle_command(trailing):
                        break
                    continue

                # 2) Listen for the command itself
                print("Listening for command...")
                speak("Listening...")
                if use_sounddevice:
                    cmd = listen_once_sounddevice(recognizer)
                else:
                    cmd = listen_once(recognizer)
                if not cmd:
                    speak("Sorry, I didn't hear a command.")
                    continue
                if handle_command(cmd):
                    break
            except (OSError, AttributeError):
                # Mic became unavailable mid-session, or fallback failed
                if not use_sounddevice and sd is not None and np is not None:
                    # Try switching to sounddevice fallback once
                    use_sounddevice = True
                    print("Switching to sounddevice fallback.")
                    speak("Switching to an alternative recording method.")
                    continue
                print("Microphone/recording error. Switching to text input mode.")
                speak("I lost access to audio input. Switching to text mode.")
                voice_mode = False
                break
            except KeyboardInterrupt:
                print("\nInterrupted. Exiting.")
                break
            except Exception:
                # Catch-all to keep the loop alive
                print("Unexpected error in main loop.")
                time.sleep(0.3)
                continue

    if not voice_mode:
        # Text fallback mode
        while True:
            try:
                cmd = input("Type a command (or 'exit' to quit)> ").strip()
                if not cmd:
                    continue
                if handle_command(cmd):
                    break
            except KeyboardInterrupt:
                print("\nInterrupted. Exiting.")
                break
            except Exception:
                print("Unexpected error in text mode.")
                continue


if __name__ == "__main__":
    main()
