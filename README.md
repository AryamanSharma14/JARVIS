<div align="center">

# JARVIS — Windows Voice Assistant

Smart, reliable, and customizable voice assistant for Windows. Speaks every response, controls your system, searches the web, plays Spotify, shows a neon GUI, and handles reminders, timers, notes, weather, news, and more.

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-informational)

</div>

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick start](#quick-start-windows-powershell)
- [Supported voice commands](#supported-voice-commands-examples)
- [Spotify API playback (optional)](#spotify-api-playback-optional)
- [Configuration](#configuration)
- [GUI](#gui)
- [Notes & troubleshooting](#notes--troubleshooting)
- [Project structure](#project-structure)

## Features
- Wake word: “Hey Jarvis” (one-shot or two-step)
- Speech recognition with `speech_recognition` (PyAudio or `sounddevice` fallback)
- Robust text-to-speech with layered fallbacks (SAPI5/pyttsx3 → COM SAPI → PowerShell); all responses are spoken
- Web: Google/Wikipedia search, open popular sites; in-site searches (YouTube, LinkedIn, Twitter/X, Reddit, Spotify, Facebook, Instagram)
- Music: Spotify direct playback via Web API (optional); play/pause/next/previous with API or media keys
- System control: volume, brightness, screenshots, battery/system/internet status
- Info: weather (auto-location), news headlines, definitions, translations, currency and temperature conversions, IP/location
- Productivity: reminders, timers, notes (SQLite)
- GUI: neon blue/black theme, chat history, system tiles (CPU/RAM/Battery), typing mode input
- Noise handling: ambient calibration, sensitivity controls, longer listening windows, auto-switch to typing after repeated timeouts

## Requirements
- Windows, Python 3.9+
- Microphone for voice input (PyAudio or sounddevice fallback)

## Quick start (Windows PowerShell)

```powershell
# 1) Create & activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Optional: Microphone backends
# A) PyAudio (classic, may need prebuilt wheels on new Python versions)
#    If you try this and it fails on Python 3.13+, use option B instead.
pip install pipwin
pipwin install pyaudio

# B) sounddevice fallback (no PyAudio needed)
#    This assistant can record audio via the sounddevice library as a fallback.
#    If PyAudio fails, just ensure these are installed (already included in requirements):
pip install sounddevice numpy

# 3) Run the assistant
python .\main.py
```

Tip: Say “Hey Jarvis” and speak a command. In very noisy rooms, use the GUI typing box or say “switch to typing mode”.

## Supported voice commands (examples)
- "what time is it" / "tell me the time"
- "what is the date" / "today's date"
- "search wikipedia for [topic]"
- "search google for [query]"
- "open youtube"
- "open google"
- "open [site]" (github, stackoverflow, gmail, maps, news, weather, whatsapp, reddit, twitter/x, facebook, instagram)
- "play music"
- "play [song or artist] on spotify"
- "pause" / "resume" / "next" / "previous"
  - Uses Spotify API when configured, falling back to system media keys on Windows
- "open calculator" (Windows)
- "open notepad" (Windows)
- "open file explorer" (Windows)
- "tell me a joke"
- "exit" / "quit" / "goodbye"
- "battery status" / "system status" / "check internet"
- "weather in [city]" / "weather report"
- "today's news" (top 5)
- "set volume to 50%" / "increase volume" / "decrease volume"
- "set brightness to 70%"
- "take a screenshot"
- "set timer for 10 minutes"
- "remind me to [task] in [10 minutes]"
- "take a note [content]"
- "calculate 25 * 43"
- "convert 100 USD to INR" / "convert 100 fahrenheit to celsius"
- "define [word]" / "translate [phrase] to [language]"
- "what's my IP address" / "where am I"

You can also combine the wake word with the command in one phrase, for example:
- "Hey Jarvis, search google for dantdm"
- "Hey Jarvis, open youtube"

## Notes & troubleshooting
- If PyAudio is missing but `sounddevice` is installed, the app will still listen via the fallback recorder.
- If neither PyAudio nor `sounddevice` is available, the app falls back to text input mode (you can type commands).
- Wikipedia searches require internet access; if unavailable or ambiguous, you’ll get a friendly message.
- In very noisy rooms, try: “use fixed threshold 600”, or “don’t cut me off” for longer listening, or switch to typing mode from the GUI.
- On some systems, Spotify app URIs may not work; the assistant will open the Spotify web player as a fallback.

### Spotify API playback (optional)
If you want Jarvis to actually start playback on your Spotify account (without manual clicking), configure the Spotify API:

1) In `config.py`, set these values:

	- `SPOTIFY_CLIENT_ID`
	- `SPOTIFY_CLIENT_SECRET`
	- `SPOTIFY_REFRESH_TOKEN`

2) Getting a refresh token (one-time):

	- Create an app at https://developer.spotify.com/ and add a Redirect URI (e.g., `http://localhost:8080/callback`).
	- Perform the Authorization Code flow to obtain a refresh token for your account. Many online guides/tools can help you complete this quickly.
	- Paste the refresh token into `config.py`.

Once configured, commands like “play [song name] on spotify” will search and start playback on your active Spotify device. If no active device exists, Jarvis will try to open Spotify and start playback. If credentials are missing or an API call fails, it will fall back to opening Spotify search.

## Configuration

All preferences live in `config.py`:
- Assistant/user names, wake words, GUI toggle
- Paths (DB, logs, screenshots)
- Feeds and API endpoints for weather/news/etc.
- TTS settings: rate, volume, preferred voice name
- Speech recognition tuning for noisy rooms:
	- `SR_DYNAMIC_ENERGY` (auto sensitivity) or `SR_ENERGY_THRESHOLD` (fixed)
	- `SR_PAUSE_THRESHOLD`, `SR_NON_SPEAKING_DURATION`
	- `SR_ADJUST_DURATION`, `SR_PHRASE_TIME_LIMIT`
	- `SR_MAX_TIMEOUTS_BEFORE_TEXT` (auto-switch to typing after repeated timeouts)

## GUI

- Neon blue/black theme with a pulsing ring and a “J” logo
- Right-side chat with colored roles
- Live tiles for CPU/RAM/Battery
- Typing mode input at the bottom (enabled when you switch to typing)

## Project structure
- `main.py` — entry point (wake word, TTS, queue, reminders)
- `jarvis_brain.py` — command parsing and behavior
- `system_control.py` — OS-level control (volume, brightness, screenshots, power)
- `web_services.py` — APIs for weather/news/definitions/translation/currency/ip/location
- `database.py` — SQLite reminders and notes
- `config.py` — preferences (assistant name, user name, feeds, paths)
- `gui.py` — neon Tkinter GUI (chat history, system tiles, typing input)
- `requirements.txt` — dependency list
- `README.md` — setup and usage instructions

---

<sub>Built with ❤️ for Windows by Aryaman. Contributions and issues welcome.</sub>
