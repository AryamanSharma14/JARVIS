"""
Windows system control operations: volume, brightness, screenshots, power actions.
Falls back gracefully if capabilities are unavailable.
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional  # noqa: F401
import ctypes

# Windows virtual key codes
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

def _send_volume_key(vk: int, repeat: int = 1) -> None:
    try:
        for _ in range(max(1, repeat)):
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    except Exception:
        pass

def _send_media_key(vk: int, repeat: int = 1) -> None:
    try:
        for _ in range(max(1, repeat)):
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
    except Exception:
        pass

# Volume via pycaw (Windows)
try:
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAVE_PYCAW = True
except Exception:
    HAVE_PYCAW = False

# Brightness
try:
    import screen_brightness_control as sbc
    HAVE_BRIGHTNESS = True
except Exception:
    HAVE_BRIGHTNESS = False

# Screenshot
try:
    import pyautogui
    HAVE_PYAUTOGUI = True
except Exception:
    HAVE_PYAUTOGUI = False


def set_volume(percent: int) -> str:
    percent = max(0, min(100, percent))
    # Prefer precise control via pycaw when available
    if HAVE_PYCAW:
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            vol_range = volume.GetVolumeRange()  # (min, max, step)
            min_vol, max_vol = vol_range[0], vol_range[1]
            target = min_vol + (max_vol - min_vol) * (percent / 100.0)
            volume.SetMasterVolumeLevel(target, None)
            return f"Volume set to {percent} percent."
        except Exception:
            # Fall through to key-event approximation
            pass
    # Fallback: approximate using volume keys (reduce to near-zero, then step up)
    try:
        # Drive volume to minimum with ample repeats
        _send_volume_key(VK_VOLUME_DOWN, repeat=60)
        # Windows volume keys typically change in ~2% increments; approximate steps
        steps_up = max(0, int(round(percent / 2)))
        if steps_up > 0:
            _send_volume_key(VK_VOLUME_UP, repeat=steps_up)
        # Nudge once to ensure unmuted if percent > 0
        if percent > 0:
            _send_volume_key(VK_VOLUME_UP, repeat=1)
        return f"Volume set to about {percent} percent."
    except Exception:
        return "I couldn't adjust the volume."


def volume_up(step: int = 10) -> str:
    if not HAVE_PYCAW:
        # Fallback: simulate key presses (rough approximation)
        _send_volume_key(VK_VOLUME_UP, repeat=max(1, step // 5))
        return "Volume increased."
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        min_vol, max_vol, _ = volume.GetVolumeRange()
        current = volume.GetMasterVolumeLevel()
        new = min(max_vol, current + (max_vol - min_vol) * (step / 100.0))
        volume.SetMasterVolumeLevel(new, None)
        return "Volume increased."
    except Exception:
        # Fallback to key events on error
        _send_volume_key(VK_VOLUME_UP, repeat=max(1, step // 5))
        return "Volume increased."


def volume_down(step: int = 10) -> str:
    if not HAVE_PYCAW:
        _send_volume_key(VK_VOLUME_DOWN, repeat=max(1, step // 5))
        return "Volume decreased."
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        min_vol, max_vol, _ = volume.GetVolumeRange()
        current = volume.GetMasterVolumeLevel()
        new = max(min_vol, current - (max_vol - min_vol) * (step / 100.0))
        volume.SetMasterVolumeLevel(new, None)
        return "Volume decreased."
    except Exception:
        _send_volume_key(VK_VOLUME_DOWN, repeat=max(1, step // 5))
        return "Volume decreased."


def set_brightness(percent: int) -> str:
    percent = max(0, min(100, percent))
    if not HAVE_BRIGHTNESS:
        return "I can't control screen brightness on this device."
    try:
        sbc.set_brightness(percent)
        return f"Brightness set to {percent} percent."
    except Exception:
        return "I couldn't adjust the brightness."


def screenshot(path: str) -> str:
    if not HAVE_PYAUTOGUI:
        return "Screenshot capability is not available."
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = pyautogui.screenshot()
        img.save(path)
        return f"Screenshot saved to {path}"
    except Exception:
        return "I couldn't take a screenshot."


def shutdown_now() -> str:
    try:
        subprocess.Popen(["shutdown", "/s", "/t", "0"])  # Windows
        return "Shutting down."
    except Exception:
        return "I couldn't shut down the computer."


def restart_now() -> str:
    try:
        subprocess.Popen(["shutdown", "/r", "/t", "0"])  # Windows
        return "Restarting now."
    except Exception:
        return "I couldn't restart the computer."


def sleep_now() -> str:
    try:
        # This may require specific power settings and admin privileges
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])  # may hibernate
        return "Entering sleep mode."
    except Exception:
        return "I couldn't put the computer to sleep."


# --- App launching helpers ---

def open_calculator() -> str:
    try:
        # Try direct launch
        subprocess.Popen(["calc.exe"])  # Windows Calculator
        return "Opening Calculator."
    except Exception:
        try:
            # Fallback via start
            subprocess.Popen(["cmd", "/c", "start", "", "calc"], shell=True)
            return "Opening Calculator."
        except Exception:
            return "I couldn't open Calculator."


def open_notepad() -> str:
    try:
        subprocess.Popen(["notepad.exe"])
        return "Opening Notepad."
    except Exception:
        return "I couldn't open Notepad."


def open_paint() -> str:
    try:
        subprocess.Popen(["mspaint.exe"])
        return "Opening Paint."
    except Exception:
        return "I couldn't open Paint."


def open_explorer() -> str:
    try:
        subprocess.Popen(["explorer.exe"])
        return "Opening File Explorer."
    except Exception:
        return "I couldn't open File Explorer."


def open_spotify() -> str:
    # Try protocol, then exe, then web
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "spotify:"], shell=True)
        return "Opening Spotify."
    except Exception:
        pass
    try:
        subprocess.Popen(["spotify.exe"])  # if in PATH
        return "Opening Spotify."
    except Exception:
        try:
            import webbrowser
            webbrowser.open("https://open.spotify.com", new=2)
            return "Opening Spotify on the web."
        except Exception:
            return "I couldn't open Spotify."


def play_music(app: str = "youtube", query: str | None = None) -> str:
    app = (app or "youtube").lower()
    try:
        import webbrowser
        if app == "spotify":
            if query:
                # Try API playback first when configured
                try:
                    from spotify_api import play_query as _spotify_play_query
                except Exception:
                    _spotify_play_query = None  # type: ignore
                if _spotify_play_query is not None:
                    msg = _spotify_play_query(query)
                    # If API not configured, message will indicate and we fall back to UI search
                    if "Playing" in msg or "Opening" in msg or "configured" not in msg:
                        return msg
                # Fallback: deep link or web search
                try:
                    subprocess.Popen(["cmd", "/c", "start", "", f"spotify:search:{query}"], shell=True)
                    return f"Opening {query} on Spotify."
                except Exception:
                    webbrowser.open(f"https://open.spotify.com/search/{query}", new=2)
                    return f"Opening {query} on Spotify."
            # No query: just open app
            return open_spotify()
        # Default to YouTube Music
        if query:
            webbrowser.open(f"https://music.youtube.com/search?q={query}", new=2)
            return f"Searching YouTube Music for {query}."
        webbrowser.open("https://music.youtube.com", new=2)
        return "Opening YouTube Music."
    except Exception:
        return "I couldn't play music."


# --- Media controls (Spotify API if available; otherwise system media keys) ---

def music_pause() -> str:
    # Try Spotify API first
    try:
        from spotify_api import pause_playback as _pause
        msg = _pause()
        # Accept only clear success; otherwise fall back to media key
        if "Paused" in msg:
            return msg
    except Exception:
        pass
    # Fallback: media key
    _send_media_key(VK_MEDIA_PLAY_PAUSE, repeat=1)
    return "Paused playback."


def music_play() -> str:
    try:
        from spotify_api import resume_playback as _resume
        msg = _resume()
        if "Resuming" in msg or "Playing" in msg:
            return msg
    except Exception:
        pass
    _send_media_key(VK_MEDIA_PLAY_PAUSE, repeat=1)
    return "Resuming playback."


def music_next() -> str:
    try:
        from spotify_api import next_track as _next
        msg = _next()
        if "next track" in msg:
            return msg
    except Exception:
        pass
    _send_media_key(VK_MEDIA_NEXT_TRACK, repeat=1)
    return "Skipping to the next track."


def music_previous() -> str:
    try:
        from spotify_api import previous_track as _prev
        msg = _prev()
        if "previous track" in msg:
            return msg
    except Exception:
        pass
    _send_media_key(VK_MEDIA_PREV_TRACK, repeat=1)
    return "Going back to the previous track."


# --- Additional Spotify controls ---

def spotify_shuffle(on: bool) -> str:
    try:
        from spotify_api import set_shuffle as _set_shuffle
        return _set_shuffle(bool(on))
    except Exception:
        return "I couldn't change shuffle on Spotify."


def spotify_repeat(mode: str) -> str:
    try:
        from spotify_api import set_repeat as _set_repeat
        return _set_repeat(mode)
    except Exception:
        return "I couldn't change repeat on Spotify."


def spotify_play_album(query: str) -> str:
    try:
        from spotify_api import play_context_query as _play_ctx
        return _play_ctx(query, "album")
    except Exception:
        return "I couldn't play that album on Spotify."


def spotify_play_playlist(query: str) -> str:
    try:
        from spotify_api import play_context_query as _play_ctx
        return _play_ctx(query, "playlist")
    except Exception:
        return "I couldn't play that playlist on Spotify."


def open_app(name: str) -> str:
    name = (name or "").strip().lower()
    if name in {"calculator", "calc"}:
        return open_calculator()
    if name in {"notepad"}:
        return open_notepad()
    if name in {"paint", "mspaint"}:
        return open_paint()
    if name in {"explorer", "file explorer", "files"}:
        return open_explorer()
    if name in {"spotify"}:
        return open_spotify()
    return f"I don't know how to open {name}."
