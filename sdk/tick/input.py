"""Four actions. That is the whole controller.

    UP / DOWN   the dial, one detent
    A           go / buy / confirm
    B           back / cancel
    QUIT        leave

A rotary encoder, two panel buttons, a keyboard and a touchscreen all collapse
into those four, so a game written on a laptop runs on the handheld with no
input code changed. That is the only reason a game is testable at all: you
cannot unit-test a thumb on a dial, but you can feed a list of `InputAction`.

Hardware (BCM numbering, not header position -- this is where it usually goes
wrong):

    encoder  CLK=GPIO21 (pin 40)  DT=GPIO20 (pin 38)  SW=GPIO16 (pin 36)
    red      GPIO13 (pin 33) -> button -> GND     back / B
    yellow   GPIO26 (pin 37) -> button -> GND     go / A

Both readers are `try_open()`: on a machine with no GPIO they return None and
the game plays on the keyboard instead of refusing to start.
"""
from __future__ import annotations

from enum import Enum, auto
import time
from typing import Callable

from .display import display_to_canvas, to_canvas


class InputAction(Enum):
    UP = auto()
    DOWN = auto()
    A = auto()
    B = auto()
    QUIT = auto()


# ---- keyboard and touch --------------------------------------------------
def event_position(event) -> tuple[int, int] | None:
    """Canvas pixels of a tap or click, or None if the event is neither."""
    import pygame
    if event.type == pygame.MOUSEBUTTONDOWN:
        if getattr(event, 'touch', False) or event.button != 1:
            return None
        return display_to_canvas(event.pos)
    if event.type == pygame.FINGERDOWN:
        # Finger positions are fractions of the display, which may be turned.
        return to_canvas(event.x, event.y)
    return None


def actions_from_event(event) -> list[InputAction]:
    """A pygame event to zero or more actions. Position is not converted here."""
    import pygame
    if event.type == pygame.QUIT:
        return [InputAction.QUIT]
    if event.type != pygame.KEYDOWN:
        return []
    key = event.key
    # Escape always leaves the program, from any screen, mid-round included.
    if key == pygame.K_ESCAPE:
        return [InputAction.QUIT]
    if key in (pygame.K_UP, pygame.K_w):
        return [InputAction.UP]
    if key in (pygame.K_DOWN, pygame.K_s):
        return [InputAction.DOWN]
    if key in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_SPACE, pygame.K_x):
        return [InputAction.A]
    if key in (pygame.K_LEFT, pygame.K_z, pygame.K_BACKSPACE):
        return [InputAction.B]
    return []


class HeldKeys:
    """Held Up/Down on a desktop emulates a spun dial.

    Without this, developing on a laptop means tapping a key forty times to
    move a bet across the ladder, and the game feels wrong in a way that has
    nothing to do with the game.
    """

    FIRST_S = 0.12      # pause before a held key starts repeating
    REPEAT_S = 0.05     # then one detent this often

    def __init__(self) -> None:
        self.held: dict[int, float] = {}

    def handle(self, event) -> None:
        import pygame
        if event.type == pygame.WINDOWFOCUSLOST:
            self.held.clear()
        elif event.type == pygame.KEYDOWN and event.key in (
                pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
            self.held[event.key] = self.FIRST_S
        elif event.type == pygame.KEYUP:
            self.held.pop(event.key, None)

    def tick(self, dt: float) -> list[InputAction]:
        import pygame
        out: list[InputAction] = []
        for key in list(self.held):
            self.held[key] -= dt
            if self.held[key] <= 0:
                out.append(InputAction.UP if key in (pygame.K_UP, pygame.K_w)
                           else InputAction.DOWN)
                if key in self.held:
                    self.held[key] = self.REPEAT_S
        return out

    def clear(self) -> None:
        self.held.clear()


# ---- GPIO ----------------------------------------------------------------
CLK_PIN, DT_PIN, SW_PIN = 21, 20, 16
RED_PIN, YELLOW_PIN = 13, 26
LONG_PRESS_S = 0.65
STEPS_PER_CLICK = 1
MIN_NAV_INTERVAL_S = 0.05
BOUNCE_S = 0.03


def _pin_factory():
    from gpiozero import Device
    from gpiozero.pins.lgpio import LGPIOFactory
    if Device.pin_factory is None:
        Device.pin_factory = LGPIOFactory(chip=0)


class EncoderInput:
    """Rotary encoder: turn -> UP/DOWN, click -> A, hold -> B.

    `poll(continuous=True)` in play reports **this poll's motion only** and
    never queues old turns, so a stopped crank stops moving the bet at once.
    `continuous=False` in menus rate-limits instead, so a whip-spin scrolls a
    list smoothly rather than wrapping it a dozen times.
    """

    def __init__(self, encoder, button, *, invert: bool = False) -> None:
        self._encoder = encoder
        self._button = button
        self._invert = invert
        self._last_steps = int(getattr(encoder, 'steps', 0))
        self._pending = 0
        self._was_pressed = bool(getattr(button, 'is_pressed', False))
        self._press_at = 0.0
        self._last_nav_at = 0.0

    @classmethod
    def try_open(cls, clk: int = CLK_PIN, dt: int = DT_PIN, sw: int = SW_PIN,
                 invert: bool = False) -> 'EncoderInput | None':
        try:
            from gpiozero import Button, RotaryEncoder
        except ImportError:
            return None
        try:
            _pin_factory()
            # max_steps=0 is unlimited; the default of 16 clamps and appears to
            # "break" after a fast spin one way. No bounce_time: mechanical
            # filtering drops edges when the dial is spun hard.
            encoder = RotaryEncoder(clk, dt, bounce_time=None, max_steps=0)
            button = Button(sw, pull_up=True, bounce_time=0.05)
        except Exception:
            return None
        return cls(encoder, button, invert=invert)

    def poll(self, *, continuous: bool = False) -> list[InputAction]:
        actions: list[InputAction] = []
        now = time.monotonic()
        steps = int(self._encoder.steps)
        delta = steps - self._last_steps
        self._last_steps = steps
        if continuous:
            self._pending = 0
            if self._invert:
                delta = -delta
            if delta:
                action = InputAction.UP if delta > 0 else InputAction.DOWN
                actions.extend([action] * min(16, abs(delta)))
        elif delta:
            if self._invert:
                delta = -delta
            self._pending += delta
            if abs(self._pending) >= STEPS_PER_CLICK and now - self._last_nav_at >= MIN_NAV_INTERVAL_S:
                if self._pending > 0:
                    actions.append(InputAction.DOWN)
                    self._pending -= STEPS_PER_CLICK
                else:
                    actions.append(InputAction.UP)
                    self._pending += STEPS_PER_CLICK
                self._last_nav_at = now
            # Direction reversed: drop leftover chatter from the other way.
            if actions and ((actions[-1] == InputAction.DOWN and self._pending < 0)
                            or (actions[-1] == InputAction.UP and self._pending > 0)):
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
        for device in (self._encoder, self._button):
            closer: Callable[[], None] | None = getattr(device, 'close', None)
            if closer is not None:
                try:
                    closer()
                except Exception:
                    pass


class ButtonPad:
    """The two panel buttons. Edge-triggered: holding one repeats nothing, and
    one already held when the game starts is ignored rather than firing on the
    first frame."""

    def __init__(self, red, yellow) -> None:
        self._buttons = ((red, InputAction.B), (yellow, InputAction.A))
        self._down = {id(b): bool(getattr(b, 'is_pressed', False)) for b, _ in self._buttons}

    @classmethod
    def try_open(cls, red: int = RED_PIN, yellow: int = YELLOW_PIN) -> 'ButtonPad | None':
        try:
            from gpiozero import Button
        except ImportError:
            return None
        try:
            _pin_factory()
            pins = [Button(pin, pull_up=True, bounce_time=BOUNCE_S) for pin in (red, yellow)]
        except Exception:
            # A pin already claimed by an overlay, or no permission: play on
            # with the encoder rather than refusing to start.
            return None
        return cls(*pins)

    def poll(self) -> list[InputAction]:
        actions: list[InputAction] = []
        for button, action in self._buttons:
            pressed = bool(button.is_pressed)
            if pressed and not self._down[id(button)]:
                actions.append(action)
            self._down[id(button)] = pressed
        return actions

    def close(self) -> None:
        for button, _ in self._buttons:
            closer = getattr(button, 'close', None)
            if closer is not None:
                try:
                    closer()
                except Exception:
                    pass
