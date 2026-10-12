# caselight: motherboard and case lighting for Linux

[![Tests](https://github.com/vaisajuh/caselight/actions/workflows/tests.yml/badge.svg)](https://github.com/vaisajuh/caselight/actions/workflows/tests.yml)

Control the RGB lighting of your motherboard and everything plugged into it
(onboard LEDs, 12V RGB headers, 5V ARGB fans and strips) on Linux, without
the vendor's Windows software. Pure Python, no dependencies.

The goal is to cover all the major motherboard brands. **Today it supports
ASUS Aura**, and other brands are welcome as contributions (see
[Adding a motherboard brand](#adding-a-motherboard-brand)).

| Brand | Controller | Status |
| --- | --- | --- |
| ASUS | Aura USB, TUF GAMING B550-PLUS (`0b05:1939`) | ✅ Tested by maintainer |
| ASUS | Other Aura USB mainboard controllers (`1867`, `1872`, `18a3`, `18a5`, `18f3`, `19af`, `1aa6`) | 🟡 Untested: same protocol, should work |
| MSI | Mystic Light | Wanted |
| Gigabyte | RGB Fusion 2 | Wanted |
| ASRock | Polychrome | Wanted |

## Install

```bash
./install.sh
```

This installs a udev rule so your user can access the controller without root,
installs the `caselight` command, and adds an optional systemd user service.

## Usage

```bash
caselight info                          # show controller, firmware and zones
caselight mode static -c ff0000         # built-in hardware mode, all zones
caselight mode breathing -c 00aaff -z argb1
caselight mode spectrum-wave
caselight off

caselight leds 1 24                     # tell caselight argb1 has 24 LEDs
caselight effect rainbow-wave -s 1.5    # per-LED software effect (foreground)
caselight effect comet -c ff00ff -z argb1

caselight serve                         # web UI at http://127.0.0.1:8765
systemctl --user enable --now caselight # run the web UI on login
```

### Hardware modes vs software effects

* **Hardware modes** (`caselight mode`) run on the controller itself. They keep going
  after caselight exits.
* **Software effects** (`caselight effect`, or the "Software" tab in the UI) are drawn
  per-LED by your PC in direct mode. They need caselight running and the right LED count
  for each ARGB header (`caselight leds <header> <count>`), because the controller can't
  detect how many LEDs are connected.

Settings live in `~/.config/caselight/config.json`.

## Development

```bash
python3 -m unittest -v      # tests use a fake controller, no hardware needed
python3 -m caselight info   # run from the source tree
```

Protocol notes: HID report `0xEC`, 65-byte packets. `0x82` firmware, `0xB0` config table,
`0x35` set effect, `0x36` effect colors, `0x3F` commit, `0x40` direct per-LED colors.
Based on the protocol documented by the [OpenRGB](https://openrgb.org) project.

## How it's built

- **Finding the controller.** `aura.py` looks through `/sys/class/hidraw/*`
  for ASUS (`0b05`) devices with a known Aura mainboard product ID and opens
  the matching `/dev/hidrawN`. No libusb or hidapi is needed.
- **Protocol.** 65-byte HID reports with report ID `0xEC`. On open the
  controller is asked for its firmware string (`0x82`) and its configuration
  table (`0xB0`), which says how many fixed RGB LEDs and ARGB headers the
  board has. These become *zones* (`mainboard`, `argb1`, …).
- **Hardware modes** are set with `0x35` (effect), `0x36` (colors) and `0x3F`
  (commit). The controller animates them itself, so they keep running after
  caselight exits.
- **Software effects** (`effects.py`) put zones into direct mode. A background
  thread renders a frame 30 times a second (each effect is a small function of
  time and LED index) and streams it with `0x40` packets of up to 20 LEDs.
- **One state format.** `core.apply()` takes a dict
  (`kind, mode, color, zones, speed, brightness`), so the CLI, the web UI
  (stdlib `http.server`, same-origin requests only) and the saved config in
  `~/.config/caselight/config.json` all share it.
- **Tests** use a fake controller that records the packets instead of
  sending them.

The protocol follows the one documented by the [OpenRGB](https://openrgb.org) project.

## How device support works

caselight is maintained by one person with one motherboard. Support for other
boards and brands comes from the people who own them:

1. You write or fix the driver and test it on your own hardware.
2. You open a pull request that includes a hardware test report (the pull
   request template asks for it).
3. The maintainer reviews the code: it is readable, talks only to its own
   device, uses only the Python standard library, and comes with an emulated
   device and tests. The maintainer can't test your hardware, so the merge
   relies on your test report.
4. After the merge you are listed as the driver's maintainer below, and asked
   to review future changes to it.

The status column above shows who has tested a device: ✅ tested by
maintainer, 🤝 community tested (by the named contributor), 🟡 untested. If a
driver breaks and nobody with the hardware can fix it, it is marked
unmaintained and may be removed.

| Driver | Maintainer |
| --- | --- |
| ASUS Aura (`caselight/aura.py`) | [@vaisajuh](https://github.com/vaisajuh) |

> **Use at your own risk.** caselight is provided as is, without warranty
> (see [LICENSE](LICENSE)). Drivers avoid commands that change firmware or
> settings permanently, but a bug in a driver or in a device's firmware can
> still leave the lights in an odd state.

## Adding a motherboard brand

The ASUS-specific code lives in `caselight/aura.py`: finding the controller,
the USB protocol and the list of hardware modes. The software effects
(`effects.py`), settings (`config.py`), CLI and web UI are shared. A new
brand, for example MSI Mystic Light, needs:

- a module next to it (`caselight/msi.py`) with a controller class offering
  the same methods as `AuraController`: `zones`, `set_mode()`,
  `enter_direct()`, `send_direct()` and `close()`
- detection, so caselight picks the right controller automatically
- an emulated controller and tests, like `FakeController` in
  `tests/test_caselight.py`
- a line for its USB vendor ID in `udev/60-caselight.rules`

The first new brand will also have to make a few shared parts brand-neutral:
the hardware mode names come from `aura.MODES` today, and the CLI opens an
`AuraController` directly. That pull request is the right place to do it.

The [OpenRGB](https://openrgb.org) project documents many of these
protocols. Learning from its documentation is fine, but don't copy its code:
OpenRGB is GPL licensed and caselight is MIT.

## Contributing

Bug reports and pull requests are welcome.

- Report bugs and ask questions in [issues](https://github.com/vaisajuh/caselight/issues).
- Run the tests before opening a pull request: `python3 -m unittest -v`.
  They use an emulated device, so no hardware is needed, and they also run
  automatically on every pull request.
- Use only the Python standard library (no third-party dependencies).
- `caselight/aura.py`, `caselight/core.py`, `caselight/effects.py`, `caselight/config.py` are also bundled in
  [clcr](https://github.com/vaisajuh/clcr), the Computer Lighting Control
  Center. You don't need to change clcr yourself: after your pull request is
  merged here, clcr's nightly sync opens a pull request there with the change.
  If you change functions or classes in these files, say so in your pull
  request, since clcr's GUI uses them.
- Adding a motherboard brand? See [above](#adding-a-motherboard-brand).
  Other kinds of devices: see clcr's
  [CONTRIBUTING.md](https://github.com/vaisajuh/clcr/blob/main/CONTRIBUTING.md#adding-a-new-device).

## Maintainer

Maintained by **Juha Väisänen** ([@vaisajuh](https://github.com/vaisajuh)).

## Related projects

Part of a small set of Linux lighting tools, all pure Python with no third-party dependencies:

- [clcr](https://github.com/vaisajuh/clcr): Computer Lighting Control Center, one desktop app for lighting across brands and devices (bundles the drivers below)
- [viactl](https://github.com/vaisajuh/viactl): VIA/QMK keyboards (tested on Akko 5075B Plus-S): RGB backlight, sidelights, keymap and macros
- **caselight** (this repo): motherboard and case lighting (currently ASUS Aura)
- [logiled](https://github.com/vaisajuh/logiled): Logitech G502 HERO mouse: lighting, DPI, polling rate and onboard mode

## License

MIT. See [LICENSE](LICENSE).
