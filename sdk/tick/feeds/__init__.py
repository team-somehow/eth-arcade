"""Feeds: where the number comes from.

    open_feed('sim')          seeded random walk, no network        (default)
    open_feed('coinbase')     live public REST ticker, 5 Hz
    open_feed('substreams')   on-chain pools via substreams/relay.py
    open_feed('frozen')       a price that never moves              (for tests)
    open_feed('replay', path='eth.ndjson')   a recorded market

Pick one with the TICK_MARKET_SOURCE setting and every game in this SDK
changes feed without touching a line of game code. That is the whole point of
the seam: your game reads `ctx.market.price`, and never knows or cares.
"""
from __future__ import annotations

import os

from ..ticks import ASSETS, Asset, PriceTick, current_asset
from .base import BaseFeed, Feed
from .coinbase import CoinbaseFeed, parse_coinbase
from .replay import Recorder, ReplayFeed, read_recording
from .sim import FrozenFeed, SimulatedFeed
from .substreams import (Block, PoolBook, PoolPrice, PoolStream, SubstreamsFeed,
                         parse_block, weighted_median)

SOURCES = ('sim', 'coinbase', 'substreams', 'replay', 'frozen')

DEFAULT_RELAY = 'http://localhost:8787'


def open_feed(source: str | None = None, seed: int | None = None,
              asset: Asset | None = None, **kwargs) -> BaseFeed:
    """The feed named by `source`, or by TICK_MARKET_SOURCE, for TICK_ASSET."""
    source = (source or os.environ.get('TICK_MARKET_SOURCE', 'sim')).strip().lower()
    asset = asset or current_asset()
    if source == 'sim':
        return SimulatedFeed(seed, asset, **kwargs)
    if source == 'frozen':
        return FrozenFeed(kwargs.pop('price', asset.start), asset)
    if source == 'coinbase':
        return CoinbaseFeed(asset)
    if source == 'substreams':
        if asset.key != 'eth':
            raise ValueError('substreams prices ETH only; use sim or coinbase')
        url = kwargs.pop('base_url', None) or os.environ.get('SUBSTREAMS_BASE_URL', DEFAULT_RELAY)
        return SubstreamsFeed(url)
    if source == 'replay':
        path = kwargs.pop('path', None) or os.environ.get('TICK_REPLAY_FILE')
        if not path:
            raise ValueError('replay needs path= or TICK_REPLAY_FILE')
        return ReplayFeed(path, asset=asset, **kwargs)
    raise ValueError(f"TICK_MARKET_SOURCE must be one of {', '.join(SOURCES)}")


__all__ = [
    'ASSETS', 'Asset', 'PriceTick', 'current_asset',
    'BaseFeed', 'Feed', 'SOURCES', 'open_feed',
    'SimulatedFeed', 'FrozenFeed', 'CoinbaseFeed', 'parse_coinbase',
    'SubstreamsFeed', 'PoolStream', 'PoolBook', 'Block', 'PoolPrice',
    'parse_block', 'weighted_median',
    'ReplayFeed', 'Recorder', 'read_recording',
]
