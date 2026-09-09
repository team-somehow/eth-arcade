# ethonline-2026

TICK: a landscape **480×320** pygame crypto arcade for a Raspberry Pi handheld. **RUSH** is playable now: turn the side dial and you are in a leveraged market ride — no aim step, no confirm screen, just keep cranking. Prices are read-only and every position is paper; the USDC balance is demo money with the real deposit path stubbed out.

## Layout

| Path | What |
|------|------|
| [`firmware/`](firmware/) | Launcher + playable RUSH |
| [`design/`](design/) | Device renders, concept archive and actual game screenshots |

## Quick start

```bash
cd firmware
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

See [`firmware/README.md`](firmware/README.md) for controls and Pi/KMSDRM notes.

**On the device:** turning the dial forward opens and sustains a LONG, back a SHORT, and the flywheel it fills is your 1x–10x leverage. A short click opens the USDC loader; a long click bails out. On desktop, hold Up/Down to emulate a spun dial. See the [actual gameplay sheet](design/rush-build/gameplay-sheet.png).
