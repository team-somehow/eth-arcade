# The plan

What this SDK is, why each piece exists, and the order to build or extend it in.

Written to be read top to bottom in about fifteen minutes. Every claim has a
runnable example; every rule has the bug that taught it.

---

## Part 1 — First principles

Seven questions. Answer them and the architecture falls out.

### 1. What is a game on this device?

**A claim about where a number will be at a known moment, backed by money.**

That is it. A box on a price ladder, an over/under, a coin flip, a hi-lo — all
the same claim with different clothes. So the SDK has exactly one bet type: a
**price range** and a **round** it settles at.

```python
ctx.bet(low=2499.0, high=2501.0)      # a box
ctx.bet(ctx.open_price, 1e9)          # "up": a one-sided range
ctx.bet(0.0, ctx.open_price)          # "down"
```

Your game decides which range the player is pointing at, and what it looks
like. Nothing else about a game is the SDK's business.

### 2. Where does the number come from?

**From somewhere real, and it must carry its own age.**

A float cannot tell you when it was true. Settle money on one and you will
eventually settle on a number from four minutes ago. So every feed produces a
`PriceTick`:

```python
PriceTick(price=2500.12, sequence=417, received_at=10234.5, source_age=0.8)
tick.age(now)      # time since arrival + how old it already was
```

`source_age` is what makes a chain block honest: a block two seconds old *is*
two seconds old, and the game must know that before it settles on it.

Four sources, one seam:

```bash
TICK_MARKET_SOURCE=sim         # seeded random walk, no network        (default)
TICK_MARKET_SOURCE=coinbase    # live public ticker at 5 Hz
TICK_MARKET_SOURCE=substreams  # on-chain pools, one tick per block
TICK_MARKET_SOURCE=replay      # a market you recorded earlier
```

Your game reads `ctx.price` and never knows which. That is the only reason it
can be developed on a laptop, tested deterministically, and demoed on-chain.

### 3. What is a fair price for a bet?

**One over the chance of winning.** Everything else is decoration.

```python
chance   = market.probability(low, high, horizon)     # normal CDF over the range
multiple = (1 - edge) / chance                        # capped, floored
```

Over a short horizon a price is a random walk in log space, and distance
travelled grows with the **square root** of time, not with time. So:

```python
sigma_10s = price * sqrt(variance_per_second * 10)
```

A one-sigma-wide band is about a 68% shot, so it pays about 1.47x. A box a
long way out is a long shot and pays accordingly. Nothing is typed into a
table; every number is computed from what the market is doing right now.

```python
>>> h = Harness(MyGame(), seed=7).warm(25)
>>> half = h.price * 0.0002              # a box 4 bps tall, on $2,500 ETH
>>> h.ctx.quote(h.price - half, h.price + half)          # on spot
2.39
>>> h.ctx.quote(h.price + half, h.price + 3*half)        # one box out
4.14
>>> h.ctx.quote(h.price + 3*half, h.price + 5*half)      # two boxes out
21.57
>>> h.ctx.quote(h.price + 5*half, h.price + 7*half)      # three: past the cap
25.0
```

That ladder is not designed, it is measured. Turn the volatility up and every
rung moves down; nothing in the game has to be retuned.

### 4. What is money?

**An integer.** Micro-USDC: whole units of 0.000001 USDC, the real on-chain
unit.

```python
wallet.balance          # 100_000_000  == 100 USDC
wallet.debit(10_000_000)
```

A balance that is a float drifts, and `0.1 + 0.2` is not a thing you want to
explain to someone whose money it is. Payouts are **truncated**, never rounded:
a book must not round money into existence it did not owe.

```python
>>> parse_usdc('0.57')        # float('0.57') * 1e6 is 569999.9999999999
570000
```

### 5. When does a bet settle?

**At the bell, on a price stamped at or after the bell.**

The clock never stops. A round is always running; when one ends the next has
already started, in the same frame — there is no ready screen, because a clock
you can pause is a clock you can wait out.

A price from *before* the bell cannot settle that bell, however fresh it looks.
So the clock waits:

```
bell ──> no post-bell price yet ──> SETTLING (up to 4s) ──> still nothing ──> VOID, stake refunded
                                 └──> price arrives ─────> settle
```

Refunding is the right answer when you are unsure. Settling a real bet against
the wrong moment's price is worse than not settling it.

### 6. Who is the player?

**A wallet — and a wallet is not a name.** `0x7ee8…CCac` on a leaderboard is
noise.

So each wallet gets a readable subname (`amber-otter.tick.eth`) and its record
lives in that name's own text records. The leaderboard is then *derived* rather
than stored: read the registry, read each name, sort. No server, no database,
nothing that dies when you stop paying for it.

```python
from tick.identity import Standings, name_of
name_of('0x7ee8...')        # 'amber-otter.tick.eth'
Standings().read()          # [Standing(name=..., pnl=Decimal('12.4'), ...), ...]
```

### 7. What does the SDK own, and what do you?

| The SDK | You |
|---|---|
| the feed, its validation, its staleness | which range the player is pointing at |
| volatility, probability, the multiple | how the player aims |
| the round clock, settlement, voiding | what it looks like |
| the wallet, the escrow, the cap | what it sounds like beyond the default cues |
| dial, buttons, keys, touch, rotation | the words on the screen |
| the generic cues and the music beds | |

If you find yourself writing a random number generator, a volatility estimate,
or a payout calculation, stop: it already exists, and the version here has the
bugs already taken out of it.

---

## Part 2 — The system

### The shape of one frame

```
                 ┌─────────────────────────────────────────────┐
  feed ────────► │ 1  market.poll()      validate, fold in      │
                 │ 2  rounds.update()    has a bell passed?     │
                 │ 3  book.settle()      pay, refund, record    │
                 │ 4  cues               bell, crossings, ticks │
                 │ 5  your on_action()   the dial and buttons   │
                 │ 6  your update()      your state             │
                 │ 7  your draw()        the frame              │
                 └─────────────────────────────────────────────┘
```

The order is not arbitrary:

* **Prices before the clock**, because the clock settles on a price.
* **Settlement before input**, because a press arriving in the same frame as a
  bell belongs to the round now open, not the one that just closed.
* **Draw last**, because everything above may have changed what is on screen.

### The layers

```
   tick.feeds      PriceTick · SimulatedFeed · CoinbaseFeed · SubstreamsFeed · ReplayFeed
        │          PoolStream (raw, per-pool, per-block)
        ▼
   tick.market     history · realized volatility · fresh / quiet / ready · probability
        │
        ├──────────► tick.pricing     chance → multiple, with cap, floor, edge
        ▼
   tick.rounds      RoundClock: open price, bell, settling, void
        │
        ▼
   tick.bets        BetBook: place (debit) · top up · settle (credit) · refund
        │                    ▲
        │                    │
   tick.money       Wallet (integer micro-USDC) ◄── tick.escrow (real, on-chain)
        │
        ▼
   tick.game        Game + GameContext   ◄── you write this
        │
        ▼
   tick.runtime     run(): display · input · cues · 30 FPS · shutdown
                    tick.hud / tick.ui  ladder · HUD · palette · synthesized sound
                    tick.identity       names and standings
```

Take any layer on its own. The data layers need no pygame at all:

```python
# a price bot, no game, no screen
from tick import Market, open_feed
market = Market(feed=open_feed('substreams'))
for tick in market.feed.stream():
    print(tick.price, market.probability(tick.price - 1, tick.price + 1, 10))
```

### What a game looks like in full

```python
from tick import Game, run
from tick.hud import Ladder, clear, draw_bet, draw_clock, draw_cursor, draw_hud

class Ladder_(Game):
    title, window_s, arm_s = 'LADDER', 10.0, 1.5

    def setup(self, ctx):
        self.offset = 0                      # detents from the round's open price

    def unit(self, ctx):
        return max(ctx.open_price, 1.0) / 10_000          # one basis point

    def aim(self, ctx):
        centre = ctx.open_price + self.offset * self.unit(ctx)
        half = 4 * self.unit(ctx)
        return centre - half, centre + half

    def on_action(self, ctx, action):
        if action.name in ('UP', 'DOWN') and not ctx.next_bets:
            self.offset += 1 if action.name == 'UP' else -1
        elif action.name == 'A':
            ctx.bet(*self.aim(ctx)) or ctx.note(ctx.refused)

    def on_round_end(self, ctx, round_):
        self.offset = 0

    def draw(self, ctx, screen):
        clear(screen)
        ladder = Ladder(ctx.open_price, 20 * self.unit(ctx))
        for bet in ctx.live_bets:
            draw_bet(screen, ladder, bet, 200, 96, glow=bet.contains(ctx.price))
        draw_cursor(screen, ladder, *self.aim(ctx), 320, 84)
        draw_clock(ctx, screen)
        draw_hud(ctx, screen)

run(Ladder_())
```

Forty lines, and it is a real game with real odds and real money.

---

## Part 3 — The rules, and what each one cost

Every rule below is enforced in code and covered by a test. They read as
paranoia until you meet the bug.

| Rule | Where | What happens without it |
|---|---|---|
| **Stillness is a calm market, not missing data** | `Market._measure` | A flat feed was priced as "typical ETH". A box parked on the line won **58 bets out of 58**. |
| **Nothing is sold when the price has not moved for 15s** | `Market.quiet` | On a line that never moves, a box on spot is a certain win at any multiple over 1x. |
| **Nothing is sold under 1.05x** | `Game.min_multiple` | A near-certain bet is not a bet, it is a withdrawal with extra steps. |
| **One print cannot move the odds** | `SPIKE_CAP` | One glitched tick inflated every payout for the next minute. |
| **A pre-bell price cannot settle a bell** | `RoundClock.update` | The round settled on whatever happened to be on screen, which is not the same number. |
| **No usable bell price for 4s → void and refund** | `VOID_AFTER` | Settling real money on the wrong moment's price. |
| **The horizon runs to the bell being bought** | `ctx.horizon()` | Buying fifteen seconds early priced ten seconds of drift: a free option, and players find free options. |
| **Topping up is priced at that press's odds** | `Bet.add` | Adding stake after the price walked toward your box cost the old, cheaper price. |
| **A bought bet cannot be moved** | your game (`ctx.next_bets`) | Repositioning after the market moves is an early exit wearing a hat. |
| **Payouts truncate down** | `BetBook.settle` | Rounding created money the book never owed. |
| **Amounts are integers** | `tick.money` | `0.57 USDC` became `0.569999` and stayed wrong. |
| **Refuse a bet whose best case exceeds the escrow cap** | `ctx.would_exceed_cap` | The screen promised a payout the contract would refuse. |
| **Geometry is fixed; only the payout reacts** | your game | A box already bought got redrawn at a different size when the market woke up. |
| **Presses are swallowed for `arm_s` after a bell** | `ctx.armed` | A press meant as "more on that box" bought the *next* round wherever the cursor sat. |
| **The dial is read raw in play, rate-limited in menus** | `EncoderInput.poll` | A whip-spin wrapped a menu a dozen times, or a stopped dial kept moving the box. |

---

## Part 4 — Building it, one shippable increment at a time

Each increment ends with something you can run, and a command that proves it.
Nothing here depends on the increment after it.

### Increment 0 — a number that arrives (half a day)

*Goal: prices, validated, from more than one source.*

Build `tick/ticks.py`, `tick/feeds/`.

```bash
tick prices --source sim --limit 20
tick prices --source coinbase --limit 20
```

**Done when:** the same seed replays the same market exactly; a tick with a
future timestamp, a negative price, or an out-of-order sequence is rejected
rather than used.

### Increment 1 — what the number means (half a day)

*Goal: measured volatility and a probability you can defend.*

Build `tick/pricing.py`, `tick/market.py`.

```bash
python examples/ticker.py
python -m unittest tests.test_market tests.test_pricing
```

**Done when:** a one-sigma band prices at 68%; a dead-flat feed reports
`MARKET QUIET / NO BETS` rather than a cheap certainty; one spiked print does
not move the estimate by more than the cap allows.

### Increment 2 — money that cannot drift (half a day)

*Goal: a wallet, in integers, with a funding seam.*

Build `tick/money.py`.

```bash
python -m unittest tests.test_money
```

**Done when:** a thousand debit/credit pairs leave the balance exactly where it
started, and `parse_usdc('0.57')` is `570000`.

### Increment 3 — the clock and the book (one day)

*Goal: rounds roll on their own and bets settle honestly.*

Build `tick/rounds.py`, `tick/bets.py`.

```bash
python -m unittest tests.test_rounds tests.test_bets
```

**Done when:** a missed frame does not shift the bell; a bell with no post-bell
price voids and refunds after four seconds; a top-up blends the multiple.

### Increment 4 — a game you can actually play (one day)

*Goal: `run(MyGame())` opens a window and plays.*

Build `tick/game.py`, `tick/runtime.py`, `tick/display.py`, `tick/input.py`,
`tick/ui.py`, `tick/hud.py`.

```bash
tick new mygame && python mygame.py
```

**Done when:** the dial moves the aim, A buys, the bell settles, the screen
shows the balance, and Escape leaves cleanly.

### Increment 5 — proof it is testable (half a day)

*Goal: the rules are tested, not eyeballed.*

Build `tick/testing.py` and the suite.

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -t .
```

**Done when:** three hundred simulated rounds of a fair book drift less than a
third of the money staked, and every example draws a frame without raising.

### Increment 6 — a price nobody can push (one day)

*Goal: the on-chain feed under the game.*

Build `tick/feeds/substreams.py`; run the relay.

```bash
python substreams/relay.py &
tick pools -v
tick run mygame.py --source substreams
```

**Done when:** many pools across two chains become one price, an outlier pool
is excluded, a chain that falls behind stops counting, and a relay that dies
makes the game refuse bets rather than settle on stale blocks.
See [docs/prices-substreams.md](docs/prices-substreams.md).

### Increment 7 — real money (one to two days)

*Goal: a stranger funds the device from their own wallet and cashes out.*

Build `tick/chain.py`, `tick/escrow.py`.

```bash
python -m unittest tests.test_escrow          # a fake chain: no network, no keys
TICK_FUNDING=arc-testnet TICK_STAKE_USDC=0.001 python mygame.py
```

**Done when:** a deposit opens a session in the sender's name, the balance is
capped at what the escrow can pay, cash-out returns the money to the address it
came from, and a restart mid-cash-out finishes the job.
See [docs/money-arc.md](docs/money-arc.md).

### Increment 8 — a player people can point at (half a day)

*Goal: names and a leaderboard.*

Build `tick/identity.py`.

```bash
tick board
```

**Done when:** a wallet resolves to a name without any index, a name is trusted
only when it points back at the wallet, and the board survives an unreachable
RPC by keeping its last rows.
See [docs/identity-ens.md](docs/identity-ens.md).

### Increment 9 — polish that is not optional

Sound cues, music beds tied to what is at stake, the encoder's arming window,
rotation for a portrait panel, `tick doctor`. These read as garnish and are
not: the crossing swoops and the pitched countdown are how a player knows
whether they are winning **without looking at the screen**, which is the entire
point of a handheld you play with your thumb.

### Increment 10 — documentation somebody will actually read (half a day)

*Goal: the docs are a site, not a pile of files.*

Build `web/`: `mdlite.py` renders the Markdown that already exists, `build.py`
assembles pages, navigation, a search index and one page per source file.

```bash
tick docs
python -m unittest tests.test_web
```

**Done when:** every internal link resolves, every `#anchor` matches a real
heading, search finds a rule by its words rather than its page, and the whole
thing opens from `file://` with nothing installed. The Markdown stays the
source of truth — a docs site with its own copy of the prose is a docs site
that is wrong within a week.

---

## Part 5 — Extending it

Things the seams already allow, in rough order of value:

| Want | Where it goes | Notes |
|---|---|---|
| A new venue (Binance, a DEX aggregator) | a class in `tick/feeds/` with `poll`/`close` | register it in `open_feed` |
| A new asset | `ASSETS` in `tick/ticks.py` | needs a realistic `sigma`; a wrong one teaches wrong odds |
| A different bet shape (a ladder of ranges, a parlay) | your game, using several `ctx.bet` calls | the book already settles many bets per round |
| A house edge | `Game.house_edge = 0.03` | and say so on screen; hiding it teaches the player the wrong thing |
| Multi-round bets | `ctx.bet(..., rounds_ahead=3)` | already priced correctly: the horizon runs to that bell |
| A different chain | `NETWORKS` in `tick/chain.py` | the escrow interface is four calls |
| Your own names | `TICK_ENS_PARENT` and friends | nothing in `identity` is hardcoded to one parent |
| Two players on one device | a `BetBook` per wallet | `Wallet` and `BetBook` are already per-player objects |

### What is deliberately not here

* **No per-bet transaction.** A ten-second round cannot wait for a block, and
  nobody will approve forty transactions an hour. One deposit in, one
  settlement out; the rounds in between are the device's.
* **No anti-tamper on the device.** Prices and odds are computed on the
  handheld. That is fine for a device you hand someone; it is not fine for a
  product with an adversary, and the honest place to move it is a signed price
  attestation the escrow checks.
* **No account system.** The wallet is the account, the name is the profile,
  and the leaderboard is a read. There is nothing to sign up for and nothing
  to shut down.
