#!/usr/bin/env python3
"""Build the Pi desktop app with dpkg-deb (on Debian/Raspberry Pi OS)."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('dist'))
args = parser.parse_args()
source = Path(__file__).resolve().parents[1]
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
architecture = subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip()
minor = sys.version_info.minor
with tempfile.TemporaryDirectory(prefix='tick-package-') as temporary:
    root = Path(temporary)
    game = root / 'opt/tick-box-run'
    game.mkdir(parents=True)
    # Explicit allowlist: never ship wallets, credentials, local .env or caches.
    for path in source.glob('*.py'):
        shutil.copy2(path, game / path.name)
    for directory in ('games', 'markets', 'screens'):
        for path in (source / directory).glob('*.py'):
            destination = game / directory / path.name
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(path, destination)
    # Install testnet dependencies into the package, leaving system Python intact.
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-compile',
                    '--target', str(game / 'vendor'),
                    'eth-account==0.14.0', 'qrcode>=8,<9'], check=True)
    files = {
        'usr/bin/tick-box-run': 'tick-box-run',
        'usr/share/applications/tick-box-run.desktop': 'tick-box-run.desktop',
        'usr/share/icons/hicolor/scalable/apps/tick-box-run.svg': 'tick-box-run.svg',
    }
    for target, name in files.items():
        destination = root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / 'packaging' / name, destination)
    (root / 'usr/bin/tick-box-run').chmod(0o755)
    control = root / 'DEBIAN/control'
    control.parent.mkdir()
    control.write_text(f'''Package: tick-box-run
Version: 1.1.0
Section: games
Priority: optional
Architecture: {architecture}
Maintainer: TICK Team <maintainer@tick.invalid>
Depends: python3 (>= 3.{minor}), python3 (<< 3.{minor + 1}), python3-pygame (>= 2.5), python3-gpiozero, python3-lgpio, util-linux
Description: TICK BOX RUN handheld arcade
 A fullscreen 480x320 arcade game with rotary dial, touch and keyboard input.
 Uses Arc testnet USDC and live Coinbase prices by default.
 Includes testnet libraries and supports local environment overrides.
''')
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(root),
                    str(output / f'tick-box-run_1.1.0_{architecture}.deb')], check=True)
