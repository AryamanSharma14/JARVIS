"""
Minimal Spotify Web API helper.
Searches tracks and starts playback on user's device when credentials are configured in config.py.
Falls back gracefully if not configured or if no active device is available.
"""
from __future__ import annotations

import time
import json
from typing import Optional, Tuple

import requests

try:
    from config import (
        SPOTIFY_CLIENT_ID,
        SPOTIFY_CLIENT_SECRET,
        SPOTIFY_REFRESH_TOKEN,
        SPOTIFY_REDIRECT_URI,
    )
except Exception:
    # Defaults if config import fails for any reason
    SPOTIFY_CLIENT_ID = ""
    SPOTIFY_CLIENT_SECRET = ""
    SPOTIFY_REFRESH_TOKEN = ""
    SPOTIFY_REDIRECT_URI = "http://localhost:8080/callback"


API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def _have_creds() -> bool:
    return bool(SPOTIFY_CLIENT_ID and SPOTIFY_REFRESH_TOKEN and (SPOTIFY_CLIENT_SECRET))


def refresh_access_token() -> Optional[str]:
    if not _have_creds():
        return None
    try:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": SPOTIFY_REFRESH_TOKEN,
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET,
        }
        resp = requests.post(TOKEN_URL, data=data, timeout=10)
        if resp.status_code != 200:
            return None
        tok = resp.json().get("access_token")
        return tok
    except Exception:
        return None


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def search_track(query: str, token: str) -> Optional[Tuple[str, str]]:
    """Return (track_uri, display_text) for the first matching track, else None."""
    try:
        params = {"q": query, "type": "track", "limit": 1}
        r = requests.get(f"{API}/search", params=params, headers=_auth_headers(token), timeout=10)
        if r.status_code != 200:
            return None
        items = r.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        t = items[0]
        uri = t.get("uri")
        name = t.get("name")
        artists = ", ".join(a.get("name") for a in t.get("artists", []) if a.get("name"))
        display = f"{name} by {artists}" if artists else name
        return uri, display
    except Exception:
        return None


def get_devices(token: str) -> list:
    try:
        r = requests.get(f"{API}/me/player/devices", headers=_auth_headers(token), timeout=10)
        if r.status_code != 200:
            return []
        return r.json().get("devices", []) or []
    except Exception:
        return []


def transfer_playback(token: str, device_id: str, play: bool = False) -> bool:
    try:
        payload = {"device_ids": [device_id], "play": play}
        r = requests.put(f"{API}/me/player", headers=_auth_headers(token), data=json.dumps(payload), timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def start_playback(token: str, device_id: Optional[str], uris: list[str]) -> bool:
    try:
        params = {"device_id": device_id} if device_id else None
        payload = {"uris": uris}
        r = requests.put(f"{API}/me/player/play", params=params, headers=_auth_headers(token), data=json.dumps(payload), timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def play_query(query: str) -> str:
    """
    Try to search for a track and start playback on user's Spotify device.
    Returns a user-facing status string.
    """
    if not _have_creds():
        return (
            "Spotify API isn't configured. Please set SPOTIFY_CLIENT_ID/SECRET/REFRESH_TOKEN in config.py. "
            "I'll open Spotify search instead."
        )
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."

    found = search_track(query, token)
    if not found:
        return "I couldn't find that track on Spotify."
    uri, display = found

    devices = get_devices(token)
    # Prefer active device; else first available device
    device_id = None
    for d in devices:
        if d.get("is_active"):
            device_id = d.get("id")
            break
    if not device_id and devices:
        device_id = devices[0].get("id")

    if not device_id:
        # Try to open Spotify to activate a device, then re-check quickly
        try:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", "spotify:"], shell=True)
        except Exception:
            pass
        time.sleep(2.0)
        devices = get_devices(token)
        if devices:
            device_id = devices[0].get("id")

    if not device_id:
        # Last resort: deep link will open the track, but autoplay depends on client settings
        try:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", uri], shell=True)
            return f"Opening {display} in Spotify."
        except Exception:
            return f"I found {display}, but I couldn't start playback."

    # Ensure playback is transferred to the chosen device, then start
    transfer_playback(token, device_id, play=True)
    ok = start_playback(token, device_id, [uri])
    if ok:
        return f"Playing {display} on Spotify."
    # Try without device_id param
    ok = start_playback(token, None, [uri])
    if ok:
        return f"Playing {display} on Spotify."
    # Fallback
    try:
        import subprocess
        subprocess.Popen(["cmd", "/c", "start", "", uri], shell=True)
        return f"Opening {display} in Spotify."
    except Exception:
        return f"I found {display}, but I couldn't start playback."


# --- Simple playback controls ---

def pause_playback() -> str:
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."
    try:
        r = requests.put(f"{API}/me/player/pause", headers=_auth_headers(token), timeout=10)
        if r.status_code in (204, 202):
            return "Paused playback."
        return "I couldn't pause playback."
    except Exception:
        return "I couldn't pause playback."


def resume_playback() -> str:
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."
    try:
        r = requests.put(f"{API}/me/player/play", headers=_auth_headers(token), timeout=10)
        if r.status_code in (204, 202):
            return "Resuming playback."
        return "I couldn't resume playback."
    except Exception:
        return "I couldn't resume playback."


def next_track() -> str:
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."
    try:
        r = requests.post(f"{API}/me/player/next", headers=_auth_headers(token), timeout=10)
        if r.status_code in (204, 202):
            return "Skipping to the next track."
        return "I couldn't skip to the next track."
    except Exception:
        return "I couldn't skip to the next track."


def previous_track() -> str:
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."
    try:
        r = requests.post(f"{API}/me/player/previous", headers=_auth_headers(token), timeout=10)
        if r.status_code in (204, 202):
            return "Going back to the previous track."
        return "I couldn't go to the previous track."
    except Exception:
        return "I couldn't go to the previous track."
