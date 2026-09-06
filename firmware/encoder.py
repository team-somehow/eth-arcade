"""Rotary encoder on GPIO → InputAction (turn = UP/DOWN, click = A, hold = B).

Wiring (BCM): CLK=21, DT=20, SW=16, VCC=3.3V, GND=GND.
Uses system gpiozero/lgpio (available after display_setup re-exec on Pi).
"""

from __future__ import annotations

import time
from typing import Callable

from input import InputAction

# BCM pin map for this handheld
CLK_PIN = 21
DT_PIN = 20
SW_PIN = 16

LONG_PRESS_S = 0.65
# Ignore sub-detent chatter; KY-040 often reports 1–2 gpiozero steps per click.
STEPS_PER_CLICK = 1
# Don't emit more than one nav action this often (fast spin = steady scroll).
MIN_NAV_INTERVAL_S = 0.05


class EncoderInput:
    """Poll-based encoder reader. Safe to call each frame from the pygame loop."""

    def __init__(
        self,
        encoder: object,
        button: object,
        *,
        invert: bool = False,
    ) -> None:
        self._encoder = encoder
        self._button = button
        self._invert = invert
        self._last_steps = int(getattr(encoder, "steps", 0))
        self._pending = 0  # accumulated signed steps toward next click
        self._was_pressed = bool(getattr(button, "is_pressed", False))
        self._press_at = 0.0
        self._last_nav_at = 0.0

    @classmethod
    def try_open(
        cls,
        clk: int = CLK_PIN,
        dt: int = DT_PIN,
        sw: int = SW_PIN,
        invert: bool = False,
    ) -> EncoderInput | None:
        try:
            from gpiozero import Button, Device, RotaryEncoder
            from gpiozero.pins.lgpio import LGPIOFactory
        except ImportError:
            return None

        try:
            if Device.pin_factory is None:
                Device.pin_factory = LGPIOFactory(chip=0)
            # max_steps=0 → unlimited. The default of 16 clamps and "breaks"
            # after a fast spin in one direction.
            # No bounce_time: mechanical filtering drops edges when spun fast.
            encoder = RotaryEncoder(clk, dt, bounce_time=None, max_steps=0)
            button = Button(sw, pull_up=True, bounce_time=0.05)
        except Exception:
            return None

        return cls(encoder, button, invert=invert)

    def poll(self) -> list[InputAction]:
        actions: list[InputAction] = []
        now = time.monotonic()

        steps = int(self._encoder.steps)
        delta = steps - self._last_steps
        self._last_steps = steps
        if delta:
            if self._invert:
                delta = -delta
            self._pending += delta

            # Emit at most one nav action per interval so a whip-spin scrolls
            # smoothly instead of wrapping the list dozens of times.
            while abs(self._pending) >= STEPS_PER_CLICK:
                if now - self._last_nav_at < MIN_NAV_INTERVAL_S:
                    # Keep residual steps (don't discard) but wait to fire.
                    break
                if self._pending > 0:
                    actions.append(InputAction.DOWN)
                    self._pending -= STEPS_PER_CLICK
                else:
                    actions.append(InputAction.UP)
                    self._pending += STEPS_PER_CLICK
                self._last_nav_at = now
                now = time.monotonic()
                # One action per poll keeps the UI in sync with a single frame.
                break

            # Direction reverse: drop leftover chatter from the other way.
            if actions and (
                (actions[-1] == InputAction.DOWN and self._pending < 0)
                or (actions[-1] == InputAction.UP and self._pending > 0)
            ):
                self._pending = 0

        pressed = bool(self._button.is_pressed)
        if pressed and not self._was_pressed:
            self._press_at = now
        elif not pressed and self._was_pressed:
            held = now - self._press_at
            actions.append(InputAction.B if held >= LONG_PRESS_S else InputAction.A)
        self._was_pressed = pressed

        return actions

    def close(self) -> None:
        close: Callable[[], None] | None
        for device in (self._encoder, self._button):
            close = getattr(device, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass
