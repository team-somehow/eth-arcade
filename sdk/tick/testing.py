"""Play a thousand rounds in a second, with no window and no waiting.

A game that settles money has rules -- what it refuses to sell, what it pays,
what it does when the feed dies -- and rules that are only ever eyeballed are
rules that are wrong. The harness here runs your real game class against a real
market and a real wallet, on a clock you control, with no display.

    from tick.testing import Harness

    def test_a_box_on_spot_pays_about_two():
        h = Harness(MyGame(), source='sim', seed=7)
        h.advance(30)                          # 30 seconds of market
        bet = h.ctx.bet(h.ctx.price - 1, h.ctx.price + 1)
        assert 1.5 < bet.multiple < 3.0
        h.advance(20)                          # past two bells
        assert h.ctx.book.history[0].stake == h.ctx.stake

Time is fake and monotonic, so `advance(600)` is instant and deterministic.
Seed the simulated feed and the same market comes back every run: that is what
makes a payout assertion an assertion.
"""
from __future__ import annotations

from .feeds.sim import SimulatedFeed
from .game import Game
from .input import InputAction
from .money import MICRO, DemoFunding, Wallet
from .runtime import Runtime


class FakeClock:
    """A monotonic clock you move by hand."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


class ScriptedFeed:
    """A feed that yields exactly the ticks you list.

        ScriptedFeed([(0.0, 2500.0), (1.0, 2501.0), (2.0, 2501.0)])

    Use it when a test is about a specific shape of market -- a jump, a gap, a
    dead flat minute -- rather than about a plausible one.
    """

    name = 'SCRIPTED'

    def __init__(self, rows, asset=None, source_age: float = 0.0) -> None:
        from .ticks import ASSETS, PriceTick
        self.asset = asset or ASSETS['eth']
        self.status = 'Scripted'
        self._PriceTick = PriceTick
        self.rows = sorted(rows)
        self.index = 0
        self.elapsed = 0.0
        self.sequence = 0
        self.source_age = source_age

    def poll(self, dt: float, now: float):
        self.elapsed += max(0.0, dt)
        out = []
        while self.index < len(self.rows) and self.rows[self.index][0] <= self.elapsed:
            _, price = self.rows[self.index][:2]
            self.index += 1
            self.sequence += 1
            out.append(self._PriceTick(price, self.sequence, now, self.source_age))
        return out

    def close(self) -> None:
        pass


class Harness:
    """A game, running headless, on a clock you control."""

    FRAME = 1 / 30

    def __init__(self, game: Game, *, feed=None, source: str = 'sim', seed: int | None = 7,
                 balance: int = 1000 * MICRO, stake: int | None = None,
                 window_s: float | None = None, start: float = 1000.0) -> None:
        self.clock = FakeClock(start)
        wallet = Wallet(balance, DemoFunding())
        if feed is None and source == 'sim':
            from .ticks import current_asset
            feed = SimulatedFeed(seed, current_asset())
        self.runtime = Runtime(game, feed=feed, wallet=wallet, source=source, seed=seed,
                               headless=True, clock=self.clock, window_s=window_s,
                               stake=stake, env=False)
        self.game = game
        self.ctx = self.runtime.ctx
        self.market = self.runtime.market
        self.wallet = wallet
        self.rounds = self.runtime.rounds
        self.book = self.runtime.book
        game.setup(self.ctx)
        self.runtime.started = True

    # ---- driving ---------------------------------------------------------
    def frame(self, dt: float | None = None, actions=(), touches=()) -> None:
        dt = self.FRAME if dt is None else dt
        self.clock.advance(dt)
        self.runtime.step(dt, actions, touches)

    def advance(self, seconds: float, dt: float | None = None) -> None:
        """Run `seconds` of game time, one frame at a time."""
        dt = self.FRAME if dt is None else dt
        steps = max(1, int(round(seconds / dt)))
        for _ in range(steps):
            self.frame(dt)

    def press(self, action: InputAction | str = InputAction.A) -> None:
        if isinstance(action, str):
            action = InputAction[action.upper()]
        self.frame(actions=[action])

    def touch(self, pos: tuple[int, int]) -> None:
        self.frame(touches=[pos])

    def warm(self, seconds: float = 20.0) -> 'Harness':
        """Run until the market is readable and the clock is rolling."""
        self.advance(seconds)
        return self

    def close(self) -> None:
        self.runtime.close()

    def __enter__(self) -> 'Harness':
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ---- reading ---------------------------------------------------------
    @property
    def price(self) -> float:
        return self.market.price

    @property
    def balance(self) -> int:
        return self.wallet.balance

    @property
    def settled(self):
        return self.book.history

    def draw_once(self) -> None:
        """Render one frame to an off-screen surface: catches a broken `draw`.

        Needs pygame and a dummy video driver:
        `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest`
        """
        import pygame
        from .display import HEIGHT, WIDTH
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((WIDTH, HEIGHT))
        surface = pygame.Surface((WIDTH, HEIGHT))
        self.ctx.screen = surface
        self.game.draw(self.ctx, surface)
