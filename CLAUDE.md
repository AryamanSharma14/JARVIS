# ARVIS — Project Guide

## Overview
Windows voice assistant (renamed Jarvis → **ARVIS**) with an Iron Man HUD web GUI. Responds to wake words, speaks every reply, controls the OS, integrates with Spotify, and uses a local Ollama LLM (`llama3.2`) for conversational AI. Falls back to a legacy regex brain if Ollama is offline.

## Running the project
```bash
# Use venv Python directly (most reliable in Git Bash)
.venv/Scripts/python.exe main.py
```

## Project structure
| File/Dir | Role |
|---|---|
| `main.py` | Entry point — wake-word loop, TTS thread, SR backends, Ollama health check, reminder daemon |
| `jarvis_brain.py` | Legacy regex brain (fallback when LLM offline; also provides `greeting()`) |
| `gui.py` | Neon Tkinter GUI (optional, superseded by web GUI) |
| `web_gui.py` | Iron Man HUD — Flask-SocketIO web GUI; `set_llm_status()` drives LLM badge |
| `config.py` | All user-editable preferences (names, SR tuning, TTS, Spotify/Ollama creds) |
| `system_control.py` | OS-level control — volume, brightness, screenshots, power |
| `web_services.py` | Weather, news, definitions, translation, currency, IP |
| `database.py` | SQLite helpers for reminders and notes (`jarvis.db`) |
| `runtime_control.py` | Runtime flags for switching modes without restart |
| `spotify_api.py` | Spotify Web API playback integration |
| `core/brain.py` | `ARVISBrain` — Ollama tool-use loop, respects `LLM_ENABLED`, falls back to regex brain |
| `core/memory.py` | Rolling conversation history (20 turns) + persistent facts → `data/memory.json` |
| `core/tools.py` | 13 Claude/Ollama tool schemas + `execute_tool()` dispatcher |
| `static/` | Web HUD assets — `index.html`, `style.css`, `app.js` |

## Key dependencies (`requirements.txt`)
- `SpeechRecognition`, `sounddevice`, `numpy` — audio input (PyAudio optional)
- `pyttsx3` + Windows SAPI5 / PowerShell fallbacks — TTS
- `edge-tts` — optional neural TTS (highest quality)
- `flask`, `flask-socketio` — web GUI
- `psutil`, `screen-brightness-control`, `pycaw`, `pyautogui`, `Pillow` — system control
- `requests`, `feedparser`, `wikipedia`, `deep-translator`, `pyjokes` — web features

Install: `pip install -r requirements.txt`

## Configuration (`config.py`)
Key settings:
- `ASSISTANT_NAME = "Arvis"`, `WAKE_WORDS` — auto-derived from name
- `LLM_ENABLED` — `True` to use Ollama; `False` to force regex brain
- `OLLAMA_HOST`, `OLLAMA_MODEL` — Ollama endpoint and model (`llama3.2`)
- `WEB_GUI_ENABLED`, `WEB_GUI_PORT` — enable Iron Man HUD (default port 5000)
- `GUI_ENABLED` — show/hide legacy Tkinter window
- `TTS_RATE`, `TTS_VOLUME`, `TTS_VOICE_NAME` — speech output
- `EDGE_TTS_ENABLED`, `EDGE_TTS_VOICE` — neural TTS via Edge
- `SR_DYNAMIC_ENERGY`, `SR_ENERGY_THRESHOLD`, `SR_PAUSE_THRESHOLD`, etc. — SR tuning
- `SR_MAX_TIMEOUTS_BEFORE_TEXT` — auto-switch to typing after N timeouts
- `IDLE_PROMPT_SECONDS` — idle speech interval (0 = off)
- `SPOTIFY_CLIENT_ID/SECRET/REFRESH_TOKEN` — Spotify API (optional)
- `DEFAULT_CITY` — fallback city for weather

> **Security note:** `config.py` contains real API credentials. Do not commit to public repos.

## Ollama setup (LLM brain)
1. Download from https://ollama.com/download and install
2. `ollama pull llama3.2`
3. `ollama serve` (runs automatically on Windows after install)
4. Restart ARVIS — HUD badge turns green, spoken confirmation plays

At startup `main.py` pings `OLLAMA_HOST/api/tags`. If unreachable: spoken setup instructions + red LLM badge in HUD. If reachable: green badge shows model name.

## LLM tool list (13 tools in `core/tools.py`)
`open_application`, `search_web`, `get_system_info`, `set_volume`, `set_brightness`,
`take_screenshot`, `get_weather`, `get_news`, `create_reminder`, `search_files`,
`play_spotify`, `remember_fact`, `exit_assistant`

## Audio backend priority
1. `PyAudio` via `sr.Microphone` (preferred)
2. `sounddevice` fallback if PyAudio unavailable
3. Text/typing mode if no audio available

## TTS backend priority
1. `edge-tts` neural voice (best quality, if installed)
2. PowerShell `System.Speech.Synthesis.SpeechSynthesizer` (forced on by default)
3. `pyttsx3` SAPI5 engine
4. Direct `comtypes` SAPI (`SAPI.SpVoice`)

`rt.FORCE_POWERSHELL_TTS = True` is set on startup for reliability.

## Architecture notes
- TTS runs in a dedicated daemon thread (`TTSEngineThread`) with a queue — never call `engine.runAndWait()` from the main thread.
- Commands dispatched via `cmd_queue` to a worker thread; `process()` / `handle_command()` returns `True` to exit.
- Web GUI (Flask-SocketIO) runs on the main thread; assistant loop runs in a daemon thread.
- `runtime_control.py` holds global flags for mode switching (voice ↔ text) without restarting.
- `core/brain.py` checks `LLM_ENABLED` first, then tries Ollama; `ConnectionError` falls through to regex brain with actionable spoken instructions.

## Platform
Windows only. Requires Python 3.9+. Uses `winsound`, `SAPI5`, and PowerShell APIs.
