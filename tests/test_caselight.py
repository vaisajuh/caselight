import time
import unittest

from caselight import config
from caselight.aura import AuraController, DeviceInfo, Zone, build_direct_packets, build_effect_color_packet
from caselight.core import apply
from caselight.effects import EffectRunner, render


class FakeController(AuraController):
    """AuraController with recorded writes instead of a real hidraw device."""

    def __init__(self):
        self.sent = []
        self.info = DeviceInfo(path="/dev/fake", firmware="TEST", zones=[
            Zone("mainboard", 0, 4, 2, 0),
            Zone("argb1", 1, 0, 30, 2, addressable=True),
            Zone("argb2", 2, 1, 0, 3, addressable=True),
        ])

    def _write(self, packet):
        assert len(packet) == 65 and packet[0] == 0xEC
        self.sent.append(packet)

    def close(self):
        pass


class PacketTests(unittest.TestCase):
    def test_direct_packets_chunked_and_last_applies(self):
        pkts = build_direct_packets(0, [(1, 2, 3)] * 45)
        self.assertEqual(len(pkts), 3)
        self.assertEqual([p[3] for p in pkts], [0, 20, 40])
        self.assertEqual([p[4] for p in pkts], [20, 20, 5])
        self.assertEqual([p[2] & 0x80 for p in pkts], [0, 0, 0x80])
        self.assertEqual(pkts[0][5:8], bytes([1, 2, 3]))

    def test_effect_color_mask_and_offset(self):
        p = build_effect_color_packet(2, [(9, 8, 7)])
        self.assertEqual((p[2] << 8) | p[3], 0b100)
        self.assertEqual(p[5 + 6 : 5 + 9], bytes([9, 8, 7]))


class ApplyTests(unittest.TestCase):
    def test_hardware_mode_all_zones(self):
        ctrl = FakeController()
        apply(ctrl, EffectRunner(ctrl), {"kind": "hardware", "mode": "breathing", "color": "#00ff00"})
        effects = [p for p in ctrl.sent if p[1] == 0x35]
        self.assertEqual([(p[2], p[5]) for p in effects], [(0, 2), (1, 2), (2, 2)])
        self.assertEqual(sum(p[1] == 0x3F for p in ctrl.sent), 3)

    def test_brightness_scales_hardware_color(self):
        ctrl = FakeController()
        apply(ctrl, EffectRunner(ctrl), {"kind": "hardware", "mode": "static", "color": "ff0000",
                                         "zones": ["mainboard"], "brightness": 0.5})
        color = next(p for p in ctrl.sent if p[1] == 0x36)
        self.assertEqual(color[5:8], bytes([128, 0, 0]))

    def test_software_effect_streams_frames_to_sized_zones(self):
        ctrl = FakeController()
        runner = EffectRunner(ctrl)
        apply(ctrl, runner, {"kind": "software", "mode": "rainbow-wave", "color": "fff"})
        time.sleep(0.15)
        runner.stop()
        direct = [p for p in ctrl.sent if p[1] == 0x40]
        self.assertTrue(direct)
        # argb2 has 0 LEDs configured so it must be skipped.
        self.assertEqual({p[2] & 0x7F for p in direct}, {4, 0})

    def test_render_bounds(self):
        for name in ("static", "breathing", "color-cycle", "rainbow-wave", "comet", "candle"):
            frame = render(name, 1.3, 12, (255, 128, 0), 2.0, 1.0)
            self.assertEqual(len(frame), 12)
            self.assertTrue(all(0 <= c <= 255 for rgb in frame for c in rgb))


class ConfigTests(unittest.TestCase):
    def test_parse_color(self):
        self.assertEqual(config.parse_color("#f80"), (255, 136, 0))
        self.assertEqual(config.parse_color("00ff7f"), (0, 255, 127))
        with self.assertRaises(ValueError):
            config.parse_color("zz")


if __name__ == "__main__":
    unittest.main()
