"""
Configuration for Jarvis assistant.
Edit values as desired.
"""

ASSISTANT_NAME = "Jarvis"
USER_NAME = "sir"  # How Jarvis should address you

# Wake words Jarvis will respond to
WAKE_WORDS = [
    f"hey {ASSISTANT_NAME.lower()}",
    f"hi {ASSISTANT_NAME.lower()}",
    f"ok {ASSISTANT_NAME.lower()}",
    f"okay {ASSISTANT_NAME.lower()}",
]

# Behavior toggles
GUI_ENABLED = True

# Web services configuration
WEATHER_PROVIDER = "open-meteo"  # fixed
DEFAULT_CITY = "London"
NEWS_FEEDS = [
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "https://feeds.bbci.co.uk/news/rss.xml",
]

# Paths
DB_PATH = "jarvis.db"
LOG_PATH = "logs/jarvis.log"
SCREENSHOT_DIR = "screenshots"

# Audio/input preferences
# If you know the mic name/substring (from sr.Microphone.list_microphone_names()), set it here to prefer it.
PREFERRED_MIC_SUBSTRING: str | None = None  # e.g., "Microphone (Realtek)"

# For sounddevice fallback, you can force an input device index (see sd.query_devices()).
SD_INPUT_DEVICE: int | None = None

# Speech/TTS preferences
# Engine rate (words-per-minute-ish) and volume (0.0 - 1.0)
TTS_RATE: int = 185
TTS_VOLUME: float = 1.0
TTS_VOICE_NAME: str | None = None  # e.g., 'Zira', 'David', or leave None for default

# Speech recognition tuning (to help in noisy rooms)
# Set DYNAMIC to True for auto-calibration, or False to use a fixed ENERGY_THRESHOLD
SR_DYNAMIC_ENERGY: bool = True
SR_ENERGY_THRESHOLD: int = 300  # used only if SR_DYNAMIC_ENERGY is False
SR_PAUSE_THRESHOLD: float = 1.0  # seconds of silence to consider phrase complete
SR_NON_SPEAKING_DURATION: float = 0.5
SR_ADJUST_DURATION: float = 0.8  # seconds to listen to ambient noise before capture
SR_PHRASE_TIME_LIMIT: float = 12.0  # default phrase time limit for listening
SR_MAX_TIMEOUTS_BEFORE_TEXT: int = 6  # auto-switch to typing after this many consecutive timeouts

# Idle prompt: how often Jarvis should say a waiting prompt when idle (seconds); set 0 to disable
IDLE_PROMPT_SECONDS: int = 15

# Spotify API (optional)
# To enable direct Spotify playback, create an app at https://developer.spotify.com/
# and set these values. You must obtain a refresh token once via the Authorization Code flow.
# If left blank, the assistant will fall back to opening Spotify/web search.
SPOTIFY_CLIENT_ID: str = "5d97ebf3cca440e4b250ea511bf3b096"
SPOTIFY_CLIENT_SECRET: str = "ca493cb086114276b4261fa5c202abb4"
SPOTIFY_REFRESH_TOKEN: str = "AQDqKAAb-pK0xRX13KAfBuHEOV_EGAX3frFix_NNUHArtiS895WdR5OhXm31eSkqFFRhBTHQMQQjBseM7HHR4XFBj_4P5Z-OZBo7Z_lnIuY6Pn98Kxv4vd-RCEd99W0rgpI"
SPOTIFY_REDIRECT_URI: str = "https://developer.spotify.com/callback"
