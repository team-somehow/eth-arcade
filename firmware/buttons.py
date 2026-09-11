"""Red and yellow panel buttons on GPIO → InputAction.

Wiring (BCM numbering, not header position):

    RED     GPIO13  (header pin 33) ── button ── GND (pin 34 or 39)
    YELLOW  GPIO26  (header pin 37) ── button ── GND (pin 34 or 39)

Each button shorts its pin to ground, so the internal pull-up holds the line
high until it is pressed. Nothing else is needed in hardware.

The mapping matches the footer the games already draw: the red dot on the left
is "back", the yellow dot on the right is "go". The encoder's own click still
works, so a device with no buttons wired loses nothing.
"""

from __future__ import annotations

from typing import Callable

from input import InputAction

# BCM pin map for this handheld
RED_PIN = 13
YELLOW_PIN = 26

# Mechanical switches chatter for a few milliseconds on contact.
BOUNCE_S = 0.03


class ButtonPad:
    """Poll-based reader for the two panel buttons. Call once per frame."""

    def __init__(self, red: object, yellow: object) -> None:
        self._buttons = ((red, InputAction.B), (yellow, InputAction.A))
        # Read the resting state now: a button already held at startup must not
        # fire on the first frame.
        self._down = {
            id(button): bool(getattr(button, 'is_pressed', False))
            for button, _ in self._buttons
        }

    @classmethod
    def try_open(cls, red: int = RED_PIN, yellow: int = YELLOW_PIN) -> ButtonPad | None:
        """Open both pins, or return None on a machine without GPIO."""
        try:
            from gpiozero import Button, Device
            from gpiozero.pins.lgpio import LGPIOFactory
        except ImportError:
            return None

        try:
            if Device.pin_factory is None:
                Device.pin_factory = LGPIOFactory(chip=0)
            pins = [Button(pin, pull_up=True, bounce_time=BOUNCE_S)
                    for pin in (red, yellow)]
        except Exception:
            # A pin already claimed by an overlay, or no permission: play on
            # with the encoder rather than refusing to start.
            return None

        return cls(*pins)

    def poll(self) -> list[InputAction]:
        """Actions for presses since the last call. Holding repeats nothing."""
        actions: list[InputAction] = []
        for button, action in self._buttons:
            pressed = bool(button.is_pressed)
            if pressed and not self._down[id(button)]:
                actions.append(action)
            self._down[id(button)] = pressed
        return actions

    def close(self) -> None:
        close: Callable[[], None] | None
        for button, _ in self._buttons:
            close = getattr(button, 'close', None)
            if close is not None:
                try:
                    close()
                except Exception:
                    pass
