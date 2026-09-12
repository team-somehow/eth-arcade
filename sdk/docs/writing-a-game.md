# Writing a game

From nothing to a playable game in about twenty minutes. Read
[PLAN.md](../PLAN.md) first if you want the reasoning; this page is the doing.

---

## 1. Scaffold

```bash
tick new dropzone
python dropzone.py
```

You now have a playable game on simulated prices: crank the dial, press A, and
a box settles at the next bell. Open `dropzone.py` — it is about eighty lines,
and every one of them is yours to change.

---

## 2. The five hooks

A game is a class. Override what you need; the rest has a default.

```python
from tick import Game, run

class Dropzone(Game):
    title = 'DROPZONE'
    window_s = 10.0

    def setup(self, ctx):                     # once, everything is already running
        self.offset = 0

    def on_action(self, ctx, action):         # UP / DOWN / A / B
        ...

    def on_settle(self, ctx, settlement):     # your bet was paid or lost
        ...

    def update(self, ctx, dt):                # every frame, before drawing
        ...

    def draw(self, ctx, screen):              # every frame
        ...

run(Dropzone())
```

The full list: `setup`, `teardown`, `on_tick`, `on_round_start`,
`on_round_end`, `on_settle`, `on_action`, `on_touch`, `update`, `draw`.

---

## 3. Placing a bet

One call. It debits, prices, and books the bet for the coming bell.

```python
def on_action(self, ctx, action):
    if action.name == 'A':
        bet = ctx.bet(low, high)
        if bet is None:
            ctx.note(ctx.refused)       # put the reason on screen
            ctx.play('warn')
        else:
            ctx.play('buy1')
```

`ctx.bet` returns `None` and sets `ctx.refused` when:

| `ctx.refused` | Meaning |
|---|---|
| `NO MARKET YET` | no price has arrived; the clock has not started |
| `READING THE MARKET` | the feed has not moved enough to measure anything |
| `FEED STALE` | the last price is too old to settle money on |
| `MARKET QUIET / NO BETS` | the price has not moved for 15s: every bet is a certainty |
| `ARMING` | a bell just rang; presses are swallowed for `arm_s` |
| `TOO SURE TO SELL` | the quote is under `min_multiple` |
| `MAX WIN REACHED / CASH OUT` | the best case exceeds what the escrow can pay |
| `NOT ENOUGH USDC` | the wallet is short |

Show it. A button that silently does nothing reads as broken hardware.

### What a bet is worth, before placing it

```python
ctx.quote(low, high)                   # multiple, at this instant
ctx.quote(low, high, rounds_ahead=2)   # for the bell after next: a longer bet
```

Draw the quote next to the cursor and it updates as the market moves — which is
most of what makes these games readable.

---

## 4. Shaping the bet

Almost every game is one of three shapes.

**A box** — a range around a level the player aims at:

```python
half = ctx.open_price * 4 / 10_000            # 4 bps: a fixed height
centre = ctx.open_price + self.offset * step
ctx.bet(centre - half, centre + half)
```

**A side** — everything above or below a line:

```python
ctx.bet(ctx.open_price, 1e9)      # up
ctx.bet(0.0, ctx.open_price)      # down
```

**A ladder** — several ranges at once, each its own bet, all settling together:

```python
for low, high in self.rungs(ctx):
    ctx.bet(low, high, stake=ctx.stake // len(self.rungs(ctx)))
```

### Size geometry in basis points, not in volatility

```python
def unit(self, ctx):
    return ctx.open_price / 10_000        # one basis point of the round's open
```

Anchor on the **round's opening price** and size in **basis points**, so the
box is the same size all round and in every market. Sizing it in sigma means
the market redraws a box the player already bought — confusing, and dishonest
about what they paid for.

If you change `window_s`, scale the geometry rather than leaving it:

```python
from tick.pricing import scale_to_window
box_bps = scale_to_window(8.0, self.window_s, reference_s=20.0)
```

Prices travel with the square root of time. Halving the round without shrinking
the box makes a box on spot a near-certainty at 1.2x and everything else a
capped lottery ticket — a flatter game, not a faster one.

---

## 5. Locking, topping up, and arming

Three small rules that make these games feel fair.

```python
class MyGame(Game):
    arm_s = 1.5          # swallow presses for a beat after each bell

    def on_action(self, ctx, action):
        if action.name in ('UP', 'DOWN'):
            if ctx.next_bets:                      # already bought: lock the dial
                ctx.note('LOCKED / A ADDS ' + ctx.usdc())
                ctx.play('lock')
                return
            self.offset += 1 if action.name == 'UP' else -1
        elif action.name == 'A':
            bets = ctx.next_bets
            low, high = (bets[0].low, bets[0].high) if bets else self.aim(ctx)
            ctx.bet(low, high)                     # tops up at *this* press's odds
```

* **The first press fixes the level.** Repositioning after the market moves is
  an early exit in disguise.
* **Later presses add stake at current odds.** Charging the first press's price
  for the fifth is a free option.
* **`arm_s` swallows the press that was meant for the last round.** Without it
  a thumb still finishing "one more on that box" buys the *new* round wherever
  the cursor happens to sit.

---

## 6. Drawing

The SDK gives you a ladder, a HUD and a palette so a one-file game still looks
like it belongs on the device.

```python
from tick.hud import (Ladder, clear, draw_bet, draw_clock, draw_cursor,
                      draw_hud, draw_open_line, draw_price_line)
from tick.ui import CREAM, MINT, MUTED, RED, YELLOW, say, say_right

def draw(self, ctx, screen):
    clear(screen)
    ladder = Ladder(ctx.open_price, 20 * self.unit(ctx))   # price -> pixels

    draw_open_line(screen, ladder, ctx.open_price)         # the reference
    draw_price_line(screen, ladder, ctx.market.history, ctx.now, right_x=170)

    for bet in ctx.live_bets:                              # settling this bell
        draw_bet(screen, ladder, bet, 200, 96, YELLOW, glow=bet.contains(ctx.price))
    for bet in ctx.next_bets:                              # bought for the next
        draw_bet(screen, ladder, bet, 320, 84, CREAM)
    if not ctx.next_bets:
        draw_cursor(screen, ladder, *self.aim(ctx), 320, 84)

    draw_clock(ctx, screen)
    draw_hud(ctx, screen, back='QUIT', go='BUY ' + ctx.usdc())
```

Two conventions worth keeping, because a player who has used one game on this
device then reads yours for free:

* **Dashed = not committed. Solid = money is on it.**
* **Anchor the view on the round's opening price**, never on spot. Anchoring on
  spot re-centres the view every tick and the price appears still while the
  world slides around it.

Size the visible band to what a bet can actually reach and no wider. Widen it
to fit every possibility and a dollar of real movement becomes an invisible
wobble.

---

## 7. Sound

You get the generic cues for free — the bell, the swoops when the price crosses
into or out of a live bet, the countdown pitched by whether you are currently
winning, the win/miss/void stings, and a music bed chosen from what is at
stake. Turn them off with `sound_cues = False` / `music = False`.

Add your own from the same kit:

```python
ctx.play('buy2')
ctx.play(ctx.sounds.detent(abs(self.offset) / self.reach))   # rising crank clicks
```

The two that matter most are the crossing swoops and the pitched countdown:
together they tell a player whether they are winning **without looking**, which
is the whole point of a handheld you play with your thumb.

---

## 8. Testing it

A game that holds money needs tests, and a game loop is testable only if it can
run without a window.

```python
# tests/test_dropzone.py
import unittest
from tick import InputAction
from tick.testing import Harness
from dropzone import Dropzone


class TestDropzone(unittest.TestCase):
    def test_a_bet_is_taken_and_settled(self):
        with Harness(Dropzone(), seed=7) as h:
            h.warm(25)                         # 25s of market, instantly
            h.press(InputAction.A)
            self.assertEqual(h.balance, 1000_000000 - h.ctx.stake)
            h.advance(25)
            self.assertTrue(h.book.history)

    def test_a_certainty_is_never_sold(self):
        with Harness(Dropzone(), seed=7) as h:
            h.warm(25)
            self.assertIsNone(h.ctx.bet(h.price * 0.5, h.price * 1.5))
            self.assertEqual(h.ctx.refused, 'TOO SURE TO SELL')

    def test_it_draws(self):
        with Harness(Dropzone(), seed=7) as h:
            h.warm(25)
            h.draw_once()
```

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -t .
```

Time in the harness is fake and monotonic, so `advance(600)` is instant, and a
seeded simulated feed gives the same market every run — which is what makes a
payout assertion an assertion.

Other tools worth knowing:

```python
from tick.testing import ScriptedFeed
Harness(MyGame(), feed=ScriptedFeed([(0.0, 2500.0), (1.0, 2501.0)]))   # an exact market
Harness(MyGame(), feed=FrozenFeed(2500.0))                             # a dead flat one
```

---

## 9. Going live

```bash
tick run dropzone.py --source coinbase                # real prices, paper money
tick run dropzone.py --source substreams              # on-chain prices
TICK_FUNDING=arc-testnet TICK_STAKE_USDC=0.001 python dropzone.py    # real money
```

Nothing in your game changes for any of these. See
[prices-substreams.md](prices-substreams.md), [money-arc.md](money-arc.md) and
[identity-ens.md](identity-ens.md).

---

## Checklist before you call it done

- [ ] Every refusal reason reaches the screen, in words.
- [ ] The dial does nothing surprising after a bet is placed — and says so.
- [ ] The view is anchored on the round's open price.
- [ ] Geometry is in basis points; only the payout reacts to the market.
- [ ] `arm_s` is set if a press can be meant for the round that just closed.
- [ ] Your game draws correctly with no price yet, and with a stale feed.
- [ ] A test asserts what happens when the market goes flat.
- [ ] A test asserts a settlement's payout, not just that one happened.
