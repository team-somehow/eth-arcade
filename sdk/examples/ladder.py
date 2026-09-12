"""LADDER -- park a box on the price and be inside it at the bell.

Run:  python examples/ladder.py

This is the shape most games on this device end up being, so it is worth
reading as the reference:

* The box is **always the same size**, fixed in basis points of the round's
  opening price. It never changes under a bet already placed. Sizing it in
  volatility instead means the market redraws a box you already bought, which
  is both confusing and dishonest about what you paid for.
* **Only the payout reacts to the market.** A wild market makes the same box
  genuinely harder to hit, and the multiple rises to match. That is the honest
  response; quietly making the target bigger is not.
* Once a box is bought, the dial is **locked out** for that round. No
  repositioning, no early exit. Money can still be added -- each press priced
  at that press's odds, not the first press's.

Everything above is four rules and about eighty lines, because the SDK owns
the feed, the clock, the odds, the wallet and the sound.
"""
from tick import Game, run
from tick.hud import (Ladder, clear, draw_bet, draw_clock, draw_cursor, draw_hud,
                      draw_open_line, draw_price_line)
from tick.ui import CREAM, MINT, MUTED, RED, YELLOW, say, say_right

STEP_BPS = 1.0       # one detent
BOX_BPS = 8.0        # box height
REACH_BPS = 12.0     # how far from the anchor the box may be cranked


class LadderGame(Game):
    title = 'LADDER'
    window_s = 10.0
    arm_s = 1.5
    min_multiple = 1.05
    max_multiple = 25.0

    def setup(self, ctx):
        self.offset = 0

    # ---- geometry --------------------------------------------------------
    def unit(self, ctx) -> float:
        return max(ctx.open_price or ctx.price, 1.0) / 10_000

    def aim(self, ctx) -> tuple[float, float]:
        centre = ctx.open_price + self.offset * STEP_BPS * self.unit(ctx)
        half = BOX_BPS / 2 * self.unit(ctx)
        return centre - half, centre + half

    @property
    def reach_steps(self) -> int:
        return int(REACH_BPS / STEP_BPS)

    # ---- input -----------------------------------------------------------
    def on_action(self, ctx, action):
        if action.name == 'B':
            return 'quit'
        if action.name in ('UP', 'DOWN'):
            if ctx.next_bets:
                # Locked: the first press fixed this box's level. Say so, in
                # sound, rather than silently ignoring the dial.
                ctx.note('LOCKED / A ADDS ' + ctx.usdc())
                ctx.play('lock')
                return
            before = self.offset
            step = 1 if action.name == 'UP' else -1
            self.offset = max(-self.reach_steps, min(self.reach_steps, self.offset + step))
            if self.offset != before:
                if self.offset == 0:
                    ctx.play('crossline')     # passing back over spot
                elif ctx.sounds:
                    ctx.play(ctx.sounds.detent(abs(self.offset) / self.reach_steps))
        elif action.name == 'A':
            bets = ctx.next_bets
            low, high = (bets[0].low, bets[0].high) if bets else self.aim(ctx)
            placed = ctx.bet(low, high)
            if placed is None:
                ctx.note(ctx.refused or 'NO BET')
                ctx.play('warn')
            else:
                ctx.play(f'buy{min(3, placed.presses)}')

    def on_round_end(self, ctx, round_):
        self.offset = 0      # the cursor follows the new anchor

    # ---- screen ----------------------------------------------------------
    def draw(self, ctx, screen):
        clear(screen)
        anchor = ctx.open_price or ctx.price
        unit = self.unit(ctx)
        ladder = Ladder(anchor, (REACH_BPS + BOX_BPS) * unit)
        draw_open_line(screen, ladder, anchor)
        draw_price_line(screen, ladder, ctx.market.history, ctx.now, right_x=170)

        for bet in ctx.live_bets:
            inside = bet.contains(ctx.price)
            rect = draw_bet(screen, ladder, bet, 200, 96, YELLOW, solid=True, glow=inside)
            say(screen, f'{ctx.usdc(bet.stake)} @ {bet.multiple:.1f}x',
                rect.left, rect.top - 17, 14, YELLOW)
        for bet in ctx.next_bets:
            rect = draw_bet(screen, ladder, bet, 320, 84, CREAM, solid=True)
            say(screen, f'{ctx.usdc(bet.stake)} @ {bet.multiple:.1f}x',
                rect.left, rect.top - 17, 14, CREAM)
        if not ctx.next_bets:
            low, high = self.aim(ctx)
            rect = draw_cursor(screen, ladder, low, high, 320, 84)
            quote = ctx.quote(low, high)
            say(screen, f'{quote:.1f}x' if quote >= ctx.game.min_multiple else 'QUIET',
                rect.left, rect.top - 17, 14, YELLOW)

        say(screen, f'MOVE {ctx.move:+.2f}', 8, 38, 15, MINT if ctx.move >= 0 else RED)
        say_right(screen, f'{len(ctx.market.history)} TICKS / {ctx.market.name}',
                  472, 38, 13, MUTED)
        draw_clock(ctx, screen, x=240, y=34)

        last = ctx.book.last
        if last is not None and ctx.now - ctx.rounds.opened_at < 2.5:
            word = 'VOID' if last.voided else ('HIT' if last.hit else 'MISS')
            colour = MUTED if last.voided else (MINT if last.hit else RED)
            say(screen, f'{word}  {ctx.usdc(last.net)}', 240, 246, 18, colour, center=True)

        draw_hud(ctx, screen, back='QUIT', go='BUY ' + ctx.usdc())


if __name__ == '__main__':
    run(LadderGame())
