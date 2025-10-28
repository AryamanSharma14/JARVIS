"""
Jarvis brain: command parsing, conversational behavior, and action routing.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from typing import Callable, List, Tuple
import difflib
import webbrowser
from urllib.parse import quote_plus
import wikipedia
from wikipedia import exceptions as wiki_exc

import psutil

from config import ASSISTANT_NAME, USER_NAME
from database import add_reminder, add_note
from web_services import (
    weather_report,
    news_briefing,
    define_word,
    translate_text,
    ip_address,
    currency_convert,
    where_am_i,
)
from system_control import (
    set_volume,
    volume_up,
    volume_down,
    set_brightness,
    screenshot,
    sleep_now,
    open_app,
    play_music,
    music_pause,
    music_play,
    music_next,
    music_previous,
)
import runtime_control as rt
import speech_recognition as sr
try:
    import sounddevice as sd
except Exception:
    sd = None  # type: ignore


class SessionMemory:
    def __init__(self) -> None:
        self.last_topics: List[str] = []

    def remember(self, topic: str) -> None:
        if topic:
            self.last_topics.append(topic)
            self.last_topics = self.last_topics[-20:]

    def recall_recent(self) -> str:
        return ", ".join(self.last_topics[-3:]) if self.last_topics else ""


def greeting() -> str:
    now = dt.datetime.now().hour
    if now < 12:
        return f"Good morning, {USER_NAME}."
    elif now < 18:
        return f"Good afternoon, {USER_NAME}."
    else:
        return f"Good evening, {USER_NAME}."


def polite_ack() -> str:
    return "Right away, {name}.".format(name=USER_NAME)


def system_status() -> str:
    try:
        cpu = psutil.cpu_percent(interval=0.7)
        mem = psutil.virtual_memory().percent
        disks = psutil.disk_usage(os.getenv("SystemDrive", "C:"))
        return f"CPU {cpu:.0f} percent, memory {mem:.0f} percent, disk {disks.percent:.0f} percent used."
    except Exception:
        return "I couldn't retrieve system status."


def battery_status() -> str:
    try:
        b = psutil.sensors_battery()
        if not b:
            return "I couldn't detect a battery on this system."
        plugged = "plugged in" if b.power_plugged else "on battery"
        return f"Battery at {b.percent:.0f} percent and {plugged}."
    except Exception:
        return "I couldn't retrieve battery status."


def check_internet() -> str:
    import socket

    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return "Internet connection appears to be working."
    except Exception:
        return "I cannot reach the internet right now."


def parse_time_string(s: str) -> Tuple[int, str]:
    """Parse '10 minutes', '1 hour', 'at 5 pm' basic forms. Returns seconds and normalized desc."""
    s = s.strip().lower()
    m = re.match(r"(\d+)\s*(second|seconds|minute|minutes|hour|hours)", s)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        mult = 1
        if unit.startswith("second"):
            mult = 1
        elif unit.startswith("minute"):
            mult = 60
        elif unit.startswith("hour"):
            mult = 3600
        return num * mult, f"{num} {unit}"
    return 0, s


def _normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("×", "*").replace("÷", "/")
    s = re.sub(r"\s+", " ", s)
    return s


def handle_command(text: str, speak: Callable[[str], None], mem: SessionMemory) -> bool:
    """Route a parsed command. Return True if should exit."""
    c = _normalize_text(text)
    # Translation FIRST so 'translate hello how are you to japanese' isn't hijacked by small talk
    m = re.search(r"^\s*translate\s+(.+?)\s+to\s+([a-zA-Z-]+)\s*$", c)
    if m:
        phrase = m.group(1).strip()
        lang = m.group(2).strip()
        speak("On it.")
        speak(translate_text(phrase, lang))
        return False
    # Google search (support 'search google for ...' and natural phrasing)
    m = re.search(r"^(?:search\s+)?google\s+(?:for\s+)?(.+)$", c)
    if m:
        query = m.group(1).strip()
        url = "https://www.google.com/search?q=" + quote_plus(query)
        speak(polite_ack())
        try:
            webbrowser.open(url, new=2)
            speak(f"Searching Google for {query}.")
        except Exception:
            speak("I couldn't open Google search.")
        mem.remember(f"google:{query}")
        return False

    # Wikipedia search
    m = re.search(r"(?:search\s+)?wikipedia\s+(?:for\s+)?(.+)$", c)
    if m:
        topic = m.group(1).strip()
        speak(polite_ack())
        try:
            summary = wikipedia.summary(topic, sentences=2, auto_suggest=True, redirect=True)
            speak(summary)
        except wiki_exc.DisambiguationError as e:
            option = e.options[0] if e.options else None
            if option:
                try:
                    summary = wikipedia.summary(option, sentences=2, auto_suggest=True)
                    speak(summary)
                except Exception:
                    speak("That topic is ambiguous. Please be more specific.")
            else:
                speak("That topic is ambiguous. Please be more specific.")
        except wiki_exc.PageError:
            speak("I couldn't find a Wikipedia page for that topic.")
        except Exception:
            speak("I had trouble reaching Wikipedia.")
        mem.remember(f"wikipedia:{topic}")
        return False

    # Open known sites and generic open

    # Windows apps first to avoid catching by generic open->[.com]
    if "open calculator" in c or c == "calculator":
        speak(polite_ack())
        speak(open_app("calculator"))
        return False
    if "open notepad" in c or c == "notepad":
        speak(polite_ack())
        speak(open_app("notepad"))
        return False
    if "open paint" in c or c == "paint":
        speak(polite_ack())
        speak(open_app("paint"))
        return False
    if "open file explorer" in c or "open explorer" in c:
        speak(polite_ack())
        speak(open_app("explorer"))
        return False

    # Music and Spotify controls before generic open
    if "open spotify" in c:
        speak(polite_ack())
        speak(open_app("spotify"))
        return False
    m = re.search(r"(?:play|open)\s+(.+?)\s+on\s+spotify$", c)
    if m:
        song = m.group(1).strip()
        speak(polite_ack())
        speak(play_music(app="spotify", query=song))
        return False
    if "play music" in c or "open music" in c:
        speak(polite_ack())
        speak(play_music(app="youtube"))
        return False

    def _resolve_site(name: str, mapping: dict) -> str:
        key = name.lower().strip()
        if key in mapping:
            return mapping[key]
        # fuzzy match to correct common typos like 'goole' -> 'google'
        candidates = difflib.get_close_matches(key, list(mapping.keys()), n=1, cutoff=0.75)
        if candidates:
            return mapping[candidates[0]]
        return ""

    m = re.search(r"open\s+([a-z0-9 ._-]+?)(?:\s+and\s+search\s+(?:for\s+)?(.+))?$", c)
    if m:
        name = m.group(1).strip()
        search_q = (m.group(2) or "").strip()
        mapping = {
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
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "classroom": "https://classroom.google.com",
            "google classroom": "https://classroom.google.com",
            "linkedin": "https://www.linkedin.com",
        }
        # If search specified, craft site search URL
        if search_q:
            site_url = None
            site_key = name.lower()
            if site_key in {"youtube"}:
                site_url = f"https://www.youtube.com/results?search_query={quote_plus(search_q)}"
            elif site_key in {"google"}:
                site_url = f"https://www.google.com/search?q={quote_plus(search_q)}"
            elif site_key in {"linkedin"}:
                site_url = f"https://www.linkedin.com/search/results/all/?keywords={quote_plus(search_q)}"
            elif site_key in {"twitter", "x"}:
                site_url = f"https://twitter.com/search?q={quote_plus(search_q)}"
            elif site_key in {"reddit"}:
                site_url = f"https://www.reddit.com/search/?q={quote_plus(search_q)}"
            elif site_key in {"spotify"}:
                # Prefer direct playback when possible
                try:
                    from spotify_api import play_query as _sp_play_query
                    msg = _sp_play_query(search_q)
                    speak(msg)
                    return False
                except Exception:
                    site_url = f"https://open.spotify.com/search/{quote_plus(search_q)}"
            elif site_key in {"facebook"}:
                site_url = f"https://www.facebook.com/search/top/?q={quote_plus(search_q)}"
            elif site_key in {"instagram"}:
                site_url = f"https://www.instagram.com/explore/tags/{quote_plus(search_q)}/"
            if site_url:
                speak(polite_ack())
                try:
                    webbrowser.open(site_url, new=2)
                    speak(f"Searching {name} for {search_q}.")
                except Exception:
                    speak(f"I couldn't search {name}.")
                return False
        # Otherwise resolve to site home
        resolved = _resolve_site(name, mapping)
        url = resolved or f"https://{name.replace(' ', '')}.com"
        speak(polite_ack())
        try:
            webbrowser.open(url, new=2)
            speak(f"Opening {name}.")
        except Exception:
            speak(f"I couldn't open {name}.")
        return False

    # Direct search commands, e.g., "search linkedin for aryaman"
    m = re.search(r"(?:search|find|look up)\s+([a-z]+)\s+(?:for\s+|about\s+)?(.+)$", c)
    if m:
        site, query = m.group(1).strip(), m.group(2).strip()
        site_key = site.lower()
        site_url = None
        if site_key in {"youtube"}:
            site_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        elif site_key in {"google"}:
            site_url = f"https://www.google.com/search?q={quote_plus(query)}"
        elif site_key in {"linkedin"}:
            site_url = f"https://www.linkedin.com/search/results/all/?keywords={quote_plus(query)}"
        elif site_key in {"twitter", "x"}:
            site_url = f"https://twitter.com/search?q={quote_plus(query)}"
        elif site_key in {"reddit"}:
            site_url = f"https://www.reddit.com/search/?q={quote_plus(query)}"
        elif site_key in {"spotify"}:
            try:
                from spotify_api import play_query as _sp_play_query
                msg = _sp_play_query(query)
                speak(msg)
                return False
            except Exception:
                site_url = f"https://open.spotify.com/search/{quote_plus(query)}"
        elif site_key in {"facebook"}:
            site_url = f"https://www.facebook.com/search/top/?q={quote_plus(query)}"
        elif site_key in {"instagram"}:
            site_url = f"https://www.instagram.com/explore/tags/{quote_plus(query)}/"
        if site_url:
            speak(polite_ack())
            try:
                webbrowser.open(site_url, new=2)
                speak(f"Searching {site} for {query}.")
            except Exception:
                speak(f"I couldn't search {site}.")
        else:
            speak(f"Sorry, I can't search {site} directly.")
        return False

    # Open basic Windows apps
    if "open calculator" in c or c == "calculator":
        speak(polite_ack())
        speak(open_app("calculator"))
        return False
    if "open notepad" in c or c == "notepad":
        speak(polite_ack())
        speak(open_app("notepad"))
        return False
    if "open paint" in c or c == "paint":
        speak(polite_ack())
        speak(open_app("paint"))
        return False

    # Music
    if "play music" in c or "open music" in c:
        speak(polite_ack())
        speak(play_music())
        return False

    # Spotify playback controls (generic phrasing)
    if any(p in c for p in ["pause", "pause music", "pause song", "pause spotify"]):
        speak(polite_ack())
        speak(music_pause())
        return False
    if any(p in c for p in ["resume", "play", "continue", "start playback"]):
        # Avoid catching 'play X on spotify' which is handled above
        if not re.search(r"play\s+.+\s+on\s+spotify", c):
            speak(polite_ack())
            speak(music_play())
            return False
    if any(p in c for p in ["next", "skip", "next song", "skip track"]):
        speak(polite_ack())
        speak(music_next())
        return False
    if any(p in c for p in ["previous", "back", "previous song", "go back"]):
        speak(polite_ack())
        speak(music_previous())
        return False


    # Exit
    if any(p in c for p in ["exit", "quit", "goodbye", "good bye"]):
        speak("Goodbye.")
        return True

    # Reminders, timers, notes SHOULD PRECEDE generic 'time' matches
    # (Timer handler is below; ensure 'time' queries don't catch 'timer')

    # Time/Date
    if re.search(r"\b(what(?:'s| is) the time|what time is it|tell me the time)\b", c) or c.strip() == "time":
        now = dt.datetime.now().strftime("%I:%M %p").lstrip("0")
        speak(f"The time is {now}.")
        return False
    if any(p in c for p in ["what is the date", "today's date", "todays date", "date"]):
        today = dt.datetime.now().strftime("%A, %B %d, %Y")
        speak(f"Today is {today}.")
        return False

    # System monitoring
    if "battery status" in c:
        speak(polite_ack())
        speak(battery_status())
        return False
    if "system status" in c:
        speak(polite_ack())
        speak(system_status())
        return False
    if "check internet" in c or "internet connection" in c:
        speak(polite_ack())
        speak(check_internet())
        return False

    # Weather/News
    m = re.search(r"weather(?:\s+in\s+(.+))?", c)
    if m:
        raw_city = m.group(1).strip() if m.group(1) else None
        speak(polite_ack())
        if raw_city:
            speak(weather_report(raw_city))
            mem.remember(f"weather:{raw_city}")
        else:
            # Auto-detect via IP
            report = weather_report(None)
            speak(report)
            mem.remember("weather:auto")
        return False
    # Temperature alias -> weather
    mt = re.search(r"(?:what(?:'s| is)\s+the\s+temperature|\btemperature\b|\btemp\b)(?:\s+in\s+(.+))?", c)
    if mt:
        city = mt.group(1).strip() if mt.group(1) else None
        speak(polite_ack())
        speak(weather_report(city))
        mem.remember(f"weather:{city or 'auto'}")
        return False
    if any(p in c for p in ["today's news", "todays news", "news briefing", "news report"]):
        speak(polite_ack())
        headlines = news_briefing(5)
        speak("Here are the top headlines.")
        for h in headlines:
            speak(h)
        mem.remember("news")
        return False

    # Smart control
    m = re.search(r"set volume to\s*(\d+)\s*%?", c)
    if m:
        speak(polite_ack())
        speak(set_volume(int(m.group(1))))
        return False
    if "increase volume" in c or "volume up" in c:
        speak(polite_ack())
        speak(volume_up())
        return False
    if "decrease volume" in c or "volume down" in c:
        speak(polite_ack())
        speak(volume_down())
        return False

    m = re.search(r"set brightness to\s*(\d+)\s*%?", c)
    if m:
        speak(polite_ack())
        speak(set_brightness(int(m.group(1))))
        return False

    if "take a screenshot" in c or "screenshot" in c:
        speak(polite_ack())
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        from config import SCREENSHOT_DIR

        path = os.path.join(SCREENSHOT_DIR, f"screenshot-{ts}.png")
        speak(screenshot(path))
        return False

    if "shut down" in c or "shutdown" in c:
        speak("Are you sure you want to shut down?")
        return False
    if "restart" in c:
        speak("Are you sure you want to restart?")
        return False
    if "sleep mode" in c or c == "sleep":
        speak(polite_ack())
        speak(sleep_now())
        return False

    # Identity/personality BEFORE math parsing to avoid 'what is your name' hitting math
    if any(p in c for p in ["what is your name", "what's your name", "who are you"]):
        hour = dt.datetime.now().hour
        sal = "Good evening" if hour >= 18 else ("Good afternoon" if hour >= 12 else "Good morning")
        speak(f"{sal}. I am {ASSISTANT_NAME}, your personal AI assistant—here to help you, {USER_NAME}.")
        return False

    # Small talk / conversational replies
    if any(p in c for p in ["how are you", "how are you doing", "how's it going", "how is it going"]):
        speak("I'm functioning at peak efficiency and ready to assist. How can I help you?")
        # Gentle follow-up to keep conversation flowing
        speak("Would you like weather, a quick search, or to open an app?")
        return False
    if any(p in c for p in ["thank you", "thanks", "thanks a lot", "appreciate it"]):
        speak("You're welcome. Always happy to help.")
        return False
    if any(p in c for p in ["you're welcome", "you are welcome"]):
        speak("Anytime.")
        return False
    if any(p in c for p in ["who created you", "who made you", "who built you"]):
        speak(f"I was assembled right here to assist you, {USER_NAME}. Consider me your digital right hand.")
        return False
    if any(p in c for p in ["what can you do", "what are your abilities", "help me", "what do you do"]):
        speak("I can search the web and Wikipedia, open apps and websites, control volume and brightness, take screenshots, give weather and news, set timers and reminders, translate, define words, convert currencies, and more. What would you like?")
        speak("You can say, for example: open YouTube and search lo-fi beats, or set timer for ten minutes.")
        return False

    # TTS diagnostics
    if any(p in c for p in ["test tts", "test speech", "speak test"]):
        speak("This is a test of my speech system. If you can hear me clearly, everything is working.")
        return False

    # Sensitivity / noise handling controls
    if any(p in c for p in ["use automatic sensitivity", "use auto sensitivity", "automatic sensitivity", "auto sensitivity"]):
        try:
            rt.set_sr_dynamic_energy(True)
            rt.set_sr_energy_threshold(None)
        except Exception:
            pass
        speak("Okay. I'll automatically adjust to the room noise.")
        return False
    m = re.search(r"use\s+fixed\s+(?:sensitivity|threshold)\s*(\d+)?", c)
    if m:
        val = m.group(1)
        try:
            rt.set_sr_dynamic_energy(False)
            if val:
                rt.set_sr_energy_threshold(int(val))
                speak(f"Understood. Fixed threshold set to {int(val)}.")
            else:
                rt.set_sr_energy_threshold(400)
                speak("Understood. Using a fixed threshold suitable for noisy rooms.")
        except Exception:
            speak("I couldn't change the sensitivity right now.")
        return False
    if any(p in c for p in ["increase sensitivity", "more sensitive"]):
        # Lower threshold by 100 (but not below 50)
        try:
            rt.set_sr_dynamic_energy(False)
            cur = rt.SR_ENERGY_THRESHOLD_OVERRIDE if rt.SR_ENERGY_THRESHOLD_OVERRIDE is not None else 300
            new = max(50, int(cur) - 100)
            rt.set_sr_energy_threshold(new)
            speak(f"Increased sensitivity. Threshold is now {new}.")
        except Exception:
            speak("I couldn't adjust sensitivity.")
        return False
    if any(p in c for p in ["decrease sensitivity", "less sensitive", "reduce sensitivity"]):
        # Raise threshold by 100 (cap reasonable max)
        try:
            rt.set_sr_dynamic_energy(False)
            cur = rt.SR_ENERGY_THRESHOLD_OVERRIDE if rt.SR_ENERGY_THRESHOLD_OVERRIDE is not None else 300
            new = min(1200, int(cur) + 100)
            rt.set_sr_energy_threshold(new)
            speak(f"Decreased sensitivity. Threshold is now {new}.")
        except Exception:
            speak("I couldn't adjust sensitivity.")
        return False

    # Listening duration controls
    if any(p in c for p in ["don't cut me off", "do not cut me off", "give me more time", "longer listening", "extend listening", "listen longer"]):
        try:
            # Increase pause threshold and phrase time limit a bit
            cur_pause = rt.SR_PAUSE_THRESHOLD_OVERRIDE if rt.SR_PAUSE_THRESHOLD_OVERRIDE is not None else None
            new_pause = (cur_pause or 1.0) + 0.3
            rt.set_sr_pause_threshold(new_pause)
            cur_pt = rt.SR_PHRASE_TIME_LIMIT_OVERRIDE if rt.SR_PHRASE_TIME_LIMIT_OVERRIDE is not None else None
            new_pt = min(20.0, (cur_pt or 12.0) + 4.0)
            rt.set_sr_phrase_time_limit(new_pt)
            speak("Okay. I'll give you a bit more time to speak.")
        except Exception:
            speak("I couldn't extend the listening time right now.")
        return False
    if any(p in c for p in ["be faster", "shorter listening", "cut quicker", "listen less"]):
        try:
            cur_pause = rt.SR_PAUSE_THRESHOLD_OVERRIDE if rt.SR_PAUSE_THRESHOLD_OVERRIDE is not None else None
            new_pause = max(0.5, (cur_pause or 1.0) - 0.2)
            rt.set_sr_pause_threshold(new_pause)
            cur_pt = rt.SR_PHRASE_TIME_LIMIT_OVERRIDE if rt.SR_PHRASE_TIME_LIMIT_OVERRIDE is not None else None
            new_pt = max(5.0, (cur_pt or 12.0) - 3.0)
            rt.set_sr_phrase_time_limit(new_pt)
            speak("Okay. I'll be a bit quicker.")
        except Exception:
            speak("I couldn't shorten the listening time right now.")
        return False

    # TTS mode control
    if any(p in c for p in ["use robust speech", "use powershell speech", "force tts fallback", "force speech fallback", "reset speech", "reset tts"]):
        try:
            rt.set_force_powershell_tts(True)
        except Exception:
            pass
        speak("Understood. I'll use a more robust speech system for now.")
        return False
    if any(p in c for p in ["use normal speech", "use default speech", "stop robust speech"]):
        try:
            rt.set_force_powershell_tts(False)
        except Exception:
            pass
        speak("Okay. I'll use the default speech system.")
        return False
    if any(p in c for p in ["tell me a joke", "joke"]):
        import random
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "I told my computer I needed a break, and it said 'No problem—I'll go to sleep.'",
            "There are 10 types of people in the world: those who understand binary and those who don't.",
        ]
        speak(random.choice(jokes))
        return False
    if any(p in c for p in ["can you hear me", "are you listening", "do you hear me"]):
        speak("Loud and clear. Go ahead.")
        return False

    # Math / conversions
    m = re.search(r"calculate\s+(.+)$", c)
    if m:
        expr = m.group(1)
        try:
            # Very basic safe eval
            expr = _normalize_text(expr)
            expr = expr.replace(" x ", " * ").replace("times", "*").replace("into", "*")
            expr = expr.replace("divide by", "/").replace("divided by", "/")
            if re.search(r"[^0-9+\-*/(). ]", expr):
                raise ValueError
            result = eval(expr, {"__builtins__": {}}, {})
            speak(f"The result is {result}.")
        except Exception:
            speak("I'm afraid I can't calculate that.")
        return False

    m = re.search(r"(?:what's|what is|compute|evaluate)\s+(.+)$", c)
    if m:
        expr = m.group(1)
        try:
            # Only treat as math if digits or arithmetic symbols present
            if not re.search(r"[0-9+\-*/x×÷()]", expr):
                raise ValueError
            expr = _normalize_text(expr)
            expr = expr.replace(" x ", " * ").replace("times", "*").replace("into", "*")
            expr = expr.replace("divide by", "/").replace("divided by", "/")
            if re.search(r"[^0-9+\-*/(). ]", expr):
                raise ValueError
            result = eval(expr, {"__builtins__": {}}, {})
            speak(f"The result is {result}.")
        except Exception:
            # Not math; fall through to other handlers
            pass
        else:
            return False

    if re.match(r"^\s*\d+(?:\s*[+\-x*÷/]\s*\d+)+\s*$", c):
        expr = c
        try:
            expr = _normalize_text(expr)
            expr = expr.replace(" x ", " * ").replace("times", "*").replace("into", "*")
            expr = expr.replace("divide by", "/").replace("divided by", "/")
            result = eval(expr, {"__builtins__": {}}, {})
            speak(f"The result is {result}.")
        except Exception:
            speak("I'm afraid I can't calculate that.")
        return False

    m = re.search(r"convert\s+([0-9.]+)\s*([a-zA-Z]{3})\s+to\s+([a-zA-Z]{3})", c)
    if m:
        amt, src, dst = float(m.group(1)), m.group(2), m.group(3)
        speak(polite_ack())
        speak(currency_convert(amt, src, dst))
        return False

    m = re.search(r"convert\s+([0-9.]+)\s*fahrenheit\s+to\s+celsius", c)
    if m:
        f = float(m.group(1))
        celsius = (f - 32) * 5.0 / 9.0
        speak(f"{f:g} Fahrenheit is {celsius:.1f} Celsius.")
        return False
    m = re.search(r"convert\s+([0-9.]+)\s*celsius\s+to\s*fahrenheit", c)
    if m:
        cval = float(m.group(1))
        fval = (cval * 9.0 / 5.0) + 32
        speak(f"{cval:g} Celsius is {fval:.1f} Fahrenheit.")
        return False

    # Definitions, translations, IP, location
    m = re.search(r"define\s+(.+)$", c)
    if m:
        speak(define_word(m.group(1).strip()))
        return False
    # (translate handled earlier)
    if "what's my ip" in c or "whats my ip" in c or "my ip address" in c:
        speak(f"Your IP address is {ip_address()}.")
        return False
    if "where am i" in c or "my location" in c:
        speak(f"You appear to be in {where_am_i()}.")
        return False

    # Reminders, timers, notes
    m = re.search(r"set timer for\s+(.+)$", c)
    if m:
        seconds, desc = parse_time_string(m.group(1))
        if seconds <= 0:
            speak("Please specify a valid duration.")
        else:
            speak(f"Timer set for {desc}.")
            import threading

            def _ding():
                speak(f"Time's up, {USER_NAME}.")

            threading.Timer(seconds, _ding).start()
        return False

    m = re.search(r"remind me to\s+(.+)\s+in\s+(.+)$", c)
    if m:
        task = m.group(1).strip()
        seconds, desc = parse_time_string(m.group(2))
        if seconds <= 0:
            speak("Please specify a valid reminder time.")
        else:
            import time

            when = int(time.time()) + seconds
            add_reminder(task, when)
            speak(f"Reminder set for {desc}.")
        return False

    # Incomplete volume
    if "set volume" in c and not re.search(r"set volume to\s*\d+", c):
        speak("Please tell me a percentage, for example, set volume to 50 percent.")
        return False

    if "take a note" in c or c.startswith("note "):
        content = c.replace("take a note", "").replace("note", "").strip()
        if content:
            add_note(content)
            speak("Noted.")
        else:
            speak("What would you like me to note?")
        return False

    # General
    if any(p in c for p in ["what is your name", "what's your name", "who are you"]):
        speak(f"I am {ASSISTANT_NAME}, at your service, {USER_NAME}.")
        return False

    # Mode switching
    if any(p in c for p in ["switch to typing", "switch to text mode", "go to text mode", "typing mode", "text mode", "stop listening"]):
        speak("Right away. Switching to typing mode.")
        try:
            rt.request_text_mode()
        except Exception:
            pass
        return False

    # Microphone management
    if "list microphones" in c or "list mics" in c:
        try:
            names = sr.Microphone.list_microphone_names()
            if not names:
                speak("I couldn't find any microphones.")
            else:
                preview = ", ".join([f"{i}: {names[i]}" for i in range(min(5, len(names)))])
                speak(f"I found {len(names)} microphones. For example: {preview}.")
        except Exception:
            speak("I couldn't access the microphone list.")
        try:
            if sd is not None:
                devices = sd.query_devices()
                inputs = [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
                if inputs:
                    preview = ", ".join([f"{i}: {n}" for i, n in inputs[:5]])
                    speak(f"I also see {len(inputs)} recording devices for the alternative recorder. For example: {preview}.")
        except Exception:
            pass
        return False

    m = re.search(r"use\s+(?:microphone|mic)\s*(?:number|index)?\s*(\d+)", c)
    if m:
        idx = int(m.group(1))
        rt.set_sr_mic_index(idx)
        rt.set_use_sounddevice(False)
        speak(f"I'll use microphone number {idx}.")
        return False

    m = re.search(r"use\s+(?:recorder|sounddevice)\s*(?:number|index)?\s*(\d+)", c)
    if m:
        idx = int(m.group(1))
        rt.set_sd_input_device_index(idx)
        rt.set_use_sounddevice(True)
        speak(f"I'll use alternative recorder number {idx}.")
        return False

    if "use default microphone" in c or "use normal microphone" in c:
        rt.set_sr_mic_index(None)
        rt.set_use_sounddevice(False)
        speak("I'll use the default microphone.")
        return False

    # Fallback
    speak("I'm afraid I can't do that, but I can try something else.")
    return False
