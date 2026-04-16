"""
Persistent memory for ARVIS: rolling conversation history and user facts.
History is kept in RAM (not persisted); facts are saved to data/memory.json.
"""
from __future__ import annotations

import json
import os
from typing import Any

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(_HERE, "data", "memory.json")


class Memory:
    MAX_HISTORY = 20  # message turns kept for Claude context

    def __init__(self) -> None:
        self._history: list[dict] = []
        self._facts: dict[str, Any] = {}
        self.load()

    # --- conversation history ---

    def add_turn(self, role: str, text: str) -> None:
        self._history.append({"role": role, "content": text})
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

    def get_context(self) -> list[dict]:
        return list(self._history)

    # --- persistent facts ---

    def remember_fact(self, key: str, value: str) -> str:
        self._facts[key] = value
        self.save()
        return f"Got it, sir. I'll remember that {key} is {value}."

    def recall_fact(self, key: str) -> str | None:
        return self._facts.get(key)

    def get_facts(self) -> dict[str, Any]:
        return dict(self._facts)

    # --- persistence ---

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump({"facts": self._facts}, f, indent=2)
        except Exception:
            pass

    def load(self) -> None:
        try:
            if os.path.exists(DATA_PATH):
                with open(DATA_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._facts = data.get("facts", {})
        except Exception:
            pass
