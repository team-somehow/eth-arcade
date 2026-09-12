"""Settings, so a device can be configured without a shell.

A handheld has no terminal. Everything tunable therefore lives in a `.env` file
next to the game, read once at startup, and **anything already set in the real
environment wins** -- so a one-off

    TICK_MARKET_SOURCE=coinbase python mygame.py

still overrides the file. Dependency-free on purpose: no python-dotenv on a Pi.

The settings every SDK layer reads
----------------------------------

    TICK_MARKET_SOURCE   sim | coinbase | substreams | replay | frozen
    TICK_ASSET           eth | btc | sol | hbar
    TICK_FUNDING         demo | arc-testnet
    TICK_STAKE_USDC      money per bet, e.g. 10 or 0.001
    TICK_ROTATE          auto | 0 | 90 | 180 | 270
    TICK_SOUND           1 | 0
    TICK_WINDOW_S        round length, if the game does not fix it
    SUBSTREAMS_BASE_URL  relay address, default http://localhost:8787
    TICK_REPLAY_FILE     recording to replay
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_NAME = '.env'


def load_env_file(path: str | Path | None = None) -> None:
    """Read KEY=value lines into the environment without overriding the shell."""
    target = Path(path) if path else Path.cwd() / ENV_NAME
    try:
        text = target.read_text()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
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


def load_env_near(start: str | Path) -> None:
    """Load the nearest .env at or above `start` (a game file or its folder)."""
    here = Path(start).resolve()
    if here.is_file():
        here = here.parent
    for folder in (here, *here.parents):
        candidate = folder / ENV_NAME
        if candidate.exists():
            load_env_file(candidate)
            return


def flag(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in ('0', 'no', 'off', 'false', '')


def number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def text(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()
