# Raspberry Pi app

Build on the target Raspberry Pi OS / Debian (requires python3-pip):

```sh
python3 firmware/packaging/build_deb.py --output dist
sudo apt install ./dist/tick-box-run_1.1.0_arm64.deb
```

The package bundles the Arc/ENS/QR libraries for the build machine's Python and
architecture. SDL/pygame and GPIO come from Raspberry Pi OS. No keys or local
settings are bundled. Launch **TICK BOX RUN** from Games or copy the executable
`/usr/share/applications/tick-box-run.desktop` to the Desktop folder.

Defaults are **Arc testnet USDC**, **live Coinbase ETH prices**, and **0.001 USDC
per press**. There is no starting paper balance or automatic simulated fallback.
Use LOAD USDC to fund the displayed device address.

Edit `~/.config/tick-box-run/.env` and relaunch to change settings:

```dotenv
TICK_FUNDING=arc-testnet
TICK_MARKET_SOURCE=coinbase
TICK_STAKE_USDC=0.001
# Optional: reuse an existing device wallet and saved session (absolute path).
# TICK_DATA_DIR=/home/jovian/tick-boxrun/.tick
```

To use paper play later, set `TICK_FUNDING=demo` and `TICK_MARKET_SOURCE=sim`.
Shell environment variables override the local file. `TICK_CONFIG_FILE` selects
an alternate config. New installations store their wallet under
`~/.local/share/tick-box-run/.tick`; keep this directory across upgrades.

Turn the dial to aim; yellow / dial click buys; red / long dial click returns.
Keyboard: Up/Down aim, Enter buys, Escape exits. Only one app instance runs at a
time. Logs: `~/.local/state/tick-box-run/game.log`.
Uninstall: `sudo apt remove tick-box-run` (wallet and settings remain).
