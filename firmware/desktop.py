"""Packaged desktop entry: local settings, live defaults, persistent wallet."""
from pathlib import Path
import os

from envfile import load_env_file


def configure() -> None:
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    load_env_file(Path(os.environ.get('TICK_CONFIG_FILE', config / 'tick-box-run/.env')))
    defaults = {
        'TICK_GAME': 'box', 'TICK_FUNDING': 'arc-testnet',
        'TICK_MARKET_SOURCE': 'coinbase', 'TICK_ASSET': 'eth',
        'TICK_STAKE_USDC': '0.001', 'TICK_SCOREKEEPER': '0',
        'TICK_DATA_DIR': str(data / 'tick-box-run/.tick'),
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


if __name__ == '__main__':
    configure()
    from main import main
    main()
