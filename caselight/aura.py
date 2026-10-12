"""Low-level driver for the ASUS Aura USB mainboard LED controller (0b05:1939 etc).

Talks to the controller through Linux hidraw, so no third-party packages are needed.
The protocol follows the one documented by the OpenRGB project for the
"AURA LED Controller" found on B550/X570/Z490-era ASUS boards.
"""

import os
import select
from dataclasses import dataclass, field
from pathlib import Path

ASUS_VID = 0x0B05
# Known mainboard Aura USB controller product IDs.
AURA_PIDS = {0x1867, 0x1872, 0x18A3, 0x18A5, 0x18F3, 0x1939, 0x19AF, 0x1AA6}

REPORT_ID = 0xEC
PACKET_SIZE = 65
MAX_LEDS_PER_PACKET = 20  # 60 payload bytes / 3

CMD_EFFECT = 0x35
CMD_EFFECT_COLOR = 0x36
CMD_COMMIT = 0x3F
CMD_DIRECT = 0x40
CMD_FIRMWARE = 0x82
CMD_CONFIG = 0xB0

# Built-in hardware effects. These keep running on the controller itself,
# so no software has to stay running.
MODES = {
    "off": 0x00,
    "static": 0x01,
    "breathing": 0x02,
    "flashing": 0x03,
    "spectrum": 0x04,
    "rainbow": 0x05,
    "spectrum-breathing": 0x06,
    "chase-fade": 0x07,
    "spectrum-chase-fade": 0x08,
    "chase": 0x09,
    "spectrum-chase": 0x0A,
    "spectrum-wave": 0x0B,
    "chase-rainbow-pulse": 0x0C,
    "random-flicker": 0x0D,
    "direct": 0xFF,
}


class AuraError(Exception):
    pass


@dataclass
class Zone:
    name: str
    effect_channel: int
    direct_channel: int
    led_count: int
    # Index of this zone's first slot in the 0x36 effect-color table.
    color_offset: int
    addressable: bool = False


@dataclass
class DeviceInfo:
    path: str
    firmware: str = ""
    config_table: bytes = b""
    zones: list[Zone] = field(default_factory=list)


def find_devices() -> list[str]:
    """Return /dev/hidrawN paths of all Aura mainboard controllers."""
    found = []
    for node in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
        try:
            uevent = (node / "device" / "uevent").read_text()
        except OSError:
            continue
        for line in uevent.splitlines():
            if line.startswith("HID_ID="):
                _bus, vid, pid = line[7:].split(":")
                if int(vid, 16) == ASUS_VID and int(pid, 16) in AURA_PIDS:
                    found.append(f"/dev/{node.name}")
    return found


def build_packet(*data: int) -> bytes:
    buf = bytearray(PACKET_SIZE)
    buf[0] = REPORT_ID
    buf[1 : 1 + len(data)] = bytes(data)
    return bytes(buf)


def build_direct_packets(channel: int, colors: list[tuple[int, int, int]]) -> list[bytes]:
    """Split a frame for one channel into direct-mode packets; the last one applies it."""
    packets = []
    for start in range(0, len(colors), MAX_LEDS_PER_PACKET):
        chunk = colors[start : start + MAX_LEDS_PER_PACKET]
        last = start + len(chunk) >= len(colors)
        payload = [c for rgb in chunk for c in rgb]
        packets.append(
            build_packet(CMD_DIRECT, channel | (0x80 if last else 0), start, len(chunk), *payload)
        )
    return packets


def build_effect_color_packet(start: int, colors: list[tuple[int, int, int]]) -> bytes:
    mask = ((1 << len(colors)) - 1) << start
    buf = bytearray(build_packet(CMD_EFFECT_COLOR, (mask >> 8) & 0xFF, mask & 0xFF, 0x00))
    for i, rgb in enumerate(colors):
        offset = 5 + 3 * (start + i)
        buf[offset : offset + 3] = bytes(rgb)
    return bytes(buf)


class AuraController:
    def __init__(self, path: str | None = None, argb_leds: dict[int, int] | None = None):
        if path is None:
            devices = find_devices()
            if not devices:
                raise AuraError("No ASUS Aura USB controller found.")
            path = devices[0]
        try:
            self.fd = os.open(path, os.O_RDWR)
        except PermissionError as e:
            raise AuraError(
                f"Permission denied opening {path}. Install the udev rule "
                "(see README) or run with sudo."
            ) from e
        self.info = DeviceInfo(path=path)
        self._argb_leds = argb_leds or {}
        self._probe()

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- transport ------------------------------------------------------

    def _write(self, packet: bytes):
        os.write(self.fd, packet)

    def _request(self, cmd: int, expect: int, timeout: float = 1.0) -> bytes:
        self._write(build_packet(cmd))
        while True:
            ready, _, _ = select.select([self.fd], [], [], timeout)
            if not ready:
                raise AuraError(f"Controller did not answer command 0x{cmd:02X}")
            data = os.read(self.fd, PACKET_SIZE)
            if len(data) > 1 and data[0] == REPORT_ID and data[1] == expect:
                return data

    # ---- discovery ------------------------------------------------------

    def _probe(self):
        fw = self._request(CMD_FIRMWARE, 0x02)
        self.info.firmware = fw[2:18].split(b"\0")[0].decode("ascii", "replace")
        cfg = self._request(CMD_CONFIG, 0x30)
        table = cfg[4:64]
        self.info.config_table = table

        argb_headers = table[0x02]
        mb_leds = table[0x1B]
        rgb_headers = table[0x1D]

        fixed_leds = mb_leds + rgb_headers
        zones = [Zone("mainboard", 0, 0x04, fixed_leds, 0)]
        for i in range(argb_headers):
            zones.append(
                Zone(
                    f"argb{i + 1}",
                    effect_channel=i + 1,
                    direct_channel=i,
                    led_count=self._argb_leds.get(i + 1, 0),
                    color_offset=fixed_leds + i,
                    addressable=True,
                )
            )
        self.info.zones = zones

    @property
    def zones(self) -> list[Zone]:
        return self.info.zones

    def zone(self, name: str) -> Zone:
        for z in self.zones:
            if z.name == name:
                return z
        raise AuraError(f"Unknown zone '{name}'. Available: {', '.join(z.name for z in self.zones)}")

    # ---- control --------------------------------------------------------

    def set_mode(self, zone: Zone, mode: str, color: tuple[int, int, int] = (255, 255, 255)):
        """Run one of the controller's built-in effects on a zone."""
        if mode not in MODES:
            raise AuraError(f"Unknown mode '{mode}'. Available: {', '.join(MODES)}")
        self._write(build_packet(CMD_EFFECT, zone.effect_channel, 0x00, 0x00, MODES[mode]))
        if mode != "direct":
            # Addressable headers take a single color slot in effect mode.
            count = 1 if zone.addressable else zone.led_count
            if count:
                self._write(build_effect_color_packet(zone.color_offset, [color] * count))
            self._write(build_packet(CMD_COMMIT, 0x55))

    def enter_direct(self, zones: list[Zone] | None = None):
        for zone in zones or self.zones:
            self.set_mode(zone, "direct")

    def send_direct(self, zone: Zone, colors: list[tuple[int, int, int]]):
        """Send one frame of per-LED colors to a zone already in direct mode."""
        for packet in build_direct_packets(zone.direct_channel, colors):
            self._write(packet)
