# TICK / BOX RUN

Native pygame game for a **480×320 landscape** handheld. Runs on desktop for development and on the Pi's configured SDL display.

**BOX RUN** is a box on the ETH price ladder and a clock that never stops. A 10-second window is always running; **cranking the dial moves your box** up and down, and **A buys the next 10 seconds** at wherever the box is sitting. At the bell, the window settles against the live price — inside the box and you're paid, outside and the stake is gone — and the next window starts in the same frame. There is no size step, no confirmation, and no early exit.

The box is **always the same size** — $1.41 on $2,500 ETH — so there is nothing to learn about it and nothing that changes under you. How far you park it from spot is the only decision, and only the *payout* reacts to the market.

## Controls

The rotary encoder is the game: GPIO21 CLK, GPIO20 DT, GPIO16 switch, 3.3 V logic.

| Input | Action |
|---|---|
| Turn the dial | Move the box up/down the price ladder — until a bet is placed |
| Short click | Buy the next 10 seconds: +10 USDC on the box where the cursor is |
| Long click (0.65 s) | Back to the launcher |

Press A again in the same window and the extra 10 goes onto **the same box** — the first press fixes that window's level. After that the dial is **locked out entirely**: the box does not move, does not shrink, and no second cursor appears. Only money can still be added, and only by pressing A. The dial frees up again when the bell rolls the window over.

Placing a bet turns the dashed box **solid where it stands**, with a pop. That is the signal that the dial is no longer yours: turn it anyway and the box shakes and the status line says `BOX LOCKED / A ADDS 10`.

Spending money on a dial nudge would be worse than a dead dial, which is why adding stake stays on the button.

Desktop and touch equivalents: Up/Down (or W/S) held down emulates a spun dial, Right/Enter/Space is the short click, Left/Z/Backspace the long one, `F` opens the loader, and **Escape quits the program immediately** from any screen. On a desktop the game opens in a plain 480×320 window; only the Pi gets the fullscreen panel. Tapping above the aim box raises it and tapping below lowers it (`design/box-run-live/touch-zones.png`); buying stays on the button.

`TICK_GAME=rush` still selects the earlier crank-a-flywheel game; `box` is the default.

The launcher is an attract screen in the same night city: the rider runs a scripted demo loop — a hit, a backflip, a hat trick, then a greedy miss that puts the fire out — under a bobbing logo, with the live ETH price in the corner. The demo line is made up; the ticker and the balance are real. PLAY and LOAD USDC sit on the street; the dial toggles between them, and tapping anywhere in the scene plays.

## Reading the screen

Time is one horizontal scale across the whole screen, 16 px a second. A rider on a one-wheeler sits a quarter of the way in at *now*, the wheel resting on the live price; history trails off to the left, and every bell is a dotted post ahead that slides toward the wheel. A box is drawn centred on the post of the bell it settles at, so it arrives under the wheel at the exact moment it is judged: be inside it as you pass through and you're paid. There are no columns.

| On screen | Meaning |
|---|---|
| `+0.62` beside the price | How far the price has come since this window opened |
| Dashed grey line, `OPEN` | The price this window opened at — the chart is anchored here |
| `07s` over a post | Time to this window's bell |
| Dotted line ahead of the wheel | Where the price is now, carried forward to read against the boxes |
| Solid yellow box | Your live bet, arriving at this bell; it glows while the price is inside |
| Solid cream box | Bought and locked for the next bell |
| Dashed yellow box | The cursor, with its live quote; a fresh one slides in from the right after every bell |
| Green / red box behind the rider | A box that already settled, with a dot where the price landed |
| `20 @ 2.0x` | Stake on that box and the multiple it pays |
| Small triangle | The box sits past the top or bottom of the visible band |

The wheel is a single wheel on purpose: the price line is jagged, and legs or a two-wheeled base would visibly clip into it, while one wheel touches it at exactly one point. The rider leans into the slope and reacts to results — a hop on a hit, a backflip on 5x or better, a wobble on a miss. **Three hits in a row is a hat trick**: the rider leans back into a one-wheel wheelie with a jetpack on fire, and stays lit until a miss puts it out.

The scene — sky, two parallax rows of city, the street, the rider — is drawn in code (`games/box_scene.py`), like the sound, with no image assets. Everything moves on the clock rather than on ticks, and the wheel, the camera and the cursor ease toward where the model says they are, so a price tick or a detent is a glide rather than a jump.

The visible band is exactly **two box-heights either way** (±$2.83 on $2,500 ETH), which is what makes a dollar of drift a visible swing rather than a wobble. Widening it to fit every reachable box would flatten the price back out, so a box cranked to the far edge is clamped with a triangle instead.

**The chart is anchored on the window's opening price, not on spot.** Anchoring on spot re-centres the view every tick and pins the newest point to the middle of the screen, which makes movement impossible to see — the price appears still while the world slides around it. Against a reference that holds still for the whole window, a move reads immediately, and the `MOVE` figure puts a number on it.

## Odds

Distance is the whole risk decision, so the payout is priced from what the market is actually doing rather than a fixed table. Park the box on spot for roughly 2x; crank it to the edge of its reach for 10x or more, capped at 25x.

Geometry is fixed in basis points of the window's opening price — a $1.41 box, 18c crank steps and $2.12 of reach on $2,500 ETH — so **volatility moves the odds and never the box**.

Those numbers are quoted for a 20-second window and **scaled by the square root of time**, because that is how far a price travels. `WINDOW_S` is therefore a safe knob: halving it without shrinking the box would leave a box on spot a near-certainty paying 1.2x and everything else pinned to the cap — a flatter game, not a faster one. Scaled, ten-second windows keep the ladder the twenty-second build had: about 1.5x on spot at the bell, 25x at full reach, 2.0x to 9.7x for the same boxes bought a window early. Sizing the box in sigma instead (as this first did) means a bet already placed gets redrawn at a different size when the market picks up, which is both confusing and dishonest about what you bought. The cost of fixing it is that a violent market makes the same box genuinely hard to hit; the multiple rises to match, which is the honest response rather than quietly making the target bigger.

The estimator is **realized variance over the last minute of wall time**: squared returns summed and divided by the time they span, with time spent sitting on one price counted as exactly that. A pool nobody swaps in, or a ticker with no new trade, is a calm market — and the bell settles on that same price, so pricing it as a typical one sells a near-certain box at 2x. The first version skipped repeated prices and fell back to "typical ETH" whenever it saw too few moves, which is precisely what a flat Coinbase or Substreams stretch produces: parking the box on the line won 58 bets out of 58. A flash spike or feed glitch is kept from inflating the odds by capping each move at four times the median move. And every estimate is made as if the window began with ten seconds of ordinary ETH, so the first seconds of data, or a market just waking from a lull, are not priced as if nothing could move; a minute of real data outweighs that six to one. The estimate is cached per tick, so the renderer can ask for it freely.

**A quiet market sells nothing.** If the price has not changed for 15 seconds, A refuses with `MARKET QUIET / NO BETS` and the aim box reads `QUIET`: on a line that never moves, a box on spot is a certain win at any multiple over 1x. Nothing that quotes under 1.05x is sold either: a near-certain box is not a bet worth selling. At start-up nothing is sold until the feed has been read — it has moved, with three seconds or ten moves behind it, since a feed that has not moved yet cannot be told from a dead one — and the screen says `READING THE MARKET...`; prices are read from boot, behind the launcher, so this is normally over before you press play. Bets already down ride to their bell as normal.

Two details that matter for fairness. Each press is priced at **that press's** odds, so topping up a box after the price walks toward it costs what it's worth then, not what it was worth when the level was fixed. And the horizon runs to the bell being bought, so buying 15 seconds early prices 35 seconds of drift — a different bet, not a free one.

## Sound

Everything is synthesized at startup — square waves, no audio assets, no dependencies — and it builds in about 0.16s.

### Music

Three looping beds, and the game picks one every frame from what is actually at stake:

| Bed | When | What it is |
|---|---|---|
| `idle` | Launcher, or nothing staked | Sparse A-minor bass and a slow arpeggio |
| `live` | Money on the next or current window | Driving bass, fast arpeggio, offbeat hats |
| `final` | Last three seconds of a live bet | Same bass, a tense descending lead, hats on every step |

Each bed is layers of **monophonic** 2-second loops, one per reserved mixer channel, so the mixer does the polyphony and Python never mixes a sample — which matters, because `audioop` was removed in 3.13. Loops are assembled from a cached palette of note renders rather than computed per sample per bar, which is the difference between 0.16s and several seconds of work at boot on a Pi. Every layer in every mode is exactly the same length, so switching bed restarts the bar cleanly instead of drifting the parts apart.

### Cues

A clip is a list of (start_hz, end_hz, seconds) segments, with phase carried across segments so a clip can glide in pitch instead of only beeping. Every cue answers a question you would otherwise have to read off the screen:

| Cue | When |
|---|---|
| Rising detent clicks | Every crank step, pitched by how far out the box has moved — the risky end of the reach sounds higher |
| `buy1` → `buy2` → `buy3` | Stacked presses on the same box, each a note higher |
| Upward swoop | The price just crossed **into** your live box |
| Downward swoop | It just crossed **out** |
| Ticks in the last 3s | Pitched high if the money is currently winning, low if it is not, and doubling in rate inside the final two seconds |
| Two-tone bell | A window rolled with no money down — the game's heartbeat. A result speaks instead of the bell |
| Fanfare | A win, longer and higher above 5x |
| Falling thud | A miss, or a flat neutral one for a voided window |
| Longer, higher fanfare | A jackpot at 15x or more |
| Tiny high click | The box passing over spot as you crank through it |
| Double low buzz | Cranking a box that is already locked |
| Falling sweep | The price feed went stale |
| Blip / rising chime / falling chime | Menu move, entering the game, backing out |
| Two-note chime | USDC loaded |

The two that matter most are the box-crossing swoops and the pitched countdown: together they tell you whether you are winning without looking, which is the whole point of a handheld you play with your thumb.

Levels are sized so three overlapping cues plus a bed peak at about 21k of 32767 — nothing clips, and the music sits at roughly half the level of the cues.

**Audio output on the Pi.** A Pi 5 has no analog jack, so ALSA alone offers only the two HDMI outputs and opening one fails with nothing connected. Sound works through the **pipewire-pulse** server instead — on this device that reaches a paired Bluetooth speaker. Do not force `SDL_AUDIODRIVER=alsa`: it bypasses the sound server and finds only the dead HDMI sinks. If the mixer cannot open at all, the game runs silently by design (`Sounds` catches it and every `play` and `music` becomes a no-op, which is tested).

Bluetooth adds 100-200ms of latency, so crank clicks trail the dial. A USB audio dongle is tighter; an I2S DAC such as a MAX98357A is tightest, but **it wants GPIO18/19/21 and GPIO21 is currently the encoder's CLK pin**, so the encoder would have to move first.

## Settlement

Only the price **at the bell** counts; sailing through the box mid-window pays nothing, and the boundary counts as inside. A quote from before the bell cannot settle a window however fresh it looks, so the display holds on `SETTLING` until a price stamped after the bell arrives. If none arrives within 4 seconds, the window is **voided and the stake refunded** — settling a real bet against the wrong moment's price is worse than not settling it. A stale feed also blocks new bets.

## Money

Balances are integer **micro-USDC** (6 decimals, the real USDC unit) so a session cannot accumulate float drift; payouts truncate downward rather than rounding money into existence. `wallet.py` holds the funding seam:

| `TICK_FUNDING` | Backend | Behavior |
|---|---|---|
| `demo` (default) | `DemoFunding` | Starts at 100 and mints local play money on +10/+25/+100 |
| `arc-testnet` | `arc.ArcFunding` | Real Arc testnet USDC through the [`TickEscrow`](../contracts/) contract. BOX RUN only |

`TICK_STAKE_USDC` sets the stake per press of A in BOX RUN and per ride in RUSH: 10 by default, as little as 0.000001. It is parsed as an exact decimal, and labels and balances show as many decimals as the stake has, so a 0.001 stake reads `0.001`, never `0.00`.

**Real USDC.** With `TICK_FUNDING=arc-testnet` the money screen (ADD USDC on the launcher) shows the device's own Arc address as a QR code. Scan it in MetaMask and send any amount of USDC on Arc testnet. The device watches Arc for transfers to itself, keeps 0.01 of each for gas (USDC is Arc's gas token; set it with `TICK_GAS_FEE_USDC`), and locks the rest in `TickEscrow` with `openFor`, in the sender's name. That takes about 8 seconds. The launcher then shows `+0.49 USDC FROM 0x7ee8..CCac` and its money button turns into CASH OUT.

Bets run on the device exactly as in demo play. CASH OUT refunds a box bought for the next window, lets the live one land, then closes the session with the final balance, and the escrow pays it straight back to the address the USDC came from. The escrow pays out at most 5x a deposit, so a press that could win past that is refused with `MAX WIN REACHED / CASH OUT`. A deposit the house cannot cover, or one over the 2.5 USDC maximum, is sent back.

The device key is created on first run in `firmware/.tick/device.json`, and the open sessions, balance and last block read are saved in `.tick/arc-testnet.json`; the folder is gitignored. A restart resumes play and finishes an interrupted cash-out. Chain work runs on its own thread, so a slow RPC never stalls a frame. Real funds need `eth-account` and `qrcode` from `requirements.txt`; demo play does not. The odds still carry no house edge.

## Prices

| `TICK_MARKET_SOURCE` | Feed |
|---|---|
| `sim` (default) | Seeded 20 Hz Gaussian walk at roughly live ETH volatility — about 0.03% over ten seconds. Tick spacing is counted in integer microseconds, so the same wall-clock time produces the same ticks at any frame rate |
| `coinbase` | Public Coinbase REST ticker at 5 Hz on a worker thread, read-only |
| `substreams` | ETH/stable pools on Arbitrum and Base (Uniswap v3 and v4, Aerodrome Slipstream), from The Graph's Substreams via `substreams/relay.py` on a laptop or server at `SUBSTREAMS_BASE_URL`. One tick per block, priced as the liquidity-weighted average of the pools, leaving out any pool more than 0.5% from the rest, and aged by block time |

`TICK_ASSET` picks the coin: `eth` (default), `btc`, `sol` or `hbar`, each priced in USD, and HBAR shown to five decimals. `sim` starts each coin at a typical price and walks it at that coin's rough live volatility, and `coinbase` polls its `-USD` product. `substreams` watches ETH pools only, so it refuses any other coin. Box geometry is in basis points of price, so the game plays the same on any of them.

The Substreams feed repeats the last price on blocks where nothing traded, because that is still each pool's price. Volatility therefore counts only moves, measured from the previous move, or those repeats would read as a calm market.

Settings like this one live in `firmware/.env` (copy `.env.example`), which `main.py` reads at startup. A value set in the shell overrides the file, so `TICK_MARKET_SOURCE=coinbase .venv/bin/python main.py` works for a one-off run.

A 20-second window needs a trace rather than a staircase, which is why the live adapter polls at 5 Hz (well inside the public rate limit) instead of once a second. Payloads are validated before use — finite positive price, timezone-aware timestamp, no future stamp — and carry a sequence number and source age, so out-of-order or stale ticks cannot price or settle anything. A production adapter should use the venue's WebSocket trade stream.

The feed is read-only. With demo money every bet is paper; with `arc-testnet` the bets still run on the device, and only deposits and cash-outs touch the chain.

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
