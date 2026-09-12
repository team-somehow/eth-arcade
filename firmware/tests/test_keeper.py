"""The scorekeeper starts beside the game, once, and only where it can do its job."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import keeper


class KeeperTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {'TICK_FUNDING': 'arc-testnet',
                                                'ARC_DEPLOYER_KEY': '0x' + '11' * 32})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.lock = Path(self.enterContext(__import__('tempfile').TemporaryDirectory()))
        patch = mock.patch.object(keeper, 'LOCK', self.lock / 'scorekeeper.lock')
        patch.start()
        self.addCleanup(patch.stop)
        log = mock.patch.object(keeper, 'LOG', self.lock / 'scorekeeper.log')
        log.start()
        self.addCleanup(log.stop)
        key = self.lock / 'scorekeeper.json'
        key.write_text('{}')
        keeper_key = mock.patch.object(keeper, 'KEEPER_KEY', key)
        keeper_key.start()
        self.addCleanup(keeper_key.stop)

    def test_demo_play_needs_no_scorekeeper(self):
        os.environ['TICK_FUNDING'] = 'demo'
        self.assertFalse(keeper.wanted())

    def test_it_can_be_turned_off(self):
        os.environ['TICK_SCOREKEEPER'] = '0'
        self.addCleanup(os.environ.pop, 'TICK_SCOREKEEPER', None)
        self.assertFalse(keeper.wanted())

    def test_a_machine_without_the_tick_key_starts_nothing(self):
        os.environ['ARC_DEPLOYER_KEY'] = ''    # load_env_file only fills what is unset
        self.assertIn('ARC_DEPLOYER_KEY', keeper.missing())
        with mock.patch('subprocess.Popen') as popen:
            self.assertIsNone(keeper.start())
        popen.assert_not_called()

    def test_a_missing_scorekeeper_key_is_never_invented(self):
        """load_device would mint one with no gas and no roles; every write would revert."""
        keeper.KEEPER_KEY.unlink()
        self.assertIn('scorekeeper.json', keeper.missing())
        with mock.patch('subprocess.Popen') as popen:
            self.assertIsNone(keeper.start())
        popen.assert_not_called()

    def test_a_machine_with_both_keys_is_ready(self):
        self.assertEqual(keeper.missing(), '')

    def test_only_the_first_launcher_on_a_machine_starts_one(self):
        held = keeper.claim()
        self.assertIsNotNone(held)
        self.assertIsNone(keeper.claim())     # a second game on this machine stands down
        held.close()
        again = keeper.claim()
        self.assertIsNotNone(again)
        again.close()


if __name__ == '__main__':
    unittest.main()
