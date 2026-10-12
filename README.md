# caselight

[![Tests](https://github.com/vaisajuh/caselight/actions/workflows/tests.yml/badge.svg)](https://github.com/vaisajuh/caselight/actions/workflows/tests.yml)

Control the RGB lighting connected to an ASUS motherboard's **Aura USB LED controller**
(onboard LEDs, 12V RGB headers and 5V ARGB headers) on Linux. Pure Python, no dependencies.

Built for the ASUS TUF GAMING B550-PLUS (`0b05:1939`); other Aura USB mainboard
controllers (`18f3`, `19af`, `1aa6`, ...) should work too.

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
- Want to add a different device or brand? See clcr's
  [CONTRIBUTING.md](https://github.com/vaisajuh/clcr/blob/main/CONTRIBUTING.md#adding-a-new-device).

## Maintainer

Maintained by **Juha Väisänen** ([@vaisajuh](https://github.com/vaisajuh)).

## Related projects

Part of a small set of Linux lighting tools, all pure Python with no third-party dependencies:

- [clcr](https://github.com/vaisajuh/clcr): Computer Lighting Control Center, one desktop app for lighting across brands and devices (bundles the drivers below)
- [akkoctl](https://github.com/vaisajuh/akkoctl): Akko 5075B Plus-S keyboard: RGB backlight, sidelights, keymap and macros
- **caselight** (this repo): ASUS Aura USB controller: motherboard and ARGB header lighting
- [logiled](https://github.com/vaisajuh/logiled): Logitech G502 HERO mouse: lighting, DPI, polling rate and onboard mode

## License

MIT. See [LICENSE](LICENSE).
