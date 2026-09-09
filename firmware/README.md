# TICK / BOX RUN

Native pygame game for a **480×320 landscape** handheld. Runs on desktop for development and on the Pi's configured SDL display.

**BOX RUN** is a box on the ETH price ladder and a clock that never stops. A 20-second window is always running; **cranking the dial moves your box** up and down, and **A buys the next 20 seconds** at wherever the box is sitting. At the bell, the window settles against the live price — inside the box and you're paid, outside and the stake is gone — and the next window starts in the same frame. There is no size step, no confirmation, and no early exit.

## Controls

The rotary encoder is the game: GPIO21 CLK, GPIO20 DT, GPIO16 switch, 3.3 V logic.

| Input | Action |
|---|---|
| Turn the dial | Move the box up/down the price ladder — until a bet is placed |
| Short click | Buy the next 20 seconds: +10 USDC on the box where the cursor is |
| Long click (0.65 s) | Back to the launcher |

Press A again in the same window and the extra 10 goes onto **the same box** — the first press fixes that window's level. After that the dial is **locked out entirely**: the box does not move, does not shrink, and no second cursor appears. Only money can still be added, and only by pressing A. The dial frees up again when the bell rolls the window over.

Spending money on a dial nudge would be worse than a dead dial, which is why adding stake stays on the button.

Desktop and touch equivalents: Up/Down (or W/S) held down emulates a spun dial, Right/Enter/Space is the short click, Left/Z/Backspace the long one, `F` opens the loader, and **Escape quits the program immediately** from any screen. On a desktop the game opens in a plain 480×320 window; only the Pi gets the fullscreen panel. Tapping the upper/lower half of the chart cranks the box.

`TICK_GAME=rush` still selects the earlier crank-a-flywheel game; `box` is the default.

## Reading the screen

Time runs left to right: the price trace covers the last 30 seconds, then the **NOW** column (this window's bell) and the **NEXT** one. There is never more than one box per column.

| On screen | Meaning |
|---|---|
| `MOVE +1.24` | How far the price has come since this window opened |
| Dashed grey line, `OPEN` | The price this window opened at — the chart is anchored here |
| Dotted white line | Where the price is now, carried across the columns so you can see it against your box |
| Solid yellow box, NOW | Your live bet, settling at this bell |
| Solid cream box, NEXT | Bought and locked for the next window |
| Dashed box, NEXT | The cursor, with its live quote. Gone once a bet is placed |
| `20 @ 2.0x` | Stake on that box and the multiple it pays |
| `BELL 07s` | Seconds until this window settles |
| Small triangle | The box sits past the top or bottom of the visible band |

**The chart is anchored on the window's opening price, not on spot.** Anchoring on spot re-centres the view every tick and pins the newest point to the middle of the screen, which makes movement impossible to see — the price appears still while the world slides around it. Against a reference that holds still for the whole window, a move reads immediately, and the `MOVE` figure puts a number on it.

## Odds

Distance is the whole risk decision, so the payout is priced from what the market is actually doing rather than a fixed table. Box height and crank step are set in standard deviations of a window's move — measured from the live tick stream — so the game plays the same whether ETH is flat or thrashing. Park the box on spot for roughly 2x; crank it a couple of sigma out for around 10x, capped at 25x.

The estimator is deliberately **median-based**: a mean of squared returns would let one flash spike or feed glitch inflate the box for several windows afterward. It is also cached per tick — the renderer asks for volatility once per plotted point, and rescanning the history hundreds of times a frame is not something the Pi can spare.

Two details that matter for fairness. Each press is priced at **that press's** odds, so topping up a box after the price walks toward it costs what it's worth then, not what it was worth when the level was fixed. And the horizon runs to the bell being bought, so buying 15 seconds early prices 35 seconds of drift — a different bet, not a free one.

## Settlement

Only the price **at the bell** counts; sailing through the box mid-window pays nothing, and the boundary counts as inside. A quote from before the bell cannot settle a window however fresh it looks, so the display holds on `SETTLING` until a price stamped after the bell arrives. If none arrives within 4 seconds, the window is **voided and the stake refunded** — settling a real bet against the wrong moment's price is worse than not settling it. A stale feed also blocks new bets.

## Money

Balances are integer **micro-USDC** (6 decimals, the real USDC unit) so a session cannot accumulate float drift; payouts truncate downward rather than rounding money into existence. `wallet.py` holds the funding seam:

| `TICK_FUNDING` | Backend | Behavior |
|---|---|---|
| `demo` (default) | `DemoFunding` | Starts at 100 and mints local play money on +10/+25/+100 |
| `usdc` | `UsdcFunding` | The real deposit shape — starts at 0 and **credits nothing** |

`UsdcFunding` is deliberately inert. A working version needs a session key on the device, an ERC-20 `transfer`/`permit` of the amount to that key on a chosen chain, and confirmation polling before the balance moves; the wallet credits only a deposit whose status comes back `confirmed`. There is no wallet, key, transfer or settlement in this build, and the odds carry no house edge — a real venue must charge one and fund payouts from somewhere.

## Prices

| `TICK_MARKET_SOURCE` | Feed |
|---|---|
| `sim` (default) | Seeded 20 Hz Gaussian walk. Tick spacing is counted in integer microseconds, so the same wall-clock time produces the same ticks at any frame rate |
| `coinbase` | Public Coinbase REST ticker at 5 Hz on a worker thread, read-only |

A 20-second window needs a trace rather than a staircase, which is why the live adapter polls at 5 Hz (well inside the public rate limit) instead of once a second. Payloads are validated before use — finite positive price, timezone-aware timestamp, no future stamp — and carry a sequence number and source age, so out-of-order or stale ticks cannot price or settle anything. A production adapter should use the venue's WebSocket trade stream.

Trading is **paper** in every configuration: the feed is read-only and no order leaves the device.

## Run, test, capture

```sh
cd firmware
.venv/bin/python main.py                    # or: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m unittest discover -s tests -v
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python capture_box.py
```

On Raspberry Pi, install the distribution's `python3-pygame` and run `python3 main.py` with the panel configured; the display bootstrap may re-exec under system Python for KMSDRM support.

Captures go to `design/box-run-live/` at native 480×320, rendered by the real game rather than image generation. Tests cover the window clock rolling on its own, buying and topping up, the cursor never moving a bought box, box height tracking measured volatility, fair odds against the stated probability, the multiple cap, inside/boundary/outside settlement, pre-bell quotes being rejected, voiding after a feed gap, whole-micro payouts, and every screen rendering.

## Pi display note

`hardware.md` records a prior Pi 5 setup, including KMSDRM device index **2**. The actual Pi Zero 2 W may use another index. Set `SDL_VIDEO_KMSDRM_DEVICE_INDEX` for the connected panel when running without a desktop; do not assume the Pi 5 card index applies. Display overlays, refresh rate, encoder direction and physical fit still need on-device verification, as does whether the SPI panel sustains the target 30 FPS full-frame redraw.
