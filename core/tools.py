"""
ARVIS tool definitions and dispatcher.
Schemas are in OpenAI/Ollama format. execute_tool() routes to existing Python functions.
"""
from __future__ import annotations

import fnmatch
import logging
import os
import re
import subprocess
import time
import webbrowser
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

if TYPE_CHECKING:
    from core.memory import Memory

# ---------------------------------------------------------------------------
# Tool schemas — OpenAI/Ollama format
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open an application on the user's Windows computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "App to open, e.g. 'spotify', 'calculator', 'notepad', 'file explorer', 'vs code', 'chrome', 'discord'.",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web or open a site.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "site": {
                        "type": "string",
                        "description": "Target site: google (default), youtube, wikipedia, reddit, github.",
                        "enum": ["google", "youtube", "wikipedia", "reddit", "github"],
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get system info: time, date, cpu, ram, battery, ip, location, or status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "One of: time, date, cpu, ram, battery, ip, location, status.",
                        "enum": ["time", "date", "cpu", "ram", "battery", "ip", "location", "status"],
                    }
                },
                "required": ["info_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the system volume to a specific percentage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level_percent": {"type": "integer", "description": "Volume level 0-100."}
                },
                "required": ["level_percent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": "Set the screen brightness to a specific percentage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level_percent": {"type": "integer", "description": "Brightness level 0-100."}
                },
                "required": ["level_percent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current screen.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name. Omit to use detected location."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get the latest news headlines.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a timed reminder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The reminder text."},
                    "time_description": {
                        "type": "string",
                        "description": "When to remind, e.g. '10 minutes', '1 hour'.",
                    },
                },
                "required": ["text", "time_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files on Desktop, Documents, and Downloads.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "File name or pattern to search for."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify",
            "description": "Play a song, artist, album, or playlist on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to play on Spotify."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Remember a fact about the user for future reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short label, e.g. 'favorite editor'."},
                    "value": {"type": "string", "description": "The value to remember."},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "exit_assistant",
            "description": "Exit or shut down the ARVIS assistant.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_APP_EXECUTABLES: dict[str, str] = {
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "discord": "discord",
    "slack": "slack",
    "task manager": "taskmgr",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "vlc": "vlc",
    "obs": "obs64",
}


def _open_application(app_name: str) -> str:
    from system_control import open_app

    name = (app_name or "").strip().lower()
    exe = _APP_EXECUTABLES.get(name)
    if exe:
        for attempt in ([exe], ["cmd", "/c", "start", "", exe]):
            try:
                subprocess.Popen(attempt, shell=(attempt[0] == "cmd"))
                return f"Opening {app_name}."
            except Exception:
                continue

    result = open_app(name)
    if "don't know" not in result.lower():
        return result

    for attempt in ([name], [name + ".exe"], ["cmd", "/c", "start", "", name]):
        try:
            subprocess.Popen(attempt, shell=(attempt[0] == "cmd"))
            return f"Trying to open {app_name}."
        except Exception:
            continue

    return f"I couldn't find or open {app_name}."


def _search_web(query: str, site: str = "google") -> str:
    site = (site or "google").lower()
    urls = {
        "google": f"https://www.google.com/search?q={quote_plus(query)}",
        "youtube": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
        "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search/{quote_plus(query)}",
        "reddit": f"https://www.reddit.com/search/?q={quote_plus(query)}",
        "github": f"https://github.com/search?q={quote_plus(query)}",
    }
    url = urls.get(site, urls["google"])
    try:
        webbrowser.open(url, new=2)
        return f"Searching {site} for: {query}."
    except Exception:
        return "I couldn't open the browser."


def _get_system_info(info_type: str) -> str:
    import datetime as dt
    import psutil
    from web_services import ip_address, where_am_i

    t = (info_type or "time").lower()
    if t == "time":
        return f"It is {dt.datetime.now().strftime('%I:%M %p')}."
    if t == "date":
        return f"Today is {dt.datetime.now().strftime('%A, %B %d, %Y')}."
    if t == "cpu":
        return f"CPU usage is {psutil.cpu_percent(interval=0.5):.0f} percent."
    if t == "ram":
        vm = psutil.virtual_memory()
        return f"RAM usage is {vm.percent:.0f} percent ({vm.available // (1024**2)} MB free)."
    if t == "battery":
        b = psutil.sensors_battery()
        if not b:
            return "I couldn't detect a battery on this system."
        plugged = "plugged in" if b.power_plugged else "on battery"
        return f"Battery is at {b.percent:.0f} percent and {plugged}."
    if t == "ip":
        return f"Your IP address is {ip_address()}."
    if t == "location":
        return f"You appear to be in {where_am_i()}."
    if t == "status":
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory().percent
        try:
            disk = psutil.disk_usage(os.getenv("SystemDrive", "C:")).percent
        except Exception:
            disk = 0
        return f"CPU {cpu:.0f} percent, memory {mem:.0f} percent, disk {disk:.0f} percent used."
    return "I don't know that info type."


def _parse_time_description(desc: str) -> int:
    desc = (desc or "").strip().lower()
    m = re.match(r"(\d+)\s*(second|seconds|minute|minutes|hour|hours)", desc)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("second"):
            return num
        if unit.startswith("minute"):
            return num * 60
        if unit.startswith("hour"):
            return num * 3600
    return 60


def _create_reminder(text: str, time_description: str) -> str:
    from database import add_reminder
    offset = _parse_time_description(time_description)
    add_reminder(text, int(time.time()) + offset)
    return f"Reminder set: '{text}' in {time_description}."


def _search_files(query: str) -> str:
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
    ]
    matches: list[str] = []
    pattern = f"*{query.lower()}*"
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for f in files:
                if fnmatch.fnmatch(f.lower(), pattern):
                    matches.append(os.path.join(root, f))
                if len(matches) >= 5:
                    break
            if len(matches) >= 5:
                break
        if len(matches) >= 5:
            break
    if not matches:
        return f"No files found matching '{query}'."
    return "Found: " + "; ".join(matches)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def execute_tool(name: str, inputs: dict, memory: "Memory") -> str:
    try:
        if name == "open_application":
            return _open_application(inputs.get("app_name", ""))
        if name == "search_web":
            return _search_web(inputs.get("query", ""), inputs.get("site", "google"))
        if name == "get_system_info":
            return _get_system_info(inputs.get("info_type", "time"))
        if name == "set_volume":
            from system_control import set_volume
            return set_volume(int(inputs.get("level_percent", 50)))
        if name == "set_brightness":
            from system_control import set_brightness
            return set_brightness(int(inputs.get("level_percent", 50)))
        if name == "take_screenshot":
            from system_control import screenshot
            import datetime as dt
            path = os.path.join("screenshots", f"screenshot_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            return screenshot(path)
        if name == "get_weather":
            from web_services import weather_report
            return weather_report(inputs.get("city"))
        if name == "get_news":
            from web_services import news_briefing
            return "Here are the top headlines: " + ". ".join(news_briefing(limit=5))
        if name == "create_reminder":
            return _create_reminder(inputs.get("text", ""), inputs.get("time_description", "1 minute"))
        if name == "search_files":
            return _search_files(inputs.get("query", ""))
        if name == "play_spotify":
            from spotify_api import play_query
            return play_query(inputs.get("query", ""))
        if name == "remember_fact":
            return memory.remember_fact(inputs.get("key", ""), inputs.get("value", ""))
        if name == "exit_assistant":
            return "__EXIT__"
        return f"Unknown tool: {name}"
    except Exception as e:
        logging.error(f"Tool '{name}' error: {e}")
        return f"Error in {name}: {e}"
