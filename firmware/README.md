# TICK / RUSH

Native pygame game for a **480×320 landscape** handheld. Runs on desktop for development and on the Pi's configured SDL display.

**RUSH** is one continuous action: turn the dial and you are in the market. There is no aim step, no size step and no confirm screen — the first two detents open a leveraged position in the direction you turned, and every detent after that pumps a flywheel whose level *is* your leverage. Stop turning and the flywheel bleeds down; let it die and the ride closes itself. The result appears in place, so cranking straight through it opens the next ride.

## Run

```sh
cd firmware
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

If the existing venv already has pygame, just run `.venv/bin/python main.py`. On Raspberry Pi, install the distribution's `python3-pygame` and run `python3 main.py` with the panel configured; the display bootstrap may re-exec under system Python for KMSDRM support.

## Controls

The rotary encoder is the whole game: GPIO21 CLK, GPIO20 DT, GPIO16 switch, 3.3 V logic.

| Input | Action |
|---|---|
| Turn forward | Open a LONG, then keep the flywheel (and leverage) up |
| Turn back | Open a SHORT, then keep the flywheel up |
| Short click | Open the USDC loader (only when no ride is live) |
| Long click (0.65 s) | Bail out of a ride; from idle, back to the launcher |

Desktop and touch equivalents for development: Up/Down (or W/S) held down emulates a spun dial, Right/Enter/Space is the short click, Left/Esc the long one, `F` opens the loader. Tapping the upper/lower half of the chart cranks forward/back; the bottom-left and bottom-right corners are the two buttons. Mouse events synthesized from touch are ignored to avoid double actions.

Inside a ride the encoder is read as raw motion so no detent is dropped or queued — a stopped hand stops pumping in the same frame. Menus keep the rate-limited scrolling so one whip-spin does not run through the whole list.

## Ride rules

Each ride stakes **10 USDC** and closes for any of four reasons: you bail out, the crank goes quiet for 1.6 s, the feed goes stale, or the position is liquidated. Leverage runs 1x–10x and is a direct readout of the flywheel: `+0.13` per detent, bleeding `0.55` per second, so leverage reflects how hard the dial is being turned right now.

PnL is marked on the quantity held *before* each price move and only then repriced, so cranking can never retroactively multiply a gain that is already made. A losing ride is floored at the stake (`Liquidated` at 0 equity) and never touches the rest of the balance. Exits always execute on a fresh quote: bailing out during a feed gap marks `CLOSING AT NEXT PRICE` and settles on the first usable tick rather than inventing a fallback price.

## Money

Balances are integer **micro-USDC** (6 decimals, the real USDC unit) so a session cannot accumulate float drift; settlement truncates sub-micro dust downward rather than rounding money into existence. `wallet.py` holds the funding seam:

| `TICK_FUNDING` | Backend | Behavior |
|---|---|---|
| `demo` (default) | `DemoFunding` | Starts at 100 and mints local play money on +10/+25/+100 |
| `usdc` | `UsdcFunding` | The real deposit shape — starts at 0 and **credits nothing** |

`UsdcFunding` is deliberately inert. A working version needs a session key on the device, an ERC-20 `transfer`/`permit` of the amount to that key on a chosen chain, and confirmation polling before the balance moves; the wallet only credits a deposit whose status comes back `confirmed`, so a pending or failed load leaves the balance alone. There is no wallet, key, transfer or settlement in this build.

## Prices

| `TICK_MARKET_SOURCE` | Feed |
|---|---|
| `sim` (default) | Seeded 20 Hz Gaussian walk. Tick spacing is counted in integer microseconds, so the same wall-clock time produces the same ticks at any frame rate. |
| `coinbase` | Public Coinbase REST ticker at ~1 Hz on a worker thread, read-only. |

Live payloads are validated before use (finite positive price, timezone-aware timestamp, no future stamp) and carry a sequence number and source age; out-of-order or stale ticks cannot price a position. A quote older than 4 s is stale and blocks new exposure. For real low-latency execution this adapter should be replaced by the venue's WebSocket book/fill streams.

Trading is **paper** in every configuration: the feed is read-only and no order ever leaves the device.

## Tests and actual UI captures

```sh
cd firmware
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m unittest discover -s tests -v
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python capture_rush.py
```

Captures go to `design/rush-build/` at native 480×320 and are rendered by the real game, not by image generation. Tests cover arming and reversal, leverage tracking and its cap, the no-retroactive-leverage rule, liquidation at the stake, exact stake return in a flat market, crank-stop and stale-feed exits, deposit crediting, feed validation, encoder continuous vs menu mode, frame-rate independence, and rendering every screen.

## Pi display note

`hardware.md` records a prior Pi 5 setup, including KMSDRM device index **2**. The actual Pi Zero 2 W may use another index. Set `SDL_VIDEO_KMSDRM_DEVICE_INDEX` for the connected panel when running without a desktop; do not assume the Pi 5 card index applies. Display overlays, refresh rate, encoder direction and physical fit still need on-device verification, as does whether the SPI panel sustains the target 30 FPS full-frame redraw.
