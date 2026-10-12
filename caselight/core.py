"""Applies a lighting state (hardware mode or software effect) to the controller."""

from . import config
from .aura import MODES, AuraController, AuraError
from .effects import EFFECTS, EffectRunner


def resolve_zones(ctrl: AuraController, names: list[str]):
    if not names or "all" in names:
        return list(ctrl.zones)
    return [ctrl.zone(n) for n in names]


def apply(ctrl: AuraController, runner: EffectRunner, state: dict):
    """state: {kind, mode, color, zones, speed, brightness}"""
    zones = resolve_zones(ctrl, state.get("zones", ["all"]))
    color = config.parse_color(state.get("color", "#ffffff"))
    brightness = float(state.get("brightness", 1.0))
    speed = float(state.get("speed", 1.0))
    mode = state["mode"]

    if state.get("kind") == "software":
        if mode not in EFFECTS:
            raise AuraError(f"Unknown effect '{mode}'. Available: {', '.join(EFFECTS)}")
        runner.start(mode, zones, color, speed, brightness)
    else:
        if mode not in MODES or mode == "direct":
            raise AuraError(f"Unknown mode '{mode}'.")
        runner.stop()
        scaled = tuple(round(c * brightness) for c in color)
        with runner.lock:
            for z in zones:
                ctrl.set_mode(z, mode, scaled)
