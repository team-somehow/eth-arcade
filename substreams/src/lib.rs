//! Live per-block prices for a chosen set of Uniswap v3 pools.
//!
//! Built on Pinax's `uniswap_v3` package rather than decoding logs itself: its
//! `map_events` already turns every Uniswap v3 log on the chain into typed
//! events, and this module only picks out the pools it was asked about.
//!
//! It keeps no state between blocks, so it can start at the chain head at
//! once. A module with a store would first have to build that store from its
//! initial block, which on Arbitrum means hundreds of millions of blocks.
//!
//! It emits a message for every block, including blocks where nothing traded,
//! so a consumer can tell a quiet market from a dead stream. That takes the
//! raw block as an input: the engine skips a module whose inputs are all
//! empty, and most Arbitrum blocks carry no Uniswap v3 event at all, which
//! left the stream silent for seconds at a time. The block is decoded as an
//! empty message, so nothing in it is actually read.
// Generated for every message in the imported package, not only the ones used here.
#[allow(dead_code)]
mod pb;

use std::collections::BTreeMap;

use pb::tick::v1::{BlockPrices, Ignored, PoolPrice};
use pb::uniswap::v3::{log, Events};
use substreams::errors::Error;
use substreams::pb::substreams::Clock;
use substreams::Hex;

/// A pool to watch, and how to turn its raw price into a quoted one.
struct Pool {
    decimals0: i32,
    decimals1: i32,
    /// Quote token0 per token1 instead of token1 per token0.
    invert: bool,
}

impl Pool {
    /// Decimal-adjusted price from a Q64.96 square-root price.
    ///
    /// f64 parses the full uint160 string with correct rounding, and the
    /// relative error that leaves (around 1e-16) is far below a cent.
    fn price(&self, sqrt_price_x96: &str) -> Option<f64> {
        let root = sqrt_price_x96.parse::<f64>().ok()? / 2f64.powi(96);
        let raw = root * root * 10f64.powi(self.decimals0 - self.decimals1);
        let price = if self.invert { 1.0 / raw } else { raw };
        (price.is_finite() && price > 0.0).then_some(price)
    }
}

/// Parses `0xpool:decimals0:decimals1[:invert]`, comma-separated.
fn parse_pools(params: &str) -> Result<BTreeMap<String, Pool>, Error> {
    let mut pools = BTreeMap::new();
    for entry in params.split(',').map(str::trim).filter(|e| !e.is_empty()) {
        let fields: Vec<&str> = entry.split(':').collect();
        let (address, decimals0, decimals1, invert) = match fields.as_slice() {
            [a, d0, d1] => (*a, *d0, *d1, false),
            [a, d0, d1, "invert"] => (*a, *d0, *d1, true),
            _ => return Err(Error::msg(format!("bad pool entry {entry:?}: want 0xpool:decimals0:decimals1[:invert]"))),
        };
        let address = address.trim_start_matches("0x").to_lowercase();
        if address.len() != 40 || Hex::decode(&address).is_err() {
            return Err(Error::msg(format!("bad pool address in {entry:?}")));
        }
        let decimals = |d: &str| d.parse::<u8>().map(i32::from).map_err(|_| Error::msg(format!("bad decimals in {entry:?}")));
        pools.insert(address, Pool { decimals0: decimals(decimals0)?, decimals1: decimals(decimals1)?, invert });
    }
    if pools.is_empty() {
        return Err(Error::msg("no pools configured"));
    }
    Ok(pools)
}

#[substreams::handlers::map]
fn map_pool_prices(
    params: String,
    clock: Clock,
    _block: Ignored,
    events: Events,
) -> Result<BlockPrices, Error> {
    let pools = parse_pools(&params)?;
    // A BTreeMap, not a HashMap: output order must be the same on every run.
    let mut latest: BTreeMap<String, PoolPrice> = BTreeMap::new();
    for tx in events.transactions {
        for entry in tx.logs {
            let Some(log::Log::Swap(swap)) = entry.log else { continue };
            let address = Hex::encode(&entry.address);
            let Some(pool) = pools.get(&address) else { continue };
            let Some(price) = pool.price(&swap.sqrt_price_x96) else { continue };
            let quote = latest.entry(address.clone()).or_insert_with(|| PoolPrice {
                pool: format!("0x{address}"),
                ..Default::default()
            });
            // Logs arrive in block order, so each swap overwrites the last and
            // what remains is the pool's state once the block is done.
            quote.swaps += 1;
            quote.price = price;
            quote.sqrt_price_x96 = swap.sqrt_price_x96;
            quote.liquidity = swap.liquidity;
            quote.ordinal = entry.ordinal;
            quote.tx_hash = format!("0x{}", Hex::encode(&tx.hash));
        }
    }
    let timestamp_ms = clock
        .timestamp
        .map(|t| t.seconds as u64 * 1000 + t.nanos as u64 / 1_000_000)
        .unwrap_or_default();
    Ok(BlockPrices {
        block_number: clock.number,
        block_hash: clock.id,
        timestamp_ms,
        prices: latest.into_values().collect(),
    })
}
