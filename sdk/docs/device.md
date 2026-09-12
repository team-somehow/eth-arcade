# The device

480×320 landscape, a rotary dial, two buttons, a speaker. Everything here is
handled for you; this page is what to do when it is not.

---

## The canvas

Your game draws on a **480×320 landscape surface** and never thinks about the
display again. If the panel underneath is portrait — a 320×480 SPI screen, say
— each finished frame is turned onto it, and touch positions are turned back
the other way so a tap lands where the player pointed.

```bash
TICK_ROTATE=auto     # turn only when the screen is portrait, and only on Linux
TICK_ROTATE=90       # force it
```

That seam earns its keep: a game written against a rotating canvas has rotation
maths smeared through its draw code *and* its input code, and it is wrong in a
different way on every device.

```python
from tick.display import WIDTH, HEIGHT, FPS     # 480, 320, 30
```

On a desktop the game opens in a plain 480×320 window; only Linux gets the
fullscreen panel.

---

## Controls

Four actions. A dial, two buttons, a keyboard and a touchscreen all collapse
into them — which is the only reason a game is testable at all.

| Action | Dial | Panel | Keyboard | Touch |
|---|---|---|---|---|
| `UP` / `DOWN` | turn | — | ↑ ↓ / W S (hold to spin) | tap above / below |
| `A` | short click | yellow | Enter · Space · → · X | — |
| `B` | long click (0.65 s) | red | Backspace · ← · Z | — |
| `QUIT` | — | — | Escape | window close |

### Wiring (BCM numbering, not header position)

```
encoder   CLK  GPIO21 (pin 40)
          DT   GPIO20 (pin 38)
          SW   GPIO16 (pin 36)
          VCC  3.3 V      GND  GND

red     GPIO13 (pin 33) ── button ── GND (pin 34 or 39)     back / B
yellow  GPIO26 (pin 37) ── button ── GND (pin 34 or 39)     go / A
```

Each button shorts its pin to ground against the internal pull-up; nothing else
is needed in hardware. Presses are edge-triggered, so holding repeats nothing,
and a button already held when the game starts is ignored rather than firing on
the first frame.

Both readers are `try_open()`: on a machine with no GPIO they return `None` and
the game plays on the keyboard rather than refusing to start.

### Why the dial is read two ways

```python
encoder.poll(continuous=True)     # in play: this poll's motion only
encoder.poll(continuous=False)    # in menus: rate-limited
```

In play, every detent counts and a stopped crank must stop moving the box at
once — so queued motion is discarded. In a menu, a whip-spin would otherwise
wrap the list a dozen times, so it is rate-limited to one step per 50 ms.

---

## Sound

Everything is synthesized at startup from square waves — no audio assets, no
dependencies, about 0.16 s to build. See the cue list in
[api.md](api.md#tickhud-and-tickui).

Sound is optional **by construction**: if the mixer cannot open, every `play`
and `music` becomes a no-op and the game runs silently. It never raises.

```bash
TICK_SOUND=0        # off
```

### On a Raspberry Pi 5

There is no analog jack, so ALSA alone offers only the two HDMI outputs, and
opening one fails with nothing connected. Sound works through the
**pipewire-pulse** server instead. Do not force `SDL_AUDIODRIVER=alsa`: it
bypasses the sound server and finds only the dead HDMI sinks.

Bluetooth adds 100–200 ms of latency, so crank clicks trail the dial. A USB
audio dongle is tighter. An I²S DAC is tightest, but it wants GPIO18/19/21 —
and GPIO21 is the encoder's CLK, so the encoder has to move first.

---

## Running on the Pi

```python
from tick.display import bootstrap
bootstrap()        # run() calls this for you, before pygame is imported
```

It does two things, both of which are the difference between a working panel
and a black one:

* Sets `SDL_VIDEODRIVER=kmsdrm` when nothing already owns the display (a
  running Wayland or X11 session is preferred and left alone).
* Re-execs under the **system** Python if the active pygame came from pip. The
  pip wheel has no KMSDRM support, so without this the game opens on nothing.

The panel's DRM card index varies by board. Set it for yours rather than
trusting a default:

```bash
SDL_VIDEO_KMSDRM_DEVICE_INDEX=2 python mygame.py
```

Install the distribution's `python3-pygame` on the Pi rather than the wheel.

---

## Headless

For tests, captures and CI:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -t .
```

`Harness` needs neither; only `Harness.draw_once()` touches pygame at all.
