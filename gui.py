"""
Neon JARVIS-style GUI for Jarvis status using Tkinter.
Dark theme with cyan/blue neon accents, pulsing mic ring, chat history,
and system tiles for CPU/RAM/Battery.
"""
from __future__ import annotations

try:
    import tkinter as tk
except Exception:  # pragma: no cover - GUI optional
    tk = None  # type: ignore

import math
import psutil
import time


class JarvisGUI:
    def __init__(self) -> None:
        if tk is None:
            raise RuntimeError("Tkinter not available")
        self.root = tk.Tk()
        self.root.title("Jarvis")
        self.root.geometry("900x600")
        self.root.configure(bg="#0b0f1a")
        self.root.minsize(820, 520)

        # Theme colors
        self.bg = "#0b0f1a"
        self.fg = "#d9faff"
        self.accent = "#00d1ff"
        self.accent2 = "#0077ff"
        self.dim = "#7bb8c7"

        # Top bar
        self.top = tk.Frame(self.root, bg=self.bg)
        self.top.pack(fill=tk.X, padx=16, pady=(12, 8))
        self.title_label = tk.Label(
            self.top, text="JARVIS", fg=self.accent, bg=self.bg, font=("Orbitron", 18, "bold")
        )
        self.title_label.pack(side=tk.LEFT)
        self.status_var = tk.StringVar(value="Online")
        self.status_label = tk.Label(
            self.top, textvariable=self.status_var, fg=self.dim, bg=self.bg, font=("Segoe UI", 12)
        )
        self.status_label.pack(side=tk.RIGHT)

        # Main area: left (logo + tiles) and right (chat)
        self.main = tk.Frame(self.root, bg=self.bg)
        self.main.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        self.left = tk.Frame(self.main, bg=self.bg)
        self.left.pack(side=tk.LEFT, fill=tk.Y)

        # Neon J logo canvas with pulsing ring
        self.mic_size = 180
        self.mic_canvas = tk.Canvas(self.left, width=self.mic_size, height=self.mic_size, bg=self.bg, highlightthickness=0)
        self.mic_canvas.pack(pady=8)
        self._mic_phase = 0.0
        self._mic_status = "idle"  # idle | listening | processing
        self._draw_mic()

        # System tiles
        self.tiles = tk.Frame(self.left, bg=self.bg)
        self.tiles.pack(pady=8)
        self.cpu_var = tk.StringVar(value="CPU 0%")
        self.ram_var = tk.StringVar(value="RAM 0%")
        self.bat_var = tk.StringVar(value="Battery --%")
        for var, label in (
            (self.cpu_var, "CPU"),
            (self.ram_var, "RAM"),
            (self.bat_var, "BAT"),
        ):
            f = tk.Frame(self.tiles, bg="#0e1422", highlightbackground=self.accent2, highlightthickness=1)
            f.pack(fill=tk.X, pady=6)
            tk.Label(f, text=label, fg=self.dim, bg="#0e1422", font=("Segoe UI", 10, "bold"), width=6, anchor="w").pack(side=tk.LEFT, padx=8, pady=6)
            tk.Label(f, textvariable=var, fg=self.fg, bg="#0e1422", font=("Consolas", 11), anchor="e").pack(side=tk.RIGHT, padx=8)

        # Chat panel
        self.right = tk.Frame(self.main, bg=self.bg)
        self.right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0))
        self.chat = tk.Text(self.right, bg="#0e1422", fg=self.fg, insertbackground=self.accent, wrap="word", relief="flat")
        self.chat.pack(fill=tk.BOTH, expand=True)
        self.chat.tag_configure("jarvis", foreground=self.accent)
        self.chat.tag_configure("user", foreground="#9cf8ff")
        self.chat.tag_configure("system", foreground=self.dim)
        self.chat.config(state=tk.DISABLED)

        # Footer with input (appears in typing mode)
        self.footer = tk.Frame(self.root, bg=self.bg)
        self.footer.pack(fill=tk.X, pady=(4, 10), padx=12)
        self.input_var = tk.StringVar()
        self.input = tk.Entry(self.footer, textvariable=self.input_var, fg=self.fg, bg="#0e1422", insertbackground=self.accent, relief="flat", font=("Segoe UI", 11))
        self.input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        # Submit via Enter
        self.input.bind("<Return>", lambda e: self._submit_input())
        # Start disabled; enabled when switching to typing mode
        self._typing_enabled = False
        self._set_typing_enabled(False)
        # Callback to main for submitted text
        self._on_submit = None

        # Animations / updates
        self._last_pulse = time.time()
        self._animate()
        self._update_system()

    def set_status(self, text: str) -> None:
        # Update status and mic color/state
        def _set():
            self.status_var.set(text)
            low = (text or "").lower()
            if "listening" in low:
                self._mic_status = "listening"
            elif "processing" in low:
                self._mic_status = "processing"
            elif "waiting" in low:
                self._mic_status = "idle"
        self.root.after(0, _set)

    def add_history(self, text: str) -> None:
        def _add():
            self.chat.config(state=tk.NORMAL)
            tag = "system"
            if text.startswith("Jarvis:"):
                tag = "jarvis"
            elif text.startswith("You said:"):
                tag = "user"
            self.chat.insert(tk.END, text + "\n", tag)
            self.chat.see(tk.END)
            self.chat.config(state=tk.DISABLED)
        self.root.after(0, _add)

    def run(self) -> None:
        self.root.mainloop()

    # --- internals ---
    def _draw_mic(self) -> None:
        c = self.mic_canvas
        c.delete("all")
        w = h = self.mic_size
        cx, cy = w // 2, h // 2
        # base ring sizes
        base_r = 58
        phase = self._mic_phase
        # status color
        col = self.accent if self._mic_status == "listening" else (self.accent2 if self._mic_status == "processing" else "#0f6b84")
        # pulse radius and thickness
        pulse = 6 * (1 + math.sin(phase))
        r1 = base_r + pulse
        r2 = base_r - 8
        # Outer glow (multiple rings)
        for i in range(6):
            rr = r1 + i * 3
            color = col
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=color, width=2)
        # Inner ring
        c.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, outline=col, width=3)
        # Neon single 'J' logo (no outline strokes)
        c.create_text(cx, cy - 4, text="J", fill=self.accent, font=("Orbitron", 46, "bold"))

    def _animate(self) -> None:
        self._mic_phase += 0.18 if self._mic_status != "idle" else 0.08
        self._draw_mic()
        self.root.after(50, self._animate)

    def _update_system(self) -> None:
        try:
            self.cpu_var.set(f"CPU {psutil.cpu_percent(interval=None):.0f}%")
            self.ram_var.set(f"RAM {psutil.virtual_memory().percent:.0f}%")
            b = psutil.sensors_battery()
            if b is not None:
                self.bat_var.set(f"Battery {b.percent:.0f}%")
            else:
                self.bat_var.set("Battery --%")
        except Exception:
            pass
        self.root.after(1000, self._update_system)

    # Text input helpers for typing mode
    def _submit_input(self) -> None:
        if not self._typing_enabled:
            return
        text = (self.input_var.get() or '').strip()
        if not text:
            return
        self.input_var.set("")
        if callable(self._on_submit):
            try:
                self._on_submit(text)
            except Exception:
                pass

    def set_on_submit(self, callback) -> None:
        self._on_submit = callback

    def _set_typing_enabled(self, enabled: bool) -> None:
        self._typing_enabled = bool(enabled)
        state = tk.NORMAL if self._typing_enabled else tk.DISABLED
        self.input.configure(state=state)
        if self._typing_enabled:
            self.input.focus_set()

    def set_typing_enabled(self, enabled: bool) -> None:
        self.root.after(0, self._set_typing_enabled, bool(enabled))
