"""Persistent settings in ~/.config/caselight/config.json."""

import json
import os
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "caselight" / "config.json"

DEFAULTS = {
    # LEDs on each ARGB header, keyed by header number ("1", "2", ...).
    # The controller can't detect this; set it to match your fans/strips.
    "argb_leds": {},
    # Last applied lighting, restored by `caselight restore` and the web UI.
    "last": {"kind": "hardware", "mode": "static", "color": "#ff0000", "zones": ["all"],
             "speed": 1.0, "brightness": 1.0},
}


def load() -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text()))
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(CONFIG_PATH)


def argb_leds(cfg: dict) -> dict[int, int]:
    return {int(k): int(v) for k, v in cfg.get("argb_leds", {}).items()}


def parse_color(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError(f"Invalid color '{value}', use e.g. ff0000 or #f00")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
