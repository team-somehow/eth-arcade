# ethonline-2026

TICK: a landscape **480×320** pygame crypto arcade for a Raspberry Pi handheld. **BOX RUN** is playable now: a box on the ETH price ladder and a 20-second clock that never stops — crank the dial to move the box, press A to buy the next 20 seconds. Prices are read-only. Money is paper by default; with `TICK_FUNDING=arc-testnet` it is real Arc testnet USDC: send it to the QR code on the device, play, and cash out back to the wallet it came from, through the [`TickEscrow`](contracts/) contract.

## Layout

| Path | What |
|------|------|
| [`firmware/`](firmware/) | Launcher + playable BOX RUN |
| [`design/`](design/) | Device renders, concept archive and actual game screenshots |
| [`substreams/`](substreams/) | The live ETH/USDC price: a Substreams module for Arbitrum and Base, the relay that serves it to the device, and `pools.py`, which finds pools in Messari's subgraphs |
| [`contracts/`](contracts/) | `TickEscrow`: USDC session escrow on Arc, with the owner as the house. Testnet: [`0x4FA3…8627`](https://testnet.arcscan.app/address/0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627) |
| [`ens/`](ens/) | Every player's wallet gets a `tick.eth` name on ENSv2 (Sepolia), with their stats as text records only the scorekeeper may write; the leaderboard is read back from ENS, on the device's LEADERS screen too |

## Where the prices come from

Every bet settles on the ETH/USDC price at the bell, so that price has to be live, updated every block, and hard to push. It comes from The Graph:

- **Substreams** (from The Graph Market) streams the swaps in every watched ETH/USDC pool on Arbitrum and Base, block by block: Uniswap v3 and v4 and Aerodrome Slipstream today, and any Sushiswap V3 pool `pools.py` adds. The module is built on Pinax's `uniswap_v3` and `uniswap_v4` packages, so it decodes no logs itself, and the same compiled module runs on both chains with only the pool list changed.
- **Messari's standardized subgraphs** say which pools to watch. They share one schema across protocols and chains, so `pools.py` asks Uniswap V3 and Sushiswap V3 the same question and gets back each pool's token order and decimals, which the module needs to turn a pool's state into dollars.
- **The device** combines the pools into one price, weighted by liquidity and leaving out any pool that strays from the rest, and prices the odds from how that price actually moves. More pools mean more trades, and more real moves to measure.

To play on it, run [`substreams/relay.py`](substreams/) and set `TICK_MARKET_SOURCE=substreams` in `firmware/.env`. The `sim` (default) and `coinbase` feeds are for playing without a relay.

## Quick start

```bash
cd firmware
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

See [`firmware/README.md`](firmware/README.md) for controls and Pi/KMSDRM notes.

**On the device:** the dial moves your box up and down the price ladder; a short click buys the next 20 seconds (+10 USDC), pressing again adds more to the same box. Distance from spot sets the payout, priced from measured live volatility. On desktop, hold Up/Down to emulate a spun dial and press Escape to quit. See the [actual gameplay sheet](design/box-run-live/gameplay-sheet.png).
