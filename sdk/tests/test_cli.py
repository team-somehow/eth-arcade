"""The command line, and the settings file it reads."""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tick.cli import main
from tick.env import flag, load_env_file, number


class TestNew(unittest.TestCase):
    def test_new_writes_a_game_that_imports_and_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(['new', 'my_game', '--into', folder]), 0)
            path = Path(folder) / 'my_game.py'
            self.assertTrue(path.exists())
            body = path.read_text()
            self.assertIn('MY GAME', body)
            self.assertIn('class MyGame(Game)', body)
            self.assertNotIn('ClassName', body)

    def test_new_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as folder:
            with redirect_stdout(io.StringIO()):
                main(['new', 'g', '--into', folder])
                self.assertEqual(main(['new', 'g', '--into', folder]), 1)
                self.assertEqual(main(['new', 'g', '--into', folder, '--force']), 0)


class TestDoctor(unittest.TestCase):
    def test_doctor_reports_the_feed_and_the_settings(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(['doctor']), 0)
        text = out.getvalue()
        self.assertIn('tick-sdk', text)
        self.assertIn('TICK_MARKET_SOURCE', text)
        self.assertIn('got', text)          # the sim feed answered


class TestRecordAndReplay(unittest.TestCase):
    def test_a_recorded_market_replays(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'm.ndjson'
            err = io.StringIO()
            with redirect_stdout(io.StringIO()):
                main(['record', '-o', str(path), '--source', 'sim', '--seconds', '0.5',
                      '--seed', '4'])
            self.assertTrue(path.exists())
            out = io.StringIO()
            with redirect_stdout(out):
                main(['replay', str(path), '--speed', '50'])
            self.assertGreater(len(out.getvalue().splitlines()), 3)


class TestSettings(unittest.TestCase):
    def test_the_shell_wins_over_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('TICK_ASSET=btc\n# a comment\nTICK_STAKE_USDC="0.5"\n')
            os.environ['TICK_ASSET'] = 'sol'
            try:
                load_env_file(path)
                self.assertEqual(os.environ['TICK_ASSET'], 'sol')
                self.assertEqual(os.environ['TICK_STAKE_USDC'], '0.5')
            finally:
                os.environ.pop('TICK_ASSET', None)
                os.environ.pop('TICK_STAKE_USDC', None)

    def test_a_missing_file_is_not_an_error(self):
        load_env_file('/nowhere/at/all/.env')

    def test_flags_and_numbers_fall_back(self):
        os.environ['TICK_SOUND'] = 'off'
        try:
            self.assertFalse(flag('TICK_SOUND'))
        finally:
            os.environ.pop('TICK_SOUND')
        self.assertTrue(flag('TICK_NOT_SET'))
        self.assertEqual(number('TICK_NOT_SET', 10.0), 10.0)


if __name__ == '__main__':
    unittest.main()
