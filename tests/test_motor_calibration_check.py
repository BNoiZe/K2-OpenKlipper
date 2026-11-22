import pathlib
import struct
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "klippy"))

from extras import k2_motor_bus as bus  # noqa: E402


def make(values):
    """A motor bus whose param reads return values {pid: float}."""
    m = types.SimpleNamespace(calibration_warnings=[], track_err_time=0.,
                              writes=[])

    def xfer(addr, payload):
        payload = tuple(payload)
        if payload == bus.END_PARAM_READ:
            return None, b""
        pid = payload[3]
        if payload[2] == 0x01:
            m.writes.append(payload)
            values[pid] = struct.unpack('<f', bytes(payload[4:8]))[0]
        value = values.get(pid, 1.0)
        return None, bytes(5) + struct.pack('<f', value) + b"\x00"
    m.xfer = xfer
    m._read_param = lambda addr, pid: bus.K2MotorBus._read_param(m, addr, pid)
    return m


def check(values):
    m = make(values)
    bus.K2MotorBus._read_params(m, "y", 0x82)
    return m.calibration_warnings


class CalibrationCheckTest(unittest.TestCase):
    def test_k2_plus_param_19_alone_is_fine(self):
        # 11-01: every K2 Plus motor reads 19 = 0.15 with 09 normal
        self.assertEqual(check({0x09: 159.91, 0x19: 0.15}), [])

    def test_k2_values_are_fine(self):
        self.assertEqual(check({0x09: 181.15, 0x19: 4.95}), [])

    def test_offset_near_zero_warns(self):
        warnings = check({0x09: 0.0, 0x19: 0.15})
        self.assertEqual(len(warnings), 1)
        self.assertIn("motor Y", warnings[0])



class TrackErrTimeTest(unittest.TestCase):
    def run_wake(self, flash, want):
        values = {0x09: 181.15, 0x19: 4.95, 0xbc: flash}
        m = make(values)
        m.track_err_time = want
        bus.K2MotorBus._read_params(m, "x", 0x81)
        return m, values

    def test_k2_pro_flash_gets_stock_value(self):
        m, values = self.run_wake(0.01, 0.1)
        self.assertEqual(len(m.writes), 1)
        self.assertEqual(m.writes[0][:4], (0x00, 0x06, 0x01, 0xbc))
        self.assertAlmostEqual(values[0xbc], 0.1, places=5)
        self.assertEqual(m.calibration_warnings, [])

    def test_unset_or_already_high_writes_nothing(self):
        self.assertEqual(self.run_wake(0.01, 0.)[0].writes, [])
        self.assertEqual(self.run_wake(0.1, 0.1)[0].writes, [])


if __name__ == "__main__":
    unittest.main()
