# Playdate-like Home Launcher

Bare-minimum pygame UI scaffold: landscape **480×320**, 1-bit look, home launcher with clock + game list. Supports **touch** and **D-pad** (keyboard on desktop).

Inspired by [Playdate](https://play.date/); display bootstrap follows the BetterWallet Pi pygame pattern (KMSDRM-ready on Linux).

## Run (desktop)

```bash
cd firmware
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Controls

| Action | Keyboard | Touch |
|--------|----------|-------|
| Navigate | ↑/↓ or W/S | Tap a list row to focus |
| Launch (A) | Enter, Space, or X | Tap the focused row again |
| Back / Quit (B) | Esc, Z, or Backspace | Tap anywhere on a launched game |

On the home screen, **B** quits. On a launched stub, **B** (or tap) returns home.

## Layout

- Status bar: product name + live clock
- Focusable list: Demo Game, Blank App, Settings (stub)
- Footer control hints
- Placeholder game screen when you press A

## Pi note

On Raspberry Pi with a Waveshare-style panel, use apt `python3-pygame` for KMSDRM. `display_setup.ensure_system_pygame()` re-execs under system Python when a venv pip pygame lacks DRM support (Linux only).
