# ethonline-2026

TICK: a landscape **480×320** pygame crypto arcade for a Raspberry Pi handheld. **BOX RUN** is playable now: a box on the ETH price ladder and a 20-second clock that never stops — crank the dial to move the box, press A to buy the next 20 seconds. Prices are read-only. Money is paper by default; with `TICK_FUNDING=arc-testnet` it is real Arc testnet USDC: send it to the QR code on the device, play, and cash out back to the wallet it came from, through the [`TickEscrow`](contracts/) contract.

## Layout

| Path | What |
|------|------|
| [`firmware/`](firmware/) | Launcher + playable BOX RUN |
| [`design/`](design/) | Device renders, concept archive and actual game screenshots |
| [`contracts/`](contracts/) | `TickEscrow`: USDC session escrow on Arc, with the owner as the house. Testnet: [`0x4FA3…8627`](https://testnet.arcscan.app/address/0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627) |

## Quick start

```bash
cd firmware
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

See [`firmware/README.md`](firmware/README.md) for controls and Pi/KMSDRM notes.

**On the device:** the dial moves your box up and down the price ladder; a short click buys the next 20 seconds (+10 USDC), pressing again adds more to the same box. Distance from spot sets the payout, priced from measured live volatility. On desktop, hold Up/Down to emulate a spun dial and press Escape to quit. See the [actual gameplay sheet](design/box-run-live/gameplay-sheet.png).
