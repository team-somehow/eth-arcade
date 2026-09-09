# TICK / BOX RUN

Native pygame game for a **480×320 landscape** handheld. Runs on desktop for development and on the Pi's configured SDL display. No browser or network is needed.

## Run

```sh
cd firmware
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

If the existing venv already has pygame, simply run `.venv/bin/python main.py` from this directory. On Raspberry Pi, install the distribution's `python3-pygame` package and run `python3 main.py` with the panel configured. Existing display bootstrap may re-exec under system Python for KMSDRM support.

## Arrow-only controls

| Key | Action |
|---|---|
| Up / Down | Aim higher/lower; in SIZE, enlarge/shrink target |
| Right | Yellow button: play → size → review → lock; again after result |
| Left | Red button: back one setup step; home from aim/result |
| Enter / Space / X | Same as Right |
| Esc / Backspace / Z | Same as Left |
| W / S | Same as Up / Down |

Up/down can be held to repeat. Confirmation is not auto-repeated. In a committed round the target is locked, and input cannot change or cancel the bet; wait 20 seconds for the result. Closing the window still exits the program. The launcher uses Right to play and Left to quit.

Touch: the bottom left/right halves act as red/yellow buttons. During aim/size, tapping the upper/lower halves of the plot adjusts the selection. Mouse events synthesized from touch are ignored to avoid double actions.

Existing rotary encoder: GPIO21 CLK, GPIO20 DT, GPIO16 switch, 3.3V logic. Rotation maps to up/down through the existing adapter; short click = yellow, long click = red. Separate physical red/yellow GPIO buttons are not wired/configured by this change; arrow testing works now. Confirm actual switch wiring before adding GPIO mappings.

## Practice rules

Start with 100 practice credits. Every round costs 10 credits, deducted only at the final LOCK confirmation. Place the target, choose its height, and review the total return (including the stake) before committing. The **price at expiry** must fall inside the range; touching it earlier does not win. Boundary equality counts as inside.

Prices are **simulated**, not a live ETH feed. A fixed 10 Hz Gaussian random walk runs for 200 samples / 20 seconds. Target position/width influence the illustrative practice quote, not the sampled outcome. Outcomes are independent of rendering speed. Total return is capped at 100 practice credits. Balance and hit count persist when returning home, but reset on application restart. There is no real money, wallet, network request, blockchain settlement, automatic rebet or saved balance. An empty balance requires an explicit refill action.

Audio is synthesized locally and optional; a device without an audio output still plays. The whole frame is currently redrawn at a target 30 FPS. The SPI display may deliver less: benchmark on the actual Pi. This is not yet a partial-update display driver optimization.

## Tests and actual UI captures

```sh
cd firmware
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m unittest discover -s tests -v
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python capture_box_run.py
```

Captures go to `design/box-run-build/` at native 480×320. Tests cover arrow controls, launcher routing, boundary settlement, debit/payout idempotency, input locking, frame-rate independence, explicit refill, and rendering all states.

## Pi display note

`hardware.md` records a prior Pi 5 setup, including KMSDRM device index **2**. The actual Pi Zero 2 W may use another index. Set `SDL_VIDEO_KMSDRM_DEVICE_INDEX` for the connected panel when running without a desktop; do not assume that the Pi 5 card index applies. Display overlays, refresh rate, encoder direction and physical fit need on-device verification.
