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

from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REFRESH_TOKEN,
)


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
        params = {"q": query, "type": "track", "limit": 5}
        r = requests.get(f"{API}/search", params=params, headers=_auth_headers(token), timeout=10)
        if r.status_code != 200:
            return None
        items = r.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        # Try to extract artist and title from query for better matching
        query_lower = query.lower()
        best = None
        for t in items:
            name = (t.get("name") or "").lower()
            artists_list = [a.get("name", "").lower() for a in t.get("artists", [])]
            uri = t.get("uri")
            display = f"{t.get('name')} by {', '.join(a.title() for a in artists_list)}"
            # Exact match on both title and artist in query
            if name in query_lower and any(artist in query_lower for artist in artists_list):
                return uri, display
            # Exact match on title
            if name in query_lower:
                best = (uri, display)
        # Fallback: return first result
        if best:
            return best
        t = items[0]
        uri = t.get("uri")
        name = t.get("name")
        artists = ", ".join(a.get("name") for a in t.get("artists", []) if a.get("name"))
        display = f"{name} by {artists}" if artists else name
        return uri, display
    except Exception:
        return None


def search_context(query: str, type_: str, token: str) -> Optional[Tuple[str, str]]:
    """Search for a context (album/playlist/artist) and return (context_uri, display)."""
    try:
        type_ = type_.lower()
        if type_ not in {"album", "playlist", "artist"}:
            return None
        params = {"q": query, "type": type_, "limit": 1}
        r = requests.get(f"{API}/search", params=params, headers=_auth_headers(token), timeout=10)
        if r.status_code != 200:
            return None
        key = f"{type_}s"
        items = r.json().get(key, {}).get("items", [])
        if not items:
            return None
        t = items[0]
        uri = t.get("uri")
        name = t.get("name") or query
        owner = ""
        if type_ == "playlist":
            owner = (t.get("owner", {}) or {}).get("display_name") or ""
        display = f"{name} {('by ' + owner) if owner else ''}".strip()
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


def start_playback_context(token: str, device_id: Optional[str], context_uri: str) -> bool:
    try:
        params = {"device_id": device_id} if device_id else None
        payload = {"context_uri": context_uri}
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


def play_context_query(query: str, type_: str) -> str:
    """Search for a playlist/album/artist and start playback of that context."""
    if not _have_creds():
        return (
            "Spotify API isn't configured. Please set SPOTIFY_CLIENT_ID/SECRET/REFRESH_TOKEN in config.py. "
            "I'll open Spotify search instead."
        )
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."

    found = search_context(query, type_, token)
    if not found:
        return f"I couldn't find that {type_} on Spotify."
    context_uri, display = found

    devices = get_devices(token)
    device_id = None
    for d in devices:
        if d.get("is_active"):
            device_id = d.get("id")
            break
    if not device_id and devices:
        device_id = devices[0].get("id")

    if not device_id:
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
        # Deep link open; autoplay depends on client settings
        try:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "", context_uri], shell=True)
            return f"Opening {display} in Spotify."
        except Exception:
            return f"I found {display}, but I couldn't start playback."

    if start_playback_context(token, device_id, context_uri) or start_playback_context(token, None, context_uri):
        return f"Playing {display} on Spotify."
    try:
        import subprocess
        subprocess.Popen(["cmd", "/c", "start", "", context_uri], shell=True)
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


def set_shuffle(on: bool) -> str:
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."
    try:
        params = {"state": str(bool(on)).lower()}
        r = requests.put(f"{API}/me/player/shuffle", params=params, headers=_auth_headers(token), timeout=10)
        if r.status_code in (204, 202):
            return "Shuffle turned on." if on else "Shuffle turned off."
        return "I couldn't change shuffle on Spotify."
    except Exception:
        return "I couldn't change shuffle on Spotify."


def set_repeat(mode: str) -> str:
    token = refresh_access_token()
    if not token:
        return "I couldn't authenticate with Spotify."
    mode = mode.lower()
    norm = {"one": "track", "track": "track", "all": "context", "context": "context", "off": "off"}
    state = norm.get(mode)
    if not state:
        return "Please say repeat one, repeat all, or repeat off."
    try:
        params = {"state": state}
        r = requests.put(f"{API}/me/player/repeat", params=params, headers=_auth_headers(token), timeout=10)
        if r.status_code in (204, 202):
            if state == "track":
                return "Repeat one is on."
            if state == "context":
                return "Repeat all is on."
            return "Repeat is off."
        return "I couldn't change repeat on Spotify."
    except Exception:
        return "I couldn't change repeat on Spotify."
