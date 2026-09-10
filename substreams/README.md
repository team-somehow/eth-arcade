# tick_eth_price

A Substreams module that reads Uniswap v3 swaps and outputs a per-block price for a chosen set of pools, on any EVM chain. It is the ETH price source for BOX RUN, where each bet settles on the ETH price at the end of a ten-second window.

## Why several pools on two chains

A bet settles on one number, so that number has to move often, be hard to push, and reflect the market rather than one venue. One pool does none of that well.

- **It updates often.** Over two minutes on Arbitrum, the busiest WETH/USDC pool changed price in 4 of 12 ten-second windows. All four WETH/stable pools together changed in 10 of 12. On Base, the WETH/stable pools moved in 27 of 28 blocks.
- **It is hard to push.** A price taken from one pool can be moved by one large trade at the bell. Moving the median of many pools on two chains at the same moment costs far more.
- **It is a fairer price.** Pools disagree. At one moment on Base they were $3.47 apart, more than twice the height of a box in the game.

The price is only a reference; bets never trade in these pools. They can settle in USDC on any chain, and the price is read where ETH has the deepest liquidity.

## How it works

```
sf.ethereum.type.v2.Block ──▶ Pinax uniswap_v3:map_events ──┐
sf.substreams.v1.Clock ─────────────────────────────────────┼──▶ map_pool_prices ──▶ tick.v1.BlockPrices
sf.ethereum.type.v2.Block ──────────────────────────────────┘
```

- **It builds on Pinax's `uniswap_v3` package** instead of decoding logs itself. That package already turns every Uniswap v3 log into typed events; this module keeps only the swaps for the pools it was given and converts each pool's `sqrtPriceX96` into a decimal-adjusted price.
- **It keeps no state between blocks**, so it starts at the chain head straight away, with nothing to backfill.
- **It emits a message for every block**, including blocks where nothing traded, so a consumer can tell a quiet market from a dead stream. The raw block is an input for this reason only: the engine skips a module whose inputs are all empty, and many Arbitrum blocks carry no Uniswap v3 event.
- **Every message carries its block time**, so a price is placed against the bell rather than against when it arrived. In testing, messages arrived about a second after each block.
- **The same compiled module runs on Arbitrum and Base.** Only the pool list changes.

The module reports each pool's price and in-range liquidity. Combining them is left to the consumer; BOX RUN uses a liquidity-weighted median.

## Where the pool list comes from

Pool addresses, token order and decimals come from Messari's standardized Uniswap v3 subgraphs on The Graph. The schema is the same on every chain, so one query finds the WETH/stable pools on Arbitrum and on Base:

```graphql
{
  liquidityPools(where: { inputTokens_contains: ["<WETH>", "<USDC>"] }) {
    id
    name
    inputTokens { symbol decimals }
    inputTokenBalances
  }
}
```

Each output price includes the hash of the transaction behind it, so a settled window can be checked against the same subgraph afterwards.

## Output

One `BlockPrices` per block, listing only the pools that traded in it:

```json
{
  "blockNumber": "503790132",
  "timestampMs": "1789063794000",
  "prices": [{
    "pool": "0xc31e54c7a869b9fcbecc14363cf510d1c41fa443",
    "price": 2456.759457684401,
    "sqrtPriceX96": "3927000007035700886487060",
    "liquidity": "26649090794393043",
    "swaps": 1,
    "ordinal": "5773",
    "txHash": "0x39ed645a77cad585294f380650d60576137a6892c0598dcecfd5b0fcda04bc3c"
  }]
}
```

## Run

Get a key from [The Graph Market](https://thegraph.market) with `substreams auth`, or set `SUBSTREAMS_API_KEY`. Then:

```sh
cargo build --target wasm32-unknown-unknown --release

# Arbitrum, with the default pool list
substreams run ./substreams.yaml map_pool_prices -e arb-one.streamingfast.io:443 -s -1 -o jsonl

# Base: same module, different pools
substreams run ./substreams.yaml map_pool_prices -e base-mainnet.streamingfast.io:443 -s -1 -o jsonl \
  -p map_pool_prices=0xd0b53d9277642d899df5c87a3966a349a798f224:18:6
```

Pools are passed as `0xpool:decimals0:decimals1`, comma-separated. Add `:invert` to quote token0 per token1 instead of token1 per token0.

## Choosing chains

`stream.sh` reads `.env` (copy it from `.env.example`) and starts one stream for each chain in `TICK_CHAINS`. It merges them into a single JSON-lines stream and adds a `chain` field to every line.

```sh
TICK_CHAINS=base            # one chain
TICK_CHAINS=arbitrum,base   # both
```

To add a chain, set its endpoint and pools as `TICK_ENDPOINT_<CHAIN>` and `TICK_POOLS_<CHAIN>`.
