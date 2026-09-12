"""GAME_TITLE -- a TICK game.

Run it:      python this_file.py
Live prices: TICK_MARKET_SOURCE=coinbase python this_file.py
Real money:  TICK_FUNDING=arc-testnet python this_file.py

Controls: dial or Up/Down moves the aim, A (Enter/Space/yellow) buys,
B (Backspace/red) quits, Escape quits.
"""
from tick import Game, run
from tick.hud import Ladder, clear, draw_bet, draw_clock, draw_cursor, draw_hud, draw_open_line
from tick.ui import MINT, MUTED, RED, YELLOW, say


class ClassName(Game):
    title = 'GAME_TITLE'
    window_s = 10.0       # a round every ten seconds; the clock never stops
    arm_s = 1.0           # swallow presses for a beat after each bell

    # The aim box, in basis points of the price: one step, half a box, and how
    # far the box may be cranked from the round's opening price.
    STEP_BPS = 1.0
    BOX_BPS = 8.0
    REACH_BPS = 12.0

    def setup(self, ctx):
        self.offset = 0            # steps away from the round's opening price

    # ---- geometry --------------------------------------------------------
    def unit(self, ctx):
        """One basis point of this round's opening price."""
        return max(ctx.open_price, 1.0) / 10_000

    def aim(self, ctx):
        """(low, high) of the aim box right now."""
        centre = ctx.open_price + self.offset * self.STEP_BPS * self.unit(ctx)
        half = self.BOX_BPS / 2 * self.unit(ctx)
        return centre - half, centre + half

    # ---- input -----------------------------------------------------------
    def on_action(self, ctx, action):
        if action.name == 'B':
            return 'quit'
        if action.name in ('UP', 'DOWN'):
            reach = int(self.REACH_BPS / self.STEP_BPS)
            moved = self.offset + (1 if action.name == 'UP' else -1)
            self.offset = max(-reach, min(reach, moved))
            ctx.play(ctx.sounds.detent(abs(self.offset) / reach) if ctx.sounds else 'move')
        if action.name == 'A':
            low, high = self.aim(ctx)
            if ctx.bet(low, high) is None:
                ctx.note(ctx.refused or 'NO BET')
                ctx.play('warn')
            else:
                ctx.play('buy1')

    def on_round_end(self, ctx, round_):
        # The cursor is pulled back to the new round's anchor.
        self.offset = 0

    # ---- screen ----------------------------------------------------------
    def draw(self, ctx, screen):
        clear(screen)
        anchor = ctx.open_price or ctx.price
        ladder = Ladder(anchor, max(self.REACH_BPS + self.BOX_BPS, 1) * self.unit(ctx))
        draw_open_line(screen, ladder, anchor)

        # Where the price is now.
        y = int(ladder.y_of(ctx.price))
        for x in range(0, 480, 8):
            screen.fill(MINT, (x, y, 4, 2))

        # Bets already down, then the cursor on top.
        for bet in ctx.live_bets:
            glow = bet.contains(ctx.price)
            draw_bet(screen, ladder, bet, 300, 90, YELLOW, solid=True, glow=glow)
        for bet in ctx.next_bets:
            draw_bet(screen, ladder, bet, 396, 76, MUTED, solid=True)
        low, high = self.aim(ctx)
        rect = draw_cursor(screen, ladder, low, high, 180, 100)
        say(screen, f'{ctx.quote(low, high):.1f}x', rect.right + 6, rect.centery - 8, 16, YELLOW)

        draw_clock(ctx, screen)
        last = ctx.book.last
        if last is not None:
            colour = MUTED if last.voided else (MINT if last.hit else RED)
            word = 'VOID' if last.voided else ('HIT' if last.hit else 'MISS')
            say(screen, f'{word}  {ctx.usdc(last.net)}', 240, 250, 18, colour, center=True)
        draw_hud(ctx, screen, back='QUIT', go='BUY')


if __name__ == '__main__':
    run(ClassName())
