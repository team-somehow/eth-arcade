"""The installed app must use live defaults and preserve local overrides."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from desktop import configure


class DesktopTests(unittest.TestCase):
    def test_live_defaults_use_a_writable_wallet_directory(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            'XDG_CONFIG_HOME': folder, 'XDG_DATA_HOME': folder,
        }, clear=True):
            configure()
            self.assertEqual(os.environ['TICK_FUNDING'], 'arc-testnet')
            self.assertEqual(os.environ['TICK_MARKET_SOURCE'], 'coinbase')
            self.assertEqual(os.environ['TICK_STAKE_USDC'], '0.001')
            self.assertEqual(os.environ['TICK_DATA_DIR'], f'{folder}/tick-box-run/.tick')

    def test_local_config_can_select_simulation_and_existing_wallet(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
            'XDG_CONFIG_HOME': folder,
        }, clear=True):
            config = Path(folder) / 'tick-box-run/.env'
            config.parent.mkdir()
            config.write_text('TICK_FUNDING=demo\nTICK_MARKET_SOURCE=sim\nTICK_DATA_DIR=/existing/.tick\n')
            configure()
            self.assertEqual(os.environ['TICK_FUNDING'], 'demo')
            self.assertEqual(os.environ['TICK_MARKET_SOURCE'], 'sim')
            self.assertEqual(os.environ['TICK_DATA_DIR'], '/existing/.tick')

    def test_shell_override_wins_over_local_config(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / '.env'
            config.write_text('TICK_MARKET_SOURCE=sim\n')
            with patch.dict(os.environ, {'TICK_CONFIG_FILE': str(config),
                                        'TICK_MARKET_SOURCE': 'coinbase'}, clear=True):
                configure()
                self.assertEqual(os.environ['TICK_MARKET_SOURCE'], 'coinbase')

    def test_missing_leaderboard_dependency_does_not_crash_dial_navigation(self):
        from screens.board import BoardFeed
        feed = BoardFeed()
        with patch.dict('sys.modules', {'names': None}):
            feed.want()
        self.assertIn('LEADERBOARD UNAVAILABLE', feed.error)
        self.assertIsNone(feed._thread)
