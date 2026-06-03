from __future__ import annotations

from collections.abc import Callable
import queue
import tkinter as tk

from .state import LightState


COLORS = {
    LightState.THINKING: "#20d66b",
    LightState.RUNNING: "#f2c94c",
    LightState.DONE: "#eb5757",
    LightState.ERROR: "#eb5757",
}

TRANSPARENT_COLOR = "#010101"


class StatusIsland:
    def __init__(self, on_close: Callable[[], None]) -> None:
        self.root = tk.Tk()
        self.on_close = on_close
        self.state_queue: queue.Queue[LightState] = queue.Queue()
        self.current_state = LightState.THINKING

        self.light_size = 18
        self.width = self.light_size + 6
        self.height = self.light_size + 6

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self._draw()
        self._position()

    def post_state(self, state: LightState) -> None:
        self.state_queue.put(state)

    def run(self, tick: Callable[[], None] | None = None) -> None:
        self._poll(tick)
        self.root.mainloop()

    def close(self) -> None:
        self.on_close()
        self.root.destroy()

    def _poll(self, tick: Callable[[], None] | None) -> None:
        if tick is not None:
            tick()
        while True:
            try:
                self.current_state = self.state_queue.get_nowait()
            except queue.Empty:
                break
        self._draw()
        self.root.after(150, self._poll, tick)

    def _position(self) -> None:
        screen_width = self.root.winfo_screenwidth()
        x = max(0, (screen_width - self.width) // 2)
        y = 0
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def _draw(self) -> None:
        self.canvas.delete("all")
        cy = self.height // 2
        r = self.light_size // 2
        cx = self.width // 2
        current_state = LightState.DONE if self.current_state == LightState.ERROR else self.current_state

        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=COLORS[current_state], outline="")
        self.canvas.create_oval(cx - r + 3, cy - r + 3, cx - r + 7, cy - r + 7, fill="#ffffff", outline="")
