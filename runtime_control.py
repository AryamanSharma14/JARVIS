"""
Runtime control flags that can be adjusted at runtime by commands.
Main loop consults these to pick audio devices/backends without restart.
"""
from __future__ import annotations

from typing import Optional

# If True, force using sounddevice fallback; if False, use SpeechRecognition Microphone;
# if None, let main decide based on detection.
USE_SOUNDDEVICE: Optional[bool] = None

# SpeechRecognition microphone device index override (None for default)
SR_MIC_DEVICE_INDEX: Optional[int] = None

# sounddevice input device index override (None for default)
SD_INPUT_DEVICE_INDEX: Optional[int] = None
# Speech recognition runtime overrides (None = use config defaults)
SR_DYNAMIC_ENERGY_OVERRIDE: Optional[bool] = None
SR_ENERGY_THRESHOLD_OVERRIDE: Optional[int] = None
SR_ADJUST_DURATION_OVERRIDE: Optional[float] = None
SR_PAUSE_THRESHOLD_OVERRIDE: Optional[float] = None
SR_NON_SPEAKING_DURATION_OVERRIDE: Optional[float] = None
SR_PHRASE_TIME_LIMIT_OVERRIDE: Optional[float] = None


def set_use_sounddevice(flag: bool) -> None:
    global USE_SOUNDDEVICE
    USE_SOUNDDEVICE = bool(flag)


def set_sr_mic_index(index: Optional[int]) -> None:
    global SR_MIC_DEVICE_INDEX
    SR_MIC_DEVICE_INDEX = index


def set_sd_input_device_index(index: Optional[int]) -> None:
    global SD_INPUT_DEVICE_INDEX
    SD_INPUT_DEVICE_INDEX = index

# Request switch to text input mode from voice loop
SWITCH_TO_TEXT_MODE: bool = False
SWITCH_TO_VOICE_MODE: bool = False

# Force using PowerShell-based TTS fallback for all speech
FORCE_POWERSHELL_TTS: bool = False


def request_text_mode() -> None:
    global SWITCH_TO_TEXT_MODE
    SWITCH_TO_TEXT_MODE = True


def request_voice_mode() -> None:
    global SWITCH_TO_VOICE_MODE
    SWITCH_TO_VOICE_MODE = True


def set_force_powershell_tts(flag: bool) -> None:
    global FORCE_POWERSHELL_TTS
    FORCE_POWERSHELL_TTS = bool(flag)


# --- SR override setters ---
def set_sr_dynamic_energy(flag: Optional[bool]) -> None:
    global SR_DYNAMIC_ENERGY_OVERRIDE
    SR_DYNAMIC_ENERGY_OVERRIDE = flag


def set_sr_energy_threshold(value: Optional[int]) -> None:
    global SR_ENERGY_THRESHOLD_OVERRIDE
    SR_ENERGY_THRESHOLD_OVERRIDE = value


def set_sr_adjust_duration(value: Optional[float]) -> None:
    global SR_ADJUST_DURATION_OVERRIDE
    SR_ADJUST_DURATION_OVERRIDE = value


def set_sr_pause_threshold(value: Optional[float]) -> None:
    global SR_PAUSE_THRESHOLD_OVERRIDE
    SR_PAUSE_THRESHOLD_OVERRIDE = value


def set_sr_non_speaking_duration(value: Optional[float]) -> None:
    global SR_NON_SPEAKING_DURATION_OVERRIDE
    SR_NON_SPEAKING_DURATION_OVERRIDE = value


def set_sr_phrase_time_limit(value: Optional[float]) -> None:
    global SR_PHRASE_TIME_LIMIT_OVERRIDE
    SR_PHRASE_TIME_LIMIT_OVERRIDE = value
