import importlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "klippy"))
cfs_mod = importlib.import_module("extras.k2_cfs")


class Obj:
    def __init__(self, status):
        self.status = status

    def get_status(self, eventtime=None):
        return self.status


class Reactor:
    now = 0.

    def monotonic(self):
        return self.now

    def pause(self, t):
        self.now = max(self.now, t)


class Cmd:
    def __init__(self, params):
        self.params = params

    def get(self, name, default=None):
        return self.params.get(name, default)

    def get_int(self, name, default=None, **kw):
        return int(self.params.get(name, default))

    def respond_info(self, msg):
        pass

    def error(self, msg):
        return RuntimeError(msg)


class FakeGcode:
    def __init__(self):
        self.scripts = []

    def run_script_from_command(self, script):
        self.scripts.append(script)


def make_cfs(fail_at):
    cfs = cfs_mod.K2CFS.__new__(cfs_mod.K2CFS)
    cfs.gcode = FakeGcode()
    objects = {'toolhead': Obj({'max_accel': 12000.})}

    class P:
        def lookup_object(self, name, default=None):
            return objects.get(name, default)

        def get_reactor(self):
            return Reactor()
    cfs.printer = P()
    cfs.status = {}
    for name in ('_require_cfs', '_require_actuation', '_require_idle',
                 '_require_position', '_set_runout_sensor_enabled',
                 '_require_hot_extruder',
                 '_count'):
        setattr(cfs, name, lambda *a: None)
    cfs._require_safe_motion = lambda *a: (205., 261., 10.)
    cfs._run_query = lambda name: {'slots_loaded': [1, 1, 1, 1]}
    cfs._measuring = lambda: {}
    cfs._path_mask = lambda m: cfs.SLOT_MASKS['C']
    cfs._nozzle_has_filament = lambda: True
    cfs.manage_runout_sensor = True
    cfs.cutter_switch_state = True
    cfs.cutter_events = None
    for name in ('purge_return_x', 'purge_safe_y', 'purge_entry_x',
                 'purge_y', 'purge_gate_x', 'purge_x', 'cutter_x',
                 'cutter_y', 'cutter_cut_x', 'cutter_release_x'):
        setattr(cfs, name, 1.)
    cfs.purge_door_x = None
    cfs.cutter_rams = 1
    for name in ('cutter_speed', 'cutter_ram_speed', 'cutter_release_speed',
                 'cutter_ram_accel', 'cutter_retract_length',
                 'cutter_retract_speed', 'cutter_tip_length',
                 'cutter_tip_push_speed', 'cutter_tip_pull_speed'):
        setattr(cfs, name, 1.)

    def after_cut(gcmd):
        raise RuntimeError("nozzle sensor still detects filament")
    cfs._cmd_CFS_UNLOAD_AFTER_CUT = after_cut
    if fail_at == 'staging':
        cfs.cutter_switch_state = False
    return cfs


class UnloadWipeTest(unittest.TestCase):
    def run_unload(self, cfs):
        with self.assertRaises(RuntimeError) as ctx:
            cfs.cmd_CFS_CUT_UNLOAD(Cmd({'SLOT': 'C', 'CONFIRM': '1'}))
        return str(ctx.exception)

    def test_failed_unload_after_the_cut_wipes_the_nozzle(self):
        cfs = make_cfs('after_cut')
        msg = self.run_unload(cfs)
        self.assertIn('still detects filament', msg)
        self.assertIn('NOZZLE_WIPE CONFIRM=1 PARK=0', cfs.gcode.scripts)

    def test_cutter_rams_rams_again_only_while_the_knife_is_stuck(self):
        # As stock cut_material: one ram; again only if the knife is not back
        for stuck, rams, want in ((0, 3, 1), (1, 3, 2), (5, 3, 3)):
            cfs = make_cfs('after_cut')
            cfs.cutter_rams = rams
            run = cfs.gcode.run_script_from_command
            left = [stuck]

            def gcode(script, run=run, cfs=cfs, left=left):
                run(script)
                if script.startswith('SET_VELOCITY_LIMIT') and 'G1 X' in script:
                    cfs.cutter_switch_state = left[0] <= 0
                    left[0] -= 1
            cfs.gcode.run_script_from_command = gcode
            try:
                cfs.cmd_CFS_CUT_UNLOAD(Cmd({'SLOT': 'C', 'CONFIRM': '1'}))
            except Exception:
                pass
            ram = [sc for sc in cfs.gcode.scripts
                   if sc.startswith('SET_VELOCITY_LIMIT') and 'G1 X' in sc]
            self.assertEqual(len(ram), want, (stuck, rams))

    def test_first_ram_runs_on_from_the_approach_without_a_stop(self):
        # Stock: run to cutter_x and ram in one queue, no M400 between
        cfs = make_cfs('after_cut')
        cfs.cutter_x = 10.
        try:
            cfs.cmd_CFS_CUT_UNLOAD(Cmd({'SLOT': 'C', 'CONFIRM': '1'}))
        except Exception:
            pass
        ram = [sc for sc in cfs.gcode.scripts
               if sc.startswith('SET_VELOCITY_LIMIT') and 'G1 X' in sc][0]
        approach, rest = ram.split('G1 X10.000', 1)
        self.assertNotIn('M400', approach + rest.split('\n', 1)[0])
        self.assertEqual(ram.count('M400'), 1)
        self.assertTrue(ram.rstrip().endswith('M400'))

    def test_failure_before_the_cut_does_not_wipe(self):
        cfs = make_cfs('staging')
        self.run_unload(cfs)
        self.assertNotIn('NOZZLE_WIPE CONFIRM=1 PARK=0', cfs.gcode.scripts)

    def test_a_failing_wipe_keeps_the_unload_error(self):
        cfs = make_cfs('after_cut')
        run = cfs.gcode.run_script_from_command

        def gcode(script):
            if script.startswith('NOZZLE_WIPE'):
                raise RuntimeError("wipe failed")
            run(script)
        cfs.gcode.run_script_from_command = gcode
        msg = self.run_unload(cfs)
        self.assertIn('still detects filament', msg)



class ChuteDoorTest(unittest.TestCase):
    # K2 Pro: X100 pushes the chute door open, the purge is back at X124
    def test_door_opener_runs_between_gate_and_purge_spot(self):
        cfs = cfs_mod.K2CFS.__new__(cfs_mod.K2CFS)
        cfs.purge_gate_x, cfs.purge_x, cfs.purge_y = 138., 124., 329.
        cfs.purge_door_x = 100.
        xs = [m.split()[1] for m in cfs._chute_moves(600.)]
        self.assertEqual(xs, ['X138.000', 'X100.000', 'X124.000'])
        cfs.purge_door_x = None
        xs = [m.split()[1] for m in cfs._chute_moves(600.)]
        self.assertEqual(xs, ['X138.000', 'X124.000'])

if __name__ == '__main__':
    unittest.main()
