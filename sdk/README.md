# TICK SDK

Build a crypto arcade game for the TICK handheld in one file.

The device is a 480×320 landscape screen, a rotary dial, two buttons and a
speaker. A game on it is always the same shape: **a claim about where a price
will be at a known moment, backed by money**. This SDK owns everything around
that claim — the live price, the clock, the odds, the wallet, the settlement,
the input and the noise — so your game only has to say what a bet *is*, what
wins, and what it looks like.

```python
from tick import Game, run
from tick.hud import clear, draw_clock, draw_hud
from tick.ui import YELLOW, say

class Coinflip(Game):
    title = 'COINFLIP'
    window_s = 10.0

    def setup(self, ctx):
        self.pick = 'UP'

    def on_action(self, ctx, action):
        if action.name in ('UP', 'DOWN'):
            self.pick = action.name
        elif action.name == 'A':
            anchor = ctx.open_price
            ctx.bet(anchor, 1e9) if self.pick == 'UP' else ctx.bet(0.0, anchor)

    def draw(self, ctx, screen):
        clear(screen)
        say(screen, self.pick, 240, 120, 32, YELLOW, center=True)
        draw_clock(ctx, screen)
        draw_hud(ctx, screen)

run(Coinflip())
```

That is a complete, playable game with live prices, fair odds computed from
measured volatility, a round clock that never stops, an integer-USDC wallet,
dial and button input, and a full set of arcade sound cues.

## Install

```bash
cd sdk
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                 # demo play: only pygame
pip install -e ".[chain]"        # + real USDC settlement and ENS names
pip install -e ".[pi]"           # + the dial and the panel buttons
tick doctor                      # what is installed, and whether the feed answers
```

Python 3.11 or newer.

## Sixty seconds

```bash
tick new mygame          # scaffold a playable game
python mygame.py         # play it on simulated prices
tick prices --source coinbase --limit 10       # watch a live feed in the terminal
tick run mygame.py --source coinbase           # play it on real prices
```

## What you get

| Layer | Module | What it owns |
|---|---|---|
| Ticks | `tick.feeds` | one validated `PriceTick`; simulated, exchange, on-chain and recorded feeds |
| Market | `tick.market` | history, realized volatility, fresh / quiet / ready, probability of a range |
| Odds | `tick.pricing` | chance → fair multiple, with a cap, a floor and a house edge you set |
| Money | `tick.money` | integer micro-USDC wallet; nothing here is a float |
| Settlement | `tick.escrow` | deposits, sessions and payouts on-chain, on a worker thread |
| Identity | `tick.identity` | a readable name per wallet, and a leaderboard read from ENS |
| Rounds | `tick.rounds` | the clock that never stops, and refuses to settle on the wrong price |
| Bets | `tick.bets` | place, top up, settle, refund — the only code that moves money |
| Your game | `tick.game` | `Game` and `GameContext` |
| Loop | `tick.runtime` | `run()`: 30 FPS, input, cues, shutdown |
| Screen | `tick.hud`, `tick.ui` | price ladder, HUD, palette, synthesized sound |

## Documentation

All of it is also a **browsable site** with search, built from these same
Markdown files — open [`web/dist/index.html`](web/dist/index.html) straight
from disk, or:

```bash
tick docs                # build it and open a browser
python web/build.py      # build only, into web/dist/
```

* **[PLAN.md](PLAN.md)** — the system from first principles, with examples, and
  the increment-by-increment plan to build or extend it.
* [docs/writing-a-game.md](docs/writing-a-game.md) — the tutorial, start here.
* [docs/prices-substreams.md](docs/prices-substreams.md) — putting an on-chain
  price under your game: Substreams, the relay, and how many pools become one
  number you can settle on.
* [docs/money-arc.md](docs/money-arc.md) — real USDC: the escrow session model,
  why there is no transaction per bet, and how a player cashes out.
* [docs/identity-ens.md](docs/identity-ens.md) — giving every wallet a name and
  a public record with ENS, and reading a leaderboard back out of it.
* [docs/device.md](docs/device.md) — the screen, the dial, the buttons, the Pi.
* [docs/api.md](docs/api.md) — the whole public surface on one page.
* [web/README.md](web/README.md) — how the docs site is generated, and how to
  add a page to it.

## The command line

```
tick doctor                          what is installed, configured and reachable
tick new mygame                      scaffold a game
tick run mygame.py [--source ...]    play it
tick prices [--source coinbase]      print the feed
tick pools [-v]                      print every pool in the on-chain stream
tick record -o eth.ndjson --seconds 300      save a real market
tick replay eth.ndjson --speed 10            play it back
tick board                           the leaderboard, read from ENS
tick docs [--port 8000]              build the documentation site and open it
```

## Testing a game

Games that hold money need tests, and a game loop is testable only if it can
run without a window. `tick.testing.Harness` runs your real game class against
a real market on a clock you control:

```python
from tick.testing import Harness
from mygame import MyGame

def test_a_wide_bet_is_never_sold():
    h = Harness(MyGame(), seed=7).warm(25)
    assert h.ctx.bet(h.price * 0.5, h.price * 1.5) is None
    assert h.ctx.refused == 'TOO SURE TO SELL'
```

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m unittest discover -s tests -t .
```

## Settings

Everything is configured by environment, read from a `.env` beside your game
(copy `.env.example`). Anything set in the shell wins, so a one-off run is
`TICK_MARKET_SOURCE=coinbase python mygame.py`.

| Setting | Values |
|---|---|
| `TICK_MARKET_SOURCE` | `sim` · `coinbase` · `substreams` · `replay` · `frozen` |
| `TICK_ASSET` | `eth` · `btc` · `sol` · `hbar` |
| `TICK_FUNDING` | `demo` · `arc-testnet` |
| `TICK_STAKE_USDC` | money per bet, e.g. `10` or `0.001` |
| `TICK_WINDOW_S` | round length, if the game does not fix it |
| `TICK_ROTATE` | `auto` · `0` · `90` · `180` · `270` |
| `TICK_SOUND` | `1` · `0` |

## Examples

| File | What it shows |
|---|---|
| [`examples/coinflip.py`](examples/coinflip.py) | the smallest real game: up or down at the bell |
| [`examples/ladder.py`](examples/ladder.py) | park a box on the price — the shape most games take |
| [`examples/ticker.py`](examples/ticker.py) | the data layer with no game and no pygame |
| [`examples/pools.py`](examples/pools.py) | every pool in the on-chain stream, block by block |
