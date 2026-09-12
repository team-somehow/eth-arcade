# The public surface, on one page

Everything you can import, what it does, and what it returns. Imports below are
what actually works; `from tick import X` covers the common ones.

---

## `tick` — the top level

```python
from tick import Game, GameContext, run, Runtime, InputAction
from tick import Market, open_feed, PriceTick, Asset, ASSETS, PoolStream
from tick import Wallet, MICRO, parse_usdc, format_usdc, stake_micro
from tick import RoundClock, Round, Bet, BetBook, Settlement
from tick import probability, multiple, sigma, scale_to_window
```

---

## `Game` — what you subclass

| Attribute | Default | Meaning |
|---|---|---|
| `title` | `'TICK GAME'` | window title and HUD label |
| `window_s` | `10.0` | round length; `TICK_WINDOW_S` overrides |
| `stake_usdc` | `None` | per bet; `None` means `TICK_STAKE_USDC` |
| `max_multiple` | `25.0` | never quote more than this |
| `min_multiple` | `1.05` | never sell under this |
| `house_edge` | `0.0` | `0.03` keeps 3% |
| `rounds_ahead` | `1` | `1` = the next bell; `0` = the round already running |
| `arm_s` | `0.0` | swallow bets for this long after a bell |
| `sound_cues` | `True` | the SDK plays the generic cues |
| `music` | `True` | the SDK picks the bed from what is at stake |

| Hook | Called |
|---|---|
| `setup(ctx)` | once, after everything is up |
| `teardown(ctx)` | once, on the way out |
| `on_tick(ctx, tick)` | a price arrived and was folded in |
| `on_round_start(ctx, round_)` | a round opened |
| `on_round_end(ctx, round_)` | a round rang; its bets have settled |
| `on_settle(ctx, settlement)` | one of your bets was paid or lost |
| `on_action(ctx, action)` | dial or button; return `'quit'` to leave |
| `on_touch(ctx, pos)` | a tap, in canvas pixels |
| `update(ctx, dt)` | every frame, before drawing |
| `draw(ctx, screen)` | every frame |

---

## `GameContext` — what every hook is handed

**State**

| | |
|---|---|
| `ctx.price` | last price |
| `ctx.open_price` | the round's opening price — anchor your view here |
| `ctx.move` | how far the price has come since the round opened |
| `ctx.remaining` | seconds to the bell |
| `ctx.round` | the `Round` now running |
| `ctx.now` / `ctx.dt` / `ctx.frame` | monotonic seconds, frame delta, frame count |
| `ctx.armed` | `False` for `arm_s` after a bell |
| `ctx.stake` | micro-USDC per bet |

**Betting**

| | |
|---|---|
| `ctx.bet(low, high, stake=None, rounds_ahead=None, label='')` | place; `None` if refused |
| `ctx.quote(low, high, rounds_ahead=None)` | the multiple right now |
| `ctx.can_bet()` / `ctx.why_not()` | may I sell, and why not |
| `ctx.refused` | why the last `bet` returned `None` |
| `ctx.horizon()` | seconds to the bell a bet placed now settles at |
| `ctx.would_exceed_cap(stake, multiple)` | past what the escrow can pay? |
| `ctx.cancel_next()` | refund bets on the round that has not started |

**Your bets**

| | |
|---|---|
| `ctx.live_bets` | settling at the next bell |
| `ctx.next_bets` | bought for the bell after that |
| `ctx.inside` | is the price inside a live bet? `None` if none |
| `ctx.staked` | money at risk |

**Objects and output**

| | |
|---|---|
| `ctx.market` `ctx.wallet` `ctx.rounds` `ctx.book` `ctx.sounds` `ctx.game` `ctx.screen` | |
| `ctx.play(cue)` | one of the cue names below |
| `ctx.note(text, seconds=2.0)` | a line for the status bar |
| `ctx.status_line()` | the note, else the refusal reason, else `''` |
| `ctx.usdc(micro=None)` | format with the decimals this game's stake needs |
| `ctx.quit()` | leave |

---

## `tick.feeds`

```python
open_feed(source=None, seed=None, asset=None, **kwargs) -> BaseFeed
```
`source`: `sim` · `coinbase` · `substreams` · `replay` · `frozen`; defaults to
`TICK_MARKET_SOURCE`.

| | |
|---|---|
| `feed.poll(dt, now) -> list[PriceTick]` | non-blocking |
| `feed.stream(interval=0.05, limit=None)` | blocking generator, for scripts |
| `feed.close()` · `feed.name` · `feed.status` · `feed.asset` | |

| Class | Notes |
|---|---|
| `SimulatedFeed(seed, asset, volatility=None)` | 20 Hz seeded walk |
| `FrozenFeed(price, asset)` | never moves; for testing refusals |
| `CoinbaseFeed(asset)` | 5 Hz public REST, worker thread |
| `SubstreamsFeed(base_url)` | one tick per block, many pools combined |
| `ReplayFeed(path, speed=1.0, loop=False)` | a recording |
| `Recorder(feed, path)` | wraps any feed and writes every tick |
| `PoolStream(base_url).blocks()` | raw per-pool, per-block `Block` objects |
| `PoolBook()` | `.apply(line, now)` · `.price(now)` · `.live_pools(now)` |

`PriceTick(price, sequence, received_at, source_age)` · `.age(now)`

---

## `tick.market`

```python
Market(feed=None, source=None, seed=None, **kwargs)
```

| | |
|---|---|
| `.poll(dt, now=None)` | read the feed and fold in; returns accepted ticks |
| `.accept(tick, now) -> bool` | validate and fold one tick |
| `.price` `.tick` `.history` `.asset` `.name` `.status` | |
| `.fresh(now)` `.quiet(now)` `.ready` | |
| `.sellable(now)` `.why_not(now)` | may a bet be sold, and why not |
| `.variance` | realized variance per second (cached) |
| `.sigma(horizon)` | one standard deviation over that horizon |
| `.probability(low, high, horizon)` | chance of landing in the range |
| `.quote(low, high, horizon, edge=0, cap=25)` | the multiple |
| `.band(sigmas, horizon)` | half-width of an N-sigma box |

Constants worth knowing: `STALE_AFTER=4.0`, `VOL_WINDOW_S=60.0`,
`QUIET_AFTER=15.0`, `SPIKE_CAP=4.0`, `PRIOR_S=10.0`.

---

## `tick.pricing`

```python
normal_cdf(x)
sigma(price, variance_per_second, horizon)
probability(price, low, high, variance_per_second, horizon)
multiple(chance, edge=0.0, cap=25.0)
scale_to_window(value_bps, window_s, reference_s=20.0)
annualized(variance_per_second)
```

---

## `tick.money`

```python
Wallet(balance=100*MICRO, funding=None)
```
`.balance` `.debit(n) -> bool` `.credit(n)` `.can_afford(n)` `.cap`
`.live` `.onchain` `.load(usdc)` `.would_exceed_cap(best)`

```python
MICRO                      # 1_000_000
to_micro(1.5)              # 1_500_000  (truncates)
parse_usdc('0.57')         # 570000     (exact; raises on >6 decimals)
format_usdc(570000, 2)     # '0.57'
places_for(1000)           # 3
stake_micro()              # from TICK_STAKE_USDC
DemoFunding()              # paper money
```

---

## `tick.rounds`

```python
RoundClock(window_s=10.0, void_after=None)
```
`.start(price, now)` · `.update(now, price, settleable) -> list[Round]`
`.remaining(now)` `.progress(now)` `.horizon(now, rounds_ahead)` `.move(price)`
`.index` `.open_price` `.ends_at` `.settling` `.current` `.closed`

`Round(index, open_price, opened_at, ends_at)` → `.close_price` `.voided`
`.move` `.remaining(now)` `.progress(now)`

---

## `tick.bets`

```python
BetBook(wallet)
```
`.place(round_index, low, high, stake, multiple, label='') -> Bet | None`
`.settle(round_) -> list[Settlement]` · `.refund(round_index)` ·
`.refund_all()` · `.for_round(i)` · `.staked()` · `.best_case()` ·
`.last` · `.streak` · `.history` · `.open`

`Bet` → `.low` `.high` `.level` `.half` `.stake` `.payout` `.multiple`
`.presses` `.label` `.contains(price)`

`Settlement` → `.hit` `.price` `.stake` `.payout` `.multiple` `.voided` `.net`

---

## `tick.escrow` and `tick.chain`

```python
build_wallet(kind=None)        # TICK_FUNDING: 'demo' or 'arc-testnet'
EscrowFunding(kind, chain=None, state_dir='.tick', gas_fee=None, start=True)
```
`.qr_text` `.in_session` `.cap` `.player` `.status` `.busy` `.error`
`.sync(wallet)` `.cash_out(wallet)` `.step()` `.stop()` `.tx_url(tx)`

```python
Chain(network(kind), load_device())     # block, incoming, house, open_for, close, transfer
Rpc(url)(method, *params)
NETWORKS['arc-testnet']
```

---

## `tick.identity`

```python
handle(address, attempt=0)              # 'amber-otter'
name_of(address, net=None, rpc=None)    # 'amber-otter.tick.eth' | None
records_of(rpc, name, keys=STATS)       # one Universal Resolver call
Standings(net=None, rpc=None, keys=STATS).read() -> list[Standing]
Leaderboard(read=None)                  # threaded: .want() .rows .error .showing
namehash(name) · dns_encode(name) · coin_type(chain_id) · ens()
```

---

## `tick.hud` and `tick.ui`

```python
clear(s) · draw_hud(ctx, s, back, go) · draw_clock(ctx, s, x, y)
Ladder(centre, half, top=34, bottom=268)     # .y_of .price_at .rect .clamped_y
draw_grid · draw_open_line · draw_bet · draw_cursor · draw_price_line
```

```python
NAVY PANEL GRID CREAM MUTED YELLOW MINT RED
font(size) · label(...) · say(...) · say_right(...) · footer(...) · dashed_rect(...)
Sounds()      # .play(cue) .music(mode) .detent(fraction) .ok
```

**Cues:** `bell` `hot` `cold` `tick_in` `tick_out` `buy1` `buy2` `buy3`
`win_small` `win_big` `jackpot` `hattrick` `fizzle` `void` `warn` `stale`
`crossline` `nav` `enter` `back` `coin` `move` `select` `lock` `tick` `hit`
`miss` `detent0`–`detent7`.
**Beds:** `idle` `live` `final` `off`.

---

## `tick.input` and `tick.display`

```python
InputAction.UP / DOWN / A / B / QUIT
actions_from_event(event) · event_position(event) · HeldKeys()
EncoderInput.try_open(clk=21, dt=20, sw=16, invert=False)   # None off-Pi
ButtonPad.try_open(red=13, yellow=26)                       # None off-Pi
```

```python
WIDTH, HEIGHT = 480, 320 ; FPS = 30
bootstrap() · init_display(title) · present() · to_canvas(fx, fy)
display_to_canvas(pos) · rotation()
```

---

## `tick.testing`

```python
Harness(game, feed=None, source='sim', seed=7, balance=1000*MICRO,
        stake=None, window_s=None, start=1000.0)
```
`.warm(25)` `.advance(seconds)` `.frame(dt, actions, touches)` `.press(action)`
`.touch(pos)` `.draw_once()` `.close()` · `.ctx` `.market` `.wallet` `.rounds`
`.book` `.price` `.balance` `.settled`

```python
FakeClock(start=1000.0)          # a monotonic clock you move by hand
ScriptedFeed([(t, price), ...])  # exactly the ticks you list
```

---

## `tick.env`

```python
load_env_file(path=None) · load_env_near(start) · flag(name, default)
number(name, default) · text(name, default)
```
