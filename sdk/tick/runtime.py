"""The loop you do not have to write.

`run(MyGame())` starts everything in the right order and shuts it down in the
reverse one:

    .env -> SDL bootstrap -> display -> feed -> wallet/escrow -> round clock
         -> sound -> your setup() -> 30 FPS loop -> teardown -> close it all

Inside each frame, in this order, and the order matters:

    1. read the feed, fold every tick into the market
    2. start the clock on the first price; roll it if a bell has passed
    3. settle the bets on any round that closed, and pay out
    4. play the generic cues (bell, crossings, countdown, win/miss, stale)
    5. hand input to your game
    6. your update(), then your draw()

Prices before the clock, because the clock settles on a price. Settlement
before input, because a press arriving in the same frame as a bell belongs to
the round that is now open, not the one that just closed. Draw last, because
everything above may have changed what is on screen.

Headless
--------

`Runtime.step()` is the whole frame minus pygame, so a test can drive a
thousand rounds in a second with no window, no sound and no sleeping. That is
what `tick.testing` is built on -- and it is why the rules in this SDK are
tested rather than eyeballed.
"""
from __future__ import annotations

import os
import sys
import time

from .bets import BetBook
from .env import flag, load_env_near, number
from .game import Game, GameContext
from .market import Market
from .money import Wallet, stake_micro
from .rounds import RoundClock


class Runtime:
    """Owns everything with a lifetime longer than a frame."""

    COUNTDOWN_S = 3.0        # pitched ticks this close to the bell

    def __init__(self, game: Game, *, feed=None, wallet: Wallet | None = None,
                 source: str | None = None, seed: int | None = None,
                 sound: bool | None = None, clock=None, headless: bool = False,
                 window_s: float | None = None, stake: int | None = None,
                 env: bool = True) -> None:
        if env:
            # The nearest .env to the game's own file, so a game in a folder
            # carries its own settings. Falls back to the working directory for
            # a game defined in a REPL or a notebook, which has no file.
            module = sys.modules.get(type(game).__module__)
            load_env_near(getattr(module, '__file__', None) or os.getcwd())
        self.game = game
        self.headless = headless
        self.clock_fn = clock or time.monotonic
        self.market = Market(feed=feed, source=source, seed=seed)
        self.wallet = wallet if wallet is not None else self._build_wallet()
        self.rounds = RoundClock(window_s if window_s is not None
                                 else number('TICK_WINDOW_S', game.window_s))
        self.book = BetBook(self.wallet)
        self.sounds = None
        if not headless and (sound if sound is not None else flag('TICK_SOUND', True)):
            from .ui import Sounds
            self.sounds = Sounds()
        self.ctx = GameContext(game, self.market, self.wallet, self.rounds, self.book,
                               self.sounds, stake if stake is not None
                               else stake_micro(game.stake_usdc))
        self.screen = None
        # cue state
        self._was_inside: bool | None = None
        self._was_fresh = True
        self._last_countdown: tuple | None = None
        self.started = False

    def _build_wallet(self) -> Wallet:
        from .escrow import build_wallet
        return build_wallet()

    # ---- one frame, without pygame ---------------------------------------
    def step(self, dt: float, actions=(), touches=()) -> None:
        ctx = self.ctx
        ctx.now = self.clock_fn()
        ctx.dt = dt
        ctx.frame += 1
        game = self.game

        # 1. prices
        for tick in self.market.poll(dt, ctx.now):
            if not self.rounds.started:
                opened = self.rounds.start(tick.price, ctx.now)
                game.on_round_start(ctx, opened)
            game.on_tick(ctx, tick)

        # 2-3. the clock, and settlement
        if self.rounds.started:
            settleable = (self.market.tick is not None
                          and self.market.tick.received_at >= self.rounds.ends_at
                          and self.market.fresh(ctx.now))
            for closed in self.rounds.update(ctx.now, self.market.price, settleable):
                settlements = self.book.settle(closed)
                ctx.armed_at = ctx.now + game.arm_s
                self._result_cues(settlements)
                game.on_round_end(ctx, closed)
                for settlement in settlements:
                    game.on_settle(ctx, settlement)
                if self.rounds.current is not None:
                    game.on_round_start(ctx, self.rounds.current)

        # 4. the cues every game wants and nobody should have to write
        if game.sound_cues:
            self._cues()
        if game.music:
            self._music()

        # 5. input
        for pos in touches:
            if game.on_touch(ctx, pos) == 'quit':
                ctx.running = False
        for action in actions:
            if action.name == 'QUIT':
                ctx.running = False
                break
            if game.on_action(ctx, action) == 'quit':
                ctx.running = False
                break

        # 6. the game's own frame
        game.update(ctx, dt)

    # ---- generic sound ---------------------------------------------------
    def _result_cues(self, settlements) -> None:
        if self.sounds is None:
            return
        if not settlements:
            # The empty-round heartbeat. A result speaks for the bell instead.
            self.sounds.play('bell')
            return
        best = max(settlements, key=lambda s: (s.hit, s.multiple))
        if best.voided:
            self.sounds.play('void')
        elif best.hit:
            self.sounds.play('jackpot' if best.multiple >= 15
                             else 'win_big' if best.multiple >= 5 else 'win_small')
        else:
            self.sounds.play('miss')

    def _cues(self) -> None:
        if self.sounds is None:
            return
        ctx = self.ctx
        # Crossing into or out of a live bet is the whole tension of a round,
        # so it gets a sound of its own in each direction.
        inside = ctx.inside
        if inside is not None and self._was_inside is not None and inside != self._was_inside:
            self.sounds.play('hot' if inside else 'cold')
        self._was_inside = inside
        # Last seconds: ticks pitched by whether the money is currently winning,
        # and doubling in rate inside the final two, so the bell rushes at you.
        left = ctx.remaining
        slot = ('s', int(left)) if left > 2 else ('h', int(left * 2))
        if inside is not None and 0 < left <= self.COUNTDOWN_S and slot != self._last_countdown:
            self.sounds.play('tick_in' if inside else 'tick_out')
        self._last_countdown = slot
        fresh = self.market.fresh(ctx.now)
        if self._was_fresh and not fresh:
            self.sounds.play('stale')
        self._was_fresh = fresh

    def _music(self) -> None:
        if self.sounds is None:
            return
        ctx = self.ctx
        if ctx.live_bets:
            self.sounds.music('final' if ctx.remaining <= 3 else 'live')
        elif ctx.next_bets:
            self.sounds.music('live')
        else:
            self.sounds.music('idle')

    # ---- the pygame loop -------------------------------------------------
    def run(self) -> None:
        from .display import FPS, bootstrap, init_display, present
        bootstrap()
        import pygame
        from .input import ButtonPad, EncoderInput, HeldKeys, actions_from_event, event_position

        self.screen = init_display(self.game.title)
        self.ctx.screen = self.screen
        clock = pygame.time.Clock()
        keys = HeldKeys()
        encoder = EncoderInput.try_open()
        pad = ButtonPad.try_open()
        self.game.setup(self.ctx)
        self.started = True
        try:
            while self.ctx.running:
                dt = clock.tick(FPS) / 1000.0
                actions, touches = [], []
                for event in pygame.event.get():
                    keys.handle(event)
                    actions.extend(actions_from_event(event))
                    pos = event_position(event)
                    if pos is not None:
                        touches.append(pos)
                actions.extend(keys.tick(dt))
                if encoder is not None:
                    # In play every detent counts, so read raw motion.
                    actions.extend(encoder.poll(continuous=True))
                if pad is not None:
                    actions.extend(pad.poll())
                self.step(dt, actions, touches)
                if not self.ctx.running:
                    break
                self.game.draw(self.ctx, self.screen)
                present()
        finally:
            self.close()
            if encoder is not None:
                encoder.close()
            if pad is not None:
                pad.close()
            pygame.quit()

    def close(self) -> None:
        if self.started:
            try:
                self.game.teardown(self.ctx)
            except Exception:      # a broken teardown must not strand the feed
                pass
        if self.sounds is not None:
            self.sounds.music('off')
        self.market.close()
        stop = getattr(self.wallet.funding, 'stop', None)
        if stop is not None:
            stop()


def run(game: Game, **kwargs) -> None:
    """Start a game and block until it quits. This is the whole entry point."""
    Runtime(game, **kwargs).run()
