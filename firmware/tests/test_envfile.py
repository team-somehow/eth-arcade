import os
import tempfile
import unittest
from pathlib import Path

from envfile import load_env_file

KEYS = ('TICK_TEST_A', 'TICK_TEST_B', 'TICK_TEST_C', 'TICK_TEST_D')


class EnvFileTest(unittest.TestCase):
    def setUp(self):
        for key in KEYS:
            os.environ.pop(key, None)
        self.addCleanup(lambda: [os.environ.pop(key, None) for key in KEYS])

    def env_file(self, text: str) -> Path:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / '.env'
        path.write_text(text)
        return path

    def test_reads_values_skipping_comments_and_blanks(self):
        load_env_file(self.env_file(
            '# a comment\n\nTICK_TEST_A=coinbase\nexport TICK_TEST_B = sim \nnot a setting\n'))
        self.assertEqual(os.environ['TICK_TEST_A'], 'coinbase')
        self.assertEqual(os.environ['TICK_TEST_B'], 'sim')

    def test_strips_matching_quotes_only(self):
        load_env_file(self.env_file('TICK_TEST_C="two words"\nTICK_TEST_D="unbalanced\n'))
        self.assertEqual(os.environ['TICK_TEST_C'], 'two words')
        self.assertEqual(os.environ['TICK_TEST_D'], '"unbalanced')

    def test_real_environment_wins(self):
        os.environ['TICK_TEST_A'] = 'from-shell'
        load_env_file(self.env_file('TICK_TEST_A=from-file\n'))
        self.assertEqual(os.environ['TICK_TEST_A'], 'from-shell')

    def test_missing_file_is_ignored(self):
        load_env_file(Path(tempfile.gettempdir()) / 'no-such-dir' / '.env')
        self.assertNotIn('TICK_TEST_A', os.environ)


if __name__ == '__main__':
    unittest.main()
