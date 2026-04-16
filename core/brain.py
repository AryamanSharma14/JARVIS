"""
ARVIS brain: Ollama-powered command processing with tool use.
Falls back to the legacy regex brain if Ollama is unreachable.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

import requests

from core.memory import Memory
from core.tools import TOOL_SCHEMAS, execute_tool

SYSTEM_PROMPT = (
    "You are ARVIS (Artificial Responsive Virtual Intelligence System), "
    "a voice assistant running on Windows. "
    "Be concise — your responses are spoken aloud, so keep them short and natural. "
    "Use tools to take action whenever appropriate. "
    "Address the user as 'sir' by default. "
    "If the user asks you to remember something, use the remember_fact tool. "
    "Never use markdown formatting; plain text only."
)


class ARVISBrain:
    def __init__(self, model: str, host: str, memory: Memory) -> None:
        self._model = model
        self._base_url = host.rstrip("/")
        self._memory = memory
        self._fallback_mem = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, text: str, speak: Callable[[str], None]) -> bool:
        """Process a user command. Returns True if ARVIS should exit."""
        from config import LLM_ENABLED
        if not LLM_ENABLED:
            return self._fallback(text, speak)
        try:
            return self._llm_process(text, speak)
        except requests.exceptions.ConnectionError:
            logging.error("ARVIS: Ollama not reachable — falling back to regex brain.")
            speak(f"Ollama is not running. Start it with: ollama serve, then ollama pull {self._model}")
            return self._fallback(text, speak)
        except Exception as e:
            logging.warning(f"ARVIS LLM error ({type(e).__name__}: {e}) — falling back.")
            return self._fallback(text, speak)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_process(self, text: str, speak: Callable[[str], None]) -> bool:
        messages = (
            [{"role": "system", "content": self._build_system_prompt()}]
            + self._memory.get_context()
            + [{"role": "user", "content": text}]
        )

        exit_flag = False

        # Tool-use loop (cap at 5 iterations to prevent runaway)
        for _ in range(5):
            resp = requests.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "tools": TOOL_SCHEMAS,
                    "stream": False,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            msg = choice["message"]

            # Add assistant turn to local message list
            messages.append(msg)

            # No tool calls — we're done
            if choice.get("finish_reason") != "tool_calls" or not msg.get("tool_calls"):
                break

            # Execute each tool and append results
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", {})
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                result = execute_tool(name, args, self._memory)
                if result == "__EXIT__":
                    exit_flag = True
                    result = "Goodbye."

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                })

        response_text = (msg.get("content") or "").strip() or "Done."

        speak(response_text)
        self._memory.add_turn("user", text)
        self._memory.add_turn("assistant", response_text)

        return exit_flag or "goodbye" in response_text.lower()

    # ------------------------------------------------------------------
    # Fallback to legacy regex brain
    # ------------------------------------------------------------------

    def _fallback(self, text: str, speak: Callable[[str], None]) -> bool:
        try:
            from jarvis_brain import handle_command, SessionMemory
            if self._fallback_mem is None:
                self._fallback_mem = SessionMemory()
            return handle_command(text, speak, self._fallback_mem)
        except Exception as e:
            logging.error(f"Fallback brain also failed: {e}")
            speak("I'm sorry, I couldn't process that request.")
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        prompt = SYSTEM_PROMPT
        facts = self._memory.get_facts()
        if facts:
            facts_lines = "\n".join(f"  - {k}: {v}" for k, v in facts.items())
            prompt += f"\n\nFacts you have remembered about the user:\n{facts_lines}"
        return prompt
