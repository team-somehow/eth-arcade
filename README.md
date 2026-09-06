# ethonline-2026

Handheld firmware experiments for a [Playdate](https://play.date/)-inspired device: landscape **480×320**, pygame UI, touch + D-pad.

## Layout

| Path | What |
|------|------|
| [`firmware/`](firmware/) | Bare-minimum home launcher (clock + game list) |

## Quick start

```bash
cd firmware
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

See [`firmware/README.md`](firmware/README.md) for controls and Pi/KMSDRM notes.
