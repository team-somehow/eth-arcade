# ethonline-2026

TICK: a landscape **480×320** pygame crypto arcade for a Raspberry Pi handheld. **BOX RUN** is playable now with arrow keys, touch or the existing encoder adapter. All betting uses clearly labeled simulated prices and practice credits.

## Layout

| Path | What |
|------|------|
| [`firmware/`](firmware/) | Launcher + playable BOX RUN |
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

**Arrows only:** Up/Down aim or resize; Right confirms; Left goes back. A round lasts 20 seconds after final confirmation. Enter/Escape also work. See the [actual gameplay sheet](design/box-run-build/gameplay-sheet.png).
