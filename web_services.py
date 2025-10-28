"""
External web services: weather, news, definitions, translation, IP, currency, location.
Uses free, no-key providers where possible.
"""
from __future__ import annotations

import requests
from typing import List, Optional
from urllib.parse import quote_plus
import feedparser

from config import NEWS_FEEDS, DEFAULT_CITY


def _ip_city_fallback() -> Optional[str]:
    # Try multiple free providers to get approximate city
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        if r.status_code == 200:
            city = (r.json() or {}).get("city")
            if city:
                return city
    except Exception:
        pass
    try:
        r = requests.get("https://ipapi.co/json/", timeout=5)
        if r.status_code == 200:
            city = (r.json() or {}).get("city")
            if city:
                return city
    except Exception:
        pass
    return None


def weather_report(city: Optional[str] = None) -> str:
    """Return a simple weather summary for the given or detected city using Open-Meteo APIs."""
    try:
        qcity = city or _ip_city_fallback() or DEFAULT_CITY
        g = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": qcity, "count": 1, "language": "en"},
            timeout=8,
        ).json()
        if not g.get("results"):
            return f"I couldn't find location data for {qcity}."
        loc = g["results"][0]
        lat = loc["latitude"]
        lon = loc["longitude"]
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
            },
            timeout=8,
        ).json()
        cw = w.get("current_weather") or {}
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        if temp is None:
            return "I couldn't fetch the weather right now."
        return f"Current weather in {loc['name']}: {temp} degrees Celsius, wind {wind} kilometers per hour."
    except Exception:
        return "I'm having trouble reaching the weather service right now."


def news_briefing(limit: int = 5) -> List[str]:
    """Return top headlines from configured RSS feeds."""
    headlines: List[str] = []
    try:
        for url in NEWS_FEEDS:
            feed = feedparser.parse(url)
            for entry in feed.entries[: limit - len(headlines)]:
                title = getattr(entry, "title", "").strip()
                if title:
                    headlines.append(title)
                if len(headlines) >= limit:
                    break
            if len(headlines) >= limit:
                break
    except Exception:
        pass
    return headlines or ["I wasn't able to retrieve the news at this time."]


def define_word(word: str) -> str:
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote_plus(word)}", timeout=8)
        if r.status_code != 200:
            # Fallback to Wikipedia summary if dictionary misses it
            try:
                import wikipedia
                summary = wikipedia.summary(word, sentences=1, auto_suggest=True, redirect=True)
                return f"{word}: {summary}"
            except Exception:
                return f"I couldn't find a definition for {word}."
        data = r.json()
        meanings = data[0].get("meanings", []) if data else []
        for m in meanings:
            defs = m.get("definitions", [])
            if defs:
                definition = defs[0].get('definition','No definition found')
                example = defs[0].get('example','')
                if example:
                    return f"{word}: {definition}. Example: {example}"
                return f"{word}: {definition}"
        return f"I couldn't find a definition for {word}."
    except Exception:
        return "I'm having trouble reaching the dictionary service."


def translate_text(text: str, target_lang: str) -> str:
    try:
        from deep_translator import GoogleTranslator

        tr = GoogleTranslator(source="auto", target=target_lang)
        return tr.translate(text)
    except Exception:
        return "I'm having trouble translating that right now."


def ip_address() -> str:
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=8).json()
        return r.get("ip") or "Unknown IP"
    except Exception:
        return "Unknown IP"


def currency_convert(amount: float, src: str, dest: str) -> str:
    try:
        r = requests.get(
            "https://api.exchangerate.host/convert",
            params={"from": src.upper(), "to": dest.upper(), "amount": amount},
            timeout=8,
        ).json()
        result = r.get("result")
        if result is None:
            # Fallback to latest rates and compute
            r2 = requests.get(
                "https://api.exchangerate.host/latest",
                params={"base": src.upper()},
                timeout=8,
            ).json()
            rate = (r2.get("rates") or {}).get(dest.upper())
            if rate is None:
                return "I couldn't fetch the currency conversion right now."
            result = float(amount) * float(rate)
        return f"{amount:g} {src.upper()} is approximately {result:.2f} {dest.upper()}."
    except Exception:
        return "I couldn't fetch the currency conversion right now."


def where_am_i() -> str:
    try:
        # Try ipinfo first, then ipapi
        r = requests.get("https://ipinfo.io/json", timeout=6)
        if r.status_code == 200:
            j = r.json()
            city = j.get("city")
            region = j.get("region")
            country = j.get("country")
            if city or region or country:
                parts = [p for p in [city, region, country] if p]
                return ", ".join(parts)
        r2 = requests.get("https://ipapi.co/json/", timeout=6)
        j2 = r2.json() if r2.status_code == 200 else {}
        city = j2.get("city")
        region = j2.get("region")
        country = j2.get("country_name") or j2.get("country")
        if city or region or country:
            parts = [p for p in [city, region, country] if p]
            return ", ".join(parts)
        return "I couldn't determine your location."
    except Exception:
        return "I couldn't determine your location."
