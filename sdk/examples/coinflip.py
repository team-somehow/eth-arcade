"""COINFLIP -- the smallest real game on this SDK. Up or down at the bell.

Run:  python examples/coinflip.py
      TICK_MARKET_SOURCE=coinbase python examples/coinflip.py

There is no aim, no geometry and no chart: pick a side, press A, and the round
settles on which side of the opening price the market closed. It exists to show
how little a game has to do -- the feed, the clock, the odds, the wallet and the
payout are all the SDK's.

Note what the odds do. A coin flip on a price is very close to 50/50, so the
quote sits a hair under 2x and *moves with the market*: when volatility drops
the two sides stop being equally likely to move far, but they stay equally
likely to be up or down, so the price barely shifts. That is the honest answer,
and it is computed, not typed in.
"""
from tick import Game, run
from tick.hud import clear, draw_clock, draw_hud
from tick.ui import CREAM, MINT, MUTED, RED, YELLOW, say

FAR = 10 ** 9      # "anything above/below": a one-sided range


class Coinflip(Game):
    title = 'COINFLIP'
    window_s = 10.0
    arm_s = 1.0

    def setup(self, ctx):
        self.pick = 'UP'

    def range_for(self, ctx, side):
        """UP is everything above the round's opening price; DOWN is below it."""
        anchor = ctx.open_price
        return (anchor, FAR) if side == 'UP' else (0.0, anchor)

    def on_action(self, ctx, action):
        if action.name == 'B':
            return 'quit'
        if action.name in ('UP', 'DOWN'):
            if self.pick != action.name:
                self.pick = action.name
                ctx.play('nav')
        elif action.name == 'A':
            low, high = self.range_for(ctx, self.pick)
            if ctx.bet(low, high, label=self.pick) is None:
                ctx.note(ctx.refused or 'NO BET')
                ctx.play('warn')
            else:
                ctx.play('buy1')

    def on_touch(self, ctx, pos):
        self.pick = 'UP' if pos[1] < 160 else 'DOWN'

    def draw(self, ctx, screen):
        clear(screen)
        draw_clock(ctx, screen, y=34)
        for index, side in enumerate(('UP', 'DOWN')):
            low, high = self.range_for(ctx, side)
            y = 80 + index * 84
            chosen = self.pick == side
            colour = YELLOW if chosen else MUTED
            screen.fill((22, 40, 51), (60, y, 360, 70))
            if chosen:
                screen.fill(colour, (60, y, 4, 70))
            say(screen, side, 84, y + 12, 26, colour)
            say(screen, f'{ctx.quote(low, high):.2f}x', 300, y + 16, 22, CREAM)
            staked = sum(bet.stake for bet in ctx.live_bets if bet.label == side)
            if staked:
                say(screen, f'{ctx.usdc(staked)} ON', 84, y + 44, 15, MINT)

        last = ctx.book.last
        if last is not None:
            word = 'VOID' if last.voided else ('WON' if last.hit else 'LOST')
            colour = MUTED if last.voided else (MINT if last.hit else RED)
            say(screen, f'{word} {ctx.usdc(abs(last.net))}', 240, 248, 18, colour, center=True)

        draw_hud(ctx, screen, back='QUIT', go='BUY')


if __name__ == '__main__':
    run(Coinflip())
