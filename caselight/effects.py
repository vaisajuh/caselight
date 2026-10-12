"""Software effects rendered on the PC and streamed to the controller in direct mode.

Unlike the built-in hardware modes, these give per-LED control (true rainbow waves,
comets, etc.) but need caselight to keep running.
"""

import colorsys
import math
import threading
import time

from .aura import AuraController, Zone

FPS = 30


def _hsv(h: float, s: float = 1.0, v: float = 1.0) -> tuple[float, float, float]:
    return colorsys.hsv_to_rgb(h % 1.0, s, v)


def static(t, i, n, color, speed):
    return color


def breathing(t, i, n, color, speed):
    k = (1 - math.cos(t * speed * math.pi)) / 2
    return tuple(c * k for c in color)


def color_cycle(t, i, n, color, speed):
    return _hsv(t * speed * 0.1)


def rainbow_wave(t, i, n, color, speed):
    return _hsv(t * speed * 0.2 + i / max(n, 1))


def comet(t, i, n, color, speed):
    head = (t * speed * n * 0.5) % max(n, 1)
    dist = (head - i) % max(n, 1)
    k = max(0.0, 1 - dist / max(n * 0.3, 1))
    return tuple(c * k * k for c in color)


def candle(t, i, n, color, speed):
    flicker = 0.75 + 0.25 * math.sin(t * speed * 7 + i * 1.7) * math.sin(t * speed * 3.1 + i)
    return tuple(c * flicker for c in color)


EFFECTS = {
    "static": static,
    "breathing": breathing,
    "color-cycle": color_cycle,
    "rainbow-wave": rainbow_wave,
    "comet": comet,
    "candle": candle,
}


def render(name, t, n, color, speed, brightness) -> list[tuple[int, int, int]]:
    fn = EFFECTS[name]
    base = tuple(c / 255 for c in color)
    frame = []
    for i in range(n):
        r, g, b = fn(t, i, n, base, speed)
        frame.append(tuple(max(0, min(255, round(c * brightness * 255))) for c in (r, g, b)))
    return frame


class EffectRunner:
    """Animates a software effect on a background thread."""

    def __init__(self, ctrl: AuraController):
        self.ctrl = ctrl
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, name: str, zones: list[Zone], color, speed=1.0, brightness=1.0):
        self.stop()
        zones = [z for z in zones if z.led_count > 0]
        with self.lock:
            self.ctrl.enter_direct(zones)
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(name, zones, color, speed, brightness), daemon=True
        )
        self._thread.start()

    def stop(self):
        if self._thread:
            self._stop.set()
            self._thread.join()
            self._thread = None

    def _loop(self, name, zones, color, speed, brightness):
        t0 = time.monotonic()
        while not self._stop.is_set():
            t = time.monotonic() - t0
            with self.lock:
                for z in zones:
                    self.ctrl.send_direct(z, render(name, t, z.led_count, color, speed, brightness))
            self._stop.wait(1 / FPS)
