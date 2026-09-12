"""What you write, and what you are handed.

A game is a class with a few optional methods. Every one of them is optional
except `draw`; the SDK calls what exists and skips what does not.

    from tick import Game, run

    class Coinflip(Game):
        title = 'COINFLIP'
        window_s = 10.0

        def setup(self, ctx):
            self.pick = 'UP'

        def on_action(self, ctx, action):
            if action.name in ('UP', 'DOWN'):
                self.pick = action.name
            if action.name == 'A':
                low, high = (ctx.price, 1e12) if self.pick == 'UP' else (0.0, ctx.price)
                ctx.bet(low, high)

        def draw(self, ctx, screen):
            ...

    run(Coinflip())

Everything else -- the feed, the round clock, the odds, the wallet, the escrow,
the encoder, the sound cues, the 480x320 canvas and its rotation -- is already
running by the time `setup` is called.

The context
-----------

`ctx` is the live state of the machine, rebuilt-free and passed to every hook:

    ctx.price          last price, a float
    ctx.market         freshness, volatility, probabilities  (tick.market)
    ctx.round          the round now running                 (tick.rounds)
    ctx.rounds         the clock itself
    ctx.wallet         balance in micro-USDC                 (tick.money)
    ctx.book           open bets and their history           (tick.bets)
    ctx.now / ctx.dt   monotonic seconds, and the frame delta

    ctx.bet(low, high)        place a bet on the next bell. Returns the Bet, or
                              None with `ctx.refused` saying why
    ctx.quote(low, high)      what that bet would pay, right now
    ctx.can_bet()             is the market sellable at all?
    ctx.play('win_big')       a sound cue
    ctx.note('LOCKED')        a line of text for the status bar
"""
from __future__ import annotations

from .bets import Bet, BetBook, Settlement
from .input import InputAction
from .market import Market
from .money import Wallet, format_usdc, places_for
from .rounds import Round, RoundClock


class Game:
    """Subclass this. Override what you need; the rest has a sane default."""

    # ---- what the runtime reads before starting --------------------------
    title = 'TICK GAME'
    window_s = 10.0          # round length in seconds; the clock never stops
    stake_usdc: str | None = None   # per bet; None means TICK_STAKE_USDC
    max_multiple = 25.0      # never quote more than this: an unfunded promise
    min_multiple = 1.05      # never sell under this: a near-certain win is not a bet
    house_edge = 0.0         # 0.0 quotes fair odds -- and says so on screen
    rounds_ahead = 1         # 1 = the next bell; 0 = the round already running
    arm_s = 0.0              # swallow bets for this long after a bell (see ctx.armed)
    sound_cues = True        # let the SDK play the generic cues for you
    music = True             # ... and pick the music bed from what is at stake

    # ---- lifecycle -------------------------------------------------------
    def setup(self, ctx: 'GameContext') -> None:
        """Once, after the display, feed and wallet are up."""

    def teardown(self, ctx: 'GameContext') -> None:
        """Once, on the way out. The feed and escrow are closed for you."""

    # ---- events ----------------------------------------------------------
    def on_tick(self, ctx: 'GameContext', tick) -> None:
        """A new price arrived and has already been folded into the market."""

    def on_round_start(self, ctx: 'GameContext', round_: Round) -> None:
        """A new round opened at `round_.open_price`."""

    def on_round_end(self, ctx: 'GameContext', round_: Round) -> None:
        """A round rang. Its bets have already settled."""

    def on_settle(self, ctx: 'GameContext', settlement: Settlement) -> None:
        """One of your bets was paid or lost. Money has already moved."""

    def on_action(self, ctx: 'GameContext', action: InputAction) -> str | None:
        """A dial turn or a button. Return 'quit' to leave."""

    def on_touch(self, ctx: 'GameContext', pos: tuple[int, int]) -> str | None:
        """A tap, in canvas pixels. Return 'quit' to leave."""

    # ---- frame -----------------------------------------------------------
    def update(self, ctx: 'GameContext', dt: float) -> None:
        """Every frame, before drawing."""

    def draw(self, ctx: 'GameContext', screen) -> None:
        """Every frame. The one hook a game has to have."""
        raise NotImplementedError('a game must draw something')


class GameContext:
    """Everything the machine currently knows, handed to every hook."""

    def __init__(self, game: Game, market: Market, wallet: Wallet,
                 rounds: RoundClock, book: BetBook, sounds=None,
                 stake: int = 0, screen=None) -> None:
        self.game = game
        self.market = market
        self.wallet = wallet
        self.rounds = rounds
        self.book = book
        self.sounds = sounds
        self.stake = stake
        self.screen = screen
        self.now = 0.0
        self.dt = 0.0
        self.frame = 0
        self.message = ''
        self.message_until = 0.0
        self.refused = ''            # why the last bet was refused, for the screen
        self.armed_at = 0.0          # bets are swallowed until this moment
        self.running = True

    # ---- shortcuts -------------------------------------------------------
    @property
    def price(self) -> float:
        return self.market.price

    @property
    def round(self) -> Round | None:
        return self.rounds.current

    @property
    def open_price(self) -> float:
        return self.rounds.open_price

    @property
    def remaining(self) -> float:
        return self.rounds.remaining(self.now)

    @property
    def move(self) -> float:
        """How far the price has come since this round opened."""
        return self.rounds.move(self.price)

    @property
    def armed(self) -> bool:
        """False for `game.arm_s` after each bell.

        Presses meant as one more stake on the round that just closed keep
        arriving for a beat after the bell. With nothing pending they would buy
        the *new* round at wherever the cursor happens to sit -- which is not
        what the thumb meant. Swallow them instead.
        """
        return self.now >= self.armed_at

    @property
    def target_round(self) -> int:
        """The round index a bet placed now will settle at.

        `rounds_ahead = 1` by default: a press buys the **next** round, not the
        one already running. Selling the running round means selling a bet
        whose outcome is already half known -- a press a second before the bell
        is nearly a sure thing, and the model correctly prices it at 1.0x and
        refuses it, which reads as a broken button rather than a rule.
        """
        return self.rounds.index + max(0, self.game.rounds_ahead)

    def horizon(self) -> float:
        """Seconds from now to the bell a bet placed now settles at."""
        return self.rounds.horizon(self.now, max(0, self.game.rounds_ahead))

    # ---- betting ---------------------------------------------------------
    def can_bet(self) -> bool:
        return self.market.sellable(self.now) and self.armed

    def why_not(self) -> str:
        """Words for the screen when a bet cannot be placed. Empty if it can."""
        if not self.armed:
            return 'ARMING'
        return self.market.why_not(self.now)

    def quote(self, low: float, high: float, rounds_ahead: int | None = None) -> float:
        """The multiple that range would pay if bought right now.

        The horizon runs to the bell being bought, so buying early prices more
        drift -- a longer bet, not a free one.
        """
        ahead = self.game.rounds_ahead if rounds_ahead is None else rounds_ahead
        horizon = self.rounds.horizon(self.now, max(0, ahead))
        return self.market.quote(low, high, horizon,
                                 self.game.house_edge, self.game.max_multiple)

    def bet(self, low: float, high: float, stake: int | None = None,
            rounds_ahead: int | None = None, label: str = '') -> Bet | None:
        """Put money on [low, high] at the coming bell. None means refused.

        Refused, in order, when: the round clock has not started; the market is
        not sellable (stale, quiet, or not yet read); the cursor is not armed;
        the quote is under `min_multiple` (a near-certain win is not a bet);
        the best case would win past what the escrow can pay; or the wallet is
        short. `ctx.refused` says which -- put it on the screen.
        """
        self.refused = ''
        ahead = self.game.rounds_ahead if rounds_ahead is None else rounds_ahead
        stake = self.stake if stake is None else stake
        if not self.rounds.started:
            self.refused = 'NO MARKET YET'
            return None
        if not self.armed:
            self.refused = 'ARMING'
            return None
        blocked = self.market.why_not(self.now)
        if blocked:
            self.refused = blocked
            return None
        multiple = self.quote(low, high, ahead)
        if multiple < self.game.min_multiple:
            self.refused = 'TOO SURE TO SELL'
            return None
        if self.would_exceed_cap(stake, multiple):
            self.refused = 'MAX WIN REACHED / CASH OUT'
            return None
        if not self.wallet.can_afford(stake):
            self.refused = 'NOT ENOUGH USDC'
            return None
        index = self.rounds.index + max(0, ahead)
        placed = self.book.place(index, low, high, stake, multiple, label)
        if placed is None:
            self.refused = 'NOT ENOUGH USDC'
        return placed

    def would_exceed_cap(self, stake: int, multiple: float) -> bool:
        """Could one more bet win past what the escrow will actually pay?

        The best case lands every open bet plus this one. Past the cap the
        contract would pay less than the screen promised, so refuse the press
        instead of writing a cheque the chain will bounce.
        """
        best = self.wallet.balance - stake + stake * multiple + self.book.best_case()
        return self.wallet.would_exceed_cap(int(best))

    def cancel_next(self) -> int:
        """Refund bets on a round that has not started yet. Returns the stake."""
        return self.book.refund(self.rounds.index + 1)

    # ---- bets you have out ----------------------------------------------
    @property
    def live_bets(self) -> list[Bet]:
        """Bets settling at the next bell."""
        return self.book.for_round(self.rounds.index)

    @property
    def next_bets(self) -> list[Bet]:
        """Bets already bought for the bell after that."""
        return self.book.for_round(self.rounds.index + 1)

    @property
    def inside(self) -> bool | None:
        """Is the price inside a live bet right now? None when nothing is live."""
        live = self.live_bets
        if not live:
            return None
        return any(bet.contains(self.price) for bet in live)

    @property
    def staked(self) -> int:
        return self.book.staked()

    # ---- output ----------------------------------------------------------
    def play(self, cue: str) -> None:
        if self.sounds is not None:
            self.sounds.play(cue)

    def note(self, text: str, seconds: float = 2.0) -> None:
        """A line for the status bar, for a couple of seconds."""
        self.message, self.message_until = text, self.now + seconds

    def status_line(self) -> str:
        """The note if one is showing, else why betting is blocked, else ''."""
        if self.message and self.now < self.message_until:
            return self.message
        return self.why_not()

    def usdc(self, micro: int | None = None) -> str:
        """Format micro-USDC with exactly the decimals this game's stake needs."""
        return format_usdc(self.stake if micro is None else micro, places_for(self.stake))

    def quit(self) -> None:
        self.running = False
