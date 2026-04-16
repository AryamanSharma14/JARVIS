"""
Iron Man HUD Web GUI for ARVIS.
Drop-in replacement for JarvisGUI — same 5-method interface.
Uses Flask-SocketIO so the browser auto-opens and receives real-time events.
"""
from __future__ import annotations

import os
import threading
import webbrowser
from collections import deque
from typing import Callable, Optional

import psutil

# Flask / SocketIO — soft import so the rest of the app keeps working if missing
try:
    from flask import Flask, render_template_string, send_from_directory
    from flask_socketio import SocketIO, emit
    _FLASK_OK = True
except ImportError:
    _FLASK_OK = False


def _tag_for(text: str) -> str:
    """Mirror gui.py tag logic."""
    if text.startswith("Arvis:") or text.startswith("ARVIS:"):
        return "jarvis"
    if text.startswith("You said:") or text.startswith("You:"):
        return "user"
    return "system"


class WebGUI:
    """Iron Man HUD web interface — drop-in for JarvisGUI."""

    IS_WEB_GUI = True  # detected by main.py to choose routing strategy

    def __init__(self, port: int = 5000) -> None:
        if not _FLASK_OK:
            raise RuntimeError("flask and flask-socketio are required: pip install flask flask-socketio")

        self._port = port
        self._on_submit: Optional[Callable[[str], None]] = None
        self._typing_enabled = True  # web UI always accepts text input
        self._history_buf: deque = deque(maxlen=50)  # replay on connect
        self._current_status = {"text": "Online", "state": "idle"}
        self._llm_status: Optional[dict] = None

        # Locate static/ folder next to this file
        static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

        self._app = Flask(__name__, static_folder=static_folder, static_url_path="/static")
        self._app.config["SECRET_KEY"] = "arvis-hud-secret"
        self._sio = SocketIO(
            self._app,
            async_mode="threading",
            cors_allowed_origins="*",
        )

        self._register_routes()
        self._register_events()

    # ------------------------------------------------------------------
    # Public interface (mirrors JarvisGUI exactly)
    # ------------------------------------------------------------------

    def set_status(self, text: str, state: str = "") -> None:
        """Update status text and optional state class (idle/listening/processing)."""
        if not state:
            low = text.lower()
            if "listen" in low:
                state = "listening"
            elif "process" in low or "thinking" in low:
                state = "processing"
            else:
                state = "idle"
        self._current_status = {"text": text, "state": state}
        self._sio.emit("status", self._current_status)

    def add_history(self, text: str) -> None:
        """Append a message to chat history."""
        item = {"text": text, "tag": _tag_for(text)}
        self._history_buf.append(item)
        self._sio.emit("history", item)

    def set_on_submit(self, callback: Callable[[str], None]) -> None:
        """Store the callback for user text input."""
        self._on_submit = callback

    def set_llm_status(self, online: bool, model: str = "") -> None:
        """Emit LLM online/offline status to the browser HUD."""
        item = {"online": online, "model": model}
        self._llm_status = item
        self._sio.emit("llm_status", item)

    def set_typing_enabled(self, enabled: bool) -> None:
        """Web UI always keeps input enabled; ignore disable requests."""
        # Voice-mode gating doesn't apply to a browser — always allow typing
        self._sio.emit("typing_enabled", {"enabled": True})

    def run(self) -> None:
        """BLOCKING. Start Flask-SocketIO and open browser."""
        url = f"http://localhost:{self._port}"
        threading.Timer(1.5, webbrowser.open, args=[url]).start()
        self._sio.run(
            self._app,
            host="0.0.0.0",
            port=self._port,
            allow_unsafe_werkzeug=True,
            log_output=False,
        )

    # ------------------------------------------------------------------
    # Internal — routes
    # ------------------------------------------------------------------

    def _register_routes(self) -> None:
        app = self._app
        static_folder = app.static_folder

        @app.route("/")
        def index():
            idx = os.path.join(static_folder, "index.html")
            with open(idx, encoding="utf-8") as f:
                return f.read()

        @app.route("/static/<path:filename>")
        def static_files(filename):
            return send_from_directory(static_folder, filename)

    # ------------------------------------------------------------------
    # Internal — Socket.IO events
    # ------------------------------------------------------------------

    def _register_events(self) -> None:
        sio = self._sio

        @sio.on("connect")
        def on_connect():
            # Replay buffered history so the startup greeting is always visible
            for item in list(self._history_buf):
                emit("history", item)
            emit("status", self._current_status)
            emit("typing_enabled", {"enabled": True})  # always enabled for web
            if self._llm_status is not None:
                emit("llm_status", self._llm_status)

        @sio.on("user_input")
        def on_user_input(data):
            text = (data.get("text") or "").strip()
            if text and self._on_submit:
                self.add_history(f"You: {text}")
                threading.Thread(target=self._on_submit, args=(text,), daemon=True).start()

        # Stats daemon
        self._start_stats_daemon()

    def _start_stats_daemon(self) -> None:
        """Push CPU/RAM/battery every 2 seconds."""
        sio = self._sio

        def _loop():
            while True:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory().percent
                    bat = psutil.sensors_battery()
                    pwr = bat.percent if bat else 100
                except Exception:
                    cpu = mem = pwr = 0
                sio.emit("stats", {"cpu": cpu, "mem": mem, "pwr": pwr})
                sio.sleep(2)

        self._sio.start_background_task(_loop)
