# A price your game can settle on

Every bet in this SDK settles on one number at one moment. That number has to
be **live**, **hard to push**, and **honest about its own age** — otherwise the
fairest odds in the world are being applied to the wrong price.

This page is how the SDK gets such a number out of live chain data, and how you
point it at a different market, a different chain, or a different set of pools.

---

## Why an exchange ticker is not enough

`TICK_MARKET_SOURCE=coinbase` is fine while you build. It is one venue, behind
a REST cache, with an unknown number of hops between the trade and you. For a
game that pays out on the price at a bell, three problems matter:

1. **It goes quiet.** A quiet ticker looks exactly like a dead one.
2. **It is one book.** One venue's price at one instant is one venue's opinion.
3. **You cannot check it afterwards.** A player who thinks they were robbed has
   nothing to look at.

Reading swaps directly off-chain fixes all three: the data is public, it is
timestamped by the block, and a settled round can be traced to the exact
transaction that set the price.

---

## The shape of it

```
  chain blocks
       │
       ▼
  Substreams module  (tick_eth_price)     runs on The Graph's network
       │   per block, per pool: price, in-range liquidity, tx hash
       ▼
  substreams run --output jsonl   ×N chains
       │   JSON lines on stdout
       ▼
  relay.py           (your laptop or a small server)
       │   GET /stream  →  newline-delimited JSON over one long-lived connection
       ▼
  tick.feeds.SubstreamsFeed      →  PriceTick  →  your game
  tick.feeds.PoolStream          →  Block / PoolPrice (raw, per pool)
```

The relay exists for one reason: **the API key must not live on a handheld
somebody can pick up**. The device holds a plain HTTP connection and receives
blocks as they are produced; it authenticates to nothing and can be handed to a
stranger.

---

## The module

The Substreams module reads Uniswap v3 and v4 swaps and emits, for every block,
each watched pool's price and in-range liquidity.

Three properties of it are what make the SDK's rules work:

* **It emits on every block, traded or not.** That is what lets `Market`
  tell a *calm* market from a *dead* one — the distinction the whole "quiet
  market sells nothing" rule rests on. A feed that only speaks when something
  happens cannot make that distinction, and a game built on one will
  eventually sell a certainty at 2x.
* **Every message carries its own block time.** `SubstreamsFeed` turns that
  into `PriceTick.source_age`, so the chain's own delay counts against
  staleness. A relay that falls two seconds behind stops the betting; it does
  not quietly settle rounds on old blocks.
* **It keeps no state between blocks**, so it starts at the chain head with
  nothing to backfill — which is what makes a cold start take seconds rather
  than minutes.

It builds on Pinax's `uniswap_v3` and `uniswap_v4` packages rather than
decoding logs itself, so the same compiled module runs on any EVM chain those
packages support, with only the pool list changed. Pools that emit the same
swap event as Uniswap v3 — Aerodrome Slipstream, Sushiswap V3 — are priced with
no change at all.

---

## Where the pool list comes from

A pool's `sqrtPriceX96` is meaningless without its **token order and
decimals**. Get either wrong and the price is off by a factor of 10¹² and the
game happily settles on it.

Standardized DEX subgraphs hold both, for every pool, in one schema that is the
same across protocols and chains. That is what makes pool discovery a single
query sent unchanged to every subgraph you list:

```graphql
{
  protocols(first: 1) { name network }
  liquidityPools(first: 20, where: { inputTokens: ["<WETH>", "<USDC>"] }) {
    id
    name
    inputTokens { id symbol decimals }
    inputTokenBalances
    fees { feeType feePercentage }
  }
}
```

```sh
python3 pools.py --dry-run     # show what it would add
python3 pools.py               # add the pools it finds
```

Adding a whole protocol costs **one subgraph id** in `.env`, because the query
does not change. That is the practical argument for the standardized schema: a
bespoke subgraph per protocol would mean a bespoke query, a bespoke parser and
a bespoke bug per protocol.

Sensible filters, and why: keep pools with a fee of 0.05% or less holding at
least 25,000 USDC. Nobody arbitrages a pool back into line until it is a fee
off — about $7 on a 0.3% pool, which is wider than a whole box in most games,
so a high-fee pool is a slow, wrong price. Size is read from the USDC the pool
actually holds rather than from a subgraph's USD figure, which reports some of
the largest pools as $0.

---

## Many pools, one number

`PoolBook` combines them. The rule is **average weighted by in-range liquidity,
after discarding any pool more than 50 bps from the weighted median.**

Each half of that does a job:

| Approach | What it gets right | What it gets wrong |
|---|---|---|
| One pool | simple | one large trade at the bell moves your settlement price |
| Median of pools | very hard to push | pins to a single pool, usually the biggest, which can go a minute without a trade — the price stops moving |
| Plain average | moves on any trade anywhere | one broken or pushed pool drags the whole number |
| **Trim, then weight** | moves with real trading, in proportion | needs enough pools to have a median worth trimming against |

And a chain whose stream falls more than ten seconds behind stops counting at
all: its pools' last prices are no longer that chain's current prices.

```python
from tick.feeds import PoolBook
book = PoolBook()
book.apply(line, wall_now)      # one stream line
book.price(wall_now)            # the combined number, or None
book.live_pools(wall_now)       # what is actually counting right now
```

More pools is not decoration. The odds are priced from volatility measured over
the last minute, so **every pool added is one more venue whose trades give the
estimator something real to measure**. A stretch where no watched pool trades
reads as a calm market — correctly — and after fifteen seconds of it the game
stops selling.

---

## Running it

```bash
# 1. get a Substreams key and build the module (see substreams/)
substreams auth
cargo build --target wasm32-unknown-unknown --release

# 2. start the relay on a machine that can keep a connection open
python3 substreams/relay.py --port 8787
# relay on http://192.168.1.24:8787/stream

# 3. point the device at it
echo 'TICK_MARKET_SOURCE=substreams'            >> .env
echo 'SUBSTREAMS_BASE_URL=http://192.168.1.24:8787' >> .env

# 4. check it before you trust it
tick pools -v
```

`tick pools -v` prints every block, every pool, and how far each pool is from
the combined price in basis points. If that is quiet or noisy, fix it before
writing a line of game code.

---

## Using it in a game

Nothing changes in your game. That is the point of the seam:

```python
class MyGame(Game):
    def on_action(self, ctx, action):
        if action.name == 'A':
            ctx.bet(ctx.price - 1, ctx.price + 1)     # same code on every feed
```

```bash
tick run mygame.py --source sim           # develop
tick run mygame.py --source substreams    # demo
```

### Reading the pools yourself

If your game wants more than one number — a spread between chains, a per-venue
display, a "which pool moved" callout — take the raw stream:

```python
from tick import PoolStream

for block in PoolStream('http://localhost:8787').blocks():
    print(block.chain, block.number, block.age(time.time()))
    for pool in block.prices:
        print('   ', pool.pool[:10], pool.price, pool.liquidity)
```

`PoolStream` reconnects on its own and yields `Block` objects with validated
per-pool prices. See [`examples/pools.py`](../examples/pools.py).

---

## Checking a settled round afterwards

Each price the module emits carries the hash of the transaction behind it. That
means a round settled at 14:32:07 can be traced to the exact swap that set the
price — by the player, after the fact, with no trust in the device at all. If
you are going to take someone's money on a number, being able to show them the
trade is worth more than any amount of UI.

---

## Recording it

Live markets are a terrible thing to develop against: you cannot make the price
do what you need to see, and you cannot make it do it twice. Record once,
replay forever:

```bash
tick record -o eth.ndjson --source substreams --seconds 600
tick run mygame.py --source replay          # TICK_REPLAY_FILE=eth.ndjson
```

Replay reproduces the recorded `source_age` too, so the gap that voided a round
in the wild voids it again on your desk.
