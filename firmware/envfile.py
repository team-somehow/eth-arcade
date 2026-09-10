"""Settings from firmware/.env, so the device can be configured without a shell.

Only KEY=value lines are read; blank lines and # comments are skipped, and a
value may be wrapped in matching quotes. Anything already set in the real
environment wins, so a one-off `TICK_MARKET_SOURCE=coinbase python main.py`
still overrides the file. Kept dependency-free for the Pi.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).with_name('.env')


def load_env_file(path: Path = ENV_FILE) -> None:
    try:
        text = path.read_text()
    except FileNotFoundError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.removeprefix('export ').strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)
