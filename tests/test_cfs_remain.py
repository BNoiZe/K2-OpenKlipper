import importlib
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "klippy"))
cfs_mod = importlib.import_module("extras.k2_cfs")


def make_cfs(printing=False, events=None):
    cfs = cfs_mod.K2CFS.__new__(cfs_mod.K2CFS)
    cfs.status = {}
    cfs.fitted = True
    cfs.env_poll_interval = 5.
    cfs.print_poll_interval = 0
    cfs.print_start_transaction = False
    cfs.last_actuation_time = -100.
    cfs.env_poll_failures = 0
    cfs.remain_stale = True
    cfs.queries = []
    cfs.events = events
    cfs._printing = lambda: printing
    cfs._check_running_out = lambda: None
    cfs._check_clog = lambda t: None

    def measuring():
        if cfs.events:
            cfs.status['last_slot_event'] = cfs.events
            cfs.remain_stale = True
            cfs.events = None
        return {'temperature': 20, 'humidity': 40}
    cfs._measuring = measuring

    def run_query(name):
        cfs.queries.append(name)
        return {'remain': [62, 0, 255, 100]}
    cfs._run_query = run_query
    return cfs


class RemainTest(unittest.TestCase):
    def test_unknown_levels_are_none(self):
        self.assertEqual(cfs_mod.K2CFS.known_remain([62, 0, 255, 100]),
                         [62, None, None, 100])

    def test_read_once_when_idle(self):
        cfs = make_cfs()
        cfs._env_poll(0.)
        cfs._env_poll(10.)
        self.assertEqual(cfs.status['remain'], [62, None, None, 100])
        self.assertEqual(cfs.queries, ['REMAIN_LEN'])

    def test_not_read_while_printing(self):
        cfs = make_cfs(printing=True)
        cfs._env_poll(0.)
        self.assertNotIn('remain', cfs.status)
        self.assertEqual(cfs.queries, [])

    def test_read_again_after_a_slot_event(self):
        cfs = make_cfs()
        cfs._env_poll(0.)
        cfs.events = 'A inserted'
        cfs._env_poll(10.)
        self.assertEqual(cfs.queries, ['REMAIN_LEN', 'REMAIN_LEN'])


if __name__ == '__main__':
    unittest.main()
