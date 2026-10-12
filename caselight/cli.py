import argparse
import sys
import time

from . import config
from .aura import MODES, AuraController, AuraError
from .core import apply
from .effects import EFFECTS, EffectRunner


def _open(args) -> AuraController:
    return AuraController(args.device, config.argb_leds(config.load()))


def cmd_info(args):
    with _open(args) as ctrl:
        print(f"Device:   {ctrl.info.path}")
        print(f"Firmware: {ctrl.info.firmware}")
        print("Zones:")
        for z in ctrl.zones:
            kind = "addressable (ARGB)" if z.addressable else "fixed RGB"
            note = "" if z.led_count or not z.addressable else "  <- set LED count with `caselight leds`"
            print(f"  {z.name:<10} {kind:<19} {z.led_count:>3} LEDs{note}")
        print("Config table:", ctrl.info.config_table.hex(" "))


def _state(args, kind):
    return {"kind": kind, "mode": args.mode, "color": args.color, "zones": args.zone or ["all"],
            "speed": args.speed, "brightness": args.brightness}


def cmd_mode(args):
    state = _state(args, "hardware")
    with _open(args) as ctrl:
        apply(ctrl, EffectRunner(ctrl), state)
    cfg = config.load()
    cfg["last"] = state
    config.save(cfg)
    print(f"Applied hardware mode '{args.mode}'.")


def cmd_off(args):
    args.mode, args.color, args.speed, args.brightness = "off", "000000", 1.0, 1.0
    cmd_mode(args)


def cmd_effect(args):
    state = _state(args, "software")
    with _open(args) as ctrl:
        runner = EffectRunner(ctrl)
        apply(ctrl, runner, state)
        cfg = config.load()
        cfg["last"] = state
        config.save(cfg)
        print(f"Running software effect '{args.mode}' (Ctrl+C to stop).")
        try:
            while runner.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            runner.stop()


def cmd_restore(args):
    state = config.load()["last"]
    if state.get("kind") == "software":
        print("Last state is a software effect; use `caselight serve` to keep it running.")
        return
    with _open(args) as ctrl:
        apply(ctrl, EffectRunner(ctrl), state)
    print(f"Restored '{state['mode']}'.")


def cmd_leds(args):
    cfg = config.load()
    cfg["argb_leds"][str(args.header)] = args.count
    config.save(cfg)
    print(f"ARGB header {args.header}: {args.count} LEDs")


def cmd_serve(args):
    from .server import serve
    with _open(args) as ctrl:
        serve(ctrl, args.host, args.port)


def main(argv=None):
    p = argparse.ArgumentParser(prog="caselight", description="Control ASUS Aura case lighting.")
    p.add_argument("--device", help="hidraw path (auto-detected by default)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="show controller and zones").set_defaults(fn=cmd_info)

    def lighting_args(sp, choices, default):
        sp.add_argument("mode", choices=choices, nargs="?", default=default)
        sp.add_argument("-c", "--color", default="ff0000", help="hex color, e.g. ff8800")
        sp.add_argument("-z", "--zone", action="append", help="zone name (repeatable, default all)")
        sp.add_argument("-b", "--brightness", type=float, default=1.0, help="0.0 - 1.0")
        sp.add_argument("-s", "--speed", type=float, default=1.0, help="software effect speed")

    sp = sub.add_parser("mode", help="set a built-in hardware mode (persists without caselight)")
    lighting_args(sp, [m for m in MODES if m != "direct"], "static")
    sp.set_defaults(fn=cmd_mode)

    sp = sub.add_parser("effect", help="run a per-LED software effect in the foreground")
    lighting_args(sp, list(EFFECTS), "rainbow-wave")
    sp.set_defaults(fn=cmd_effect)

    sp = sub.add_parser("off", help="turn lights off")
    sp.add_argument("-z", "--zone", action="append")
    sp.set_defaults(fn=cmd_off)

    sub.add_parser("restore", help="re-apply the last hardware mode").set_defaults(fn=cmd_restore)

    sp = sub.add_parser("leds", help="set the number of LEDs on an ARGB header")
    sp.add_argument("header", type=int, help="header number, e.g. 1 for argb1")
    sp.add_argument("count", type=int)
    sp.set_defaults(fn=cmd_leds)

    sp = sub.add_parser("serve", help="start the web UI")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.set_defaults(fn=cmd_serve)

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except (AuraError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
