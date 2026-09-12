"""Record a market once, replay it forever.

Live markets are terrible to develop against: you cannot make the price do the
thing you need to see, and you cannot make it do it twice. So record a real
feed to a file, then replay it -- at wall speed to watch your game, or as fast
as the CPU allows to run a thousand rounds in a test.

    tick record --source coinbase --seconds 300 -o eth.ndjson
    tick replay eth.ndjson --speed 4

Recording format is one JSON object per line: {"t": 0.0, "p": 2500.12,
"a": 0.4}. `t` is seconds since the recording began, so a file is portable and
readable, and `a` is the source age the tick carried, so replay reproduces
staleness -- including the gap that voided a window.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..ticks import ASSETS, Asset, PriceTick
from .base import BaseFeed


class Recorder:
    """Wraps any feed and writes every tick it yields to a file.

        with Recorder(open_feed('coinbase'), 'eth.ndjson') as feed:
            for tick in feed.stream(limit=1000):
                ...
    """

    def __init__(self, feed, path: str | Path) -> None:
        self.feed = feed
        self.path = Path(path)
        self.handle = self.path.open('w')
        self.first: float | None = None
        self.count = 0
        self.name = getattr(feed, 'name', 'FEED')
        self.asset = getattr(feed, 'asset', ASSETS['eth'])

    @property
    def status(self) -> str:
        return f'{getattr(self.feed, "status", "")} / recording {self.count}'

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        ticks = self.feed.poll(dt, now)
        for tick in ticks:
            if self.first is None:
                self.first = tick.received_at
            self.handle.write(json.dumps({
                't': round(tick.received_at - self.first, 6),
                'p': tick.price,
                'a': round(tick.source_age, 4),
            }) + '\n')
            self.count += 1
        if ticks:
            self.handle.flush()
        return ticks

    def close(self) -> None:
        self.feed.close()
        self.handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


def read_recording(path: str | Path) -> list[tuple[float, float, float]]:
    """(offset seconds, price, source age) for every line in a recording."""
    out: list[tuple[float, float, float]] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        out.append((float(row['t']), float(row['p']), float(row.get('a', 0.0))))
    return out


class ReplayFeed(BaseFeed):
    """A recording, played back on the game clock.

    `speed` multiplies time: 1.0 is how it happened, 10.0 runs ten minutes of
    market in one. `loop` starts over at the end instead of going silent, which
    is what you want for an attract screen or a long soak test.
    """

    name = 'REPLAY'

    def __init__(self, path: str | Path | None = None,
                 rows: Iterable[tuple[float, float, float]] | None = None,
                 speed: float = 1.0, loop: bool = False,
                 asset: Asset = ASSETS['eth']) -> None:
        if rows is None:
            if path is None:
                raise ValueError('ReplayFeed needs a path or rows')
            rows = read_recording(path)
        self.rows = list(rows)
        if not self.rows:
            raise ValueError('Recording is empty')
        self.asset = asset
        self.speed = max(0.001, speed)
        self.loop = loop
        self.index = 0
        self.elapsed = 0.0
        self.sequence = 0
        self.laps = 0
        self.span = self.rows[-1][0]
        self.status = f'Replay / {len(self.rows)} ticks / {self.span:.0f}s'
        self.done = False

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        if self.done:
            return []
        self.elapsed += max(0.0, dt) * self.speed
        out: list[PriceTick] = []
        while self.index < len(self.rows) and self.rows[self.index][0] <= self.elapsed:
            offset, price, age = self.rows[self.index]
            self.index += 1
            self.sequence += 1
            # Stamp arrival at `now`: a replayed tick is fresh news to the game,
            # and only the recorded source age counts against it.
            out.append(PriceTick(price, self.sequence, now, age / self.speed))
        if self.index >= len(self.rows):
            if self.loop:
                self.index, self.elapsed, self.laps = 0, 0.0, self.laps + 1
            else:
                self.done = True
                self.status = 'Replay finished'
        return out

    def close(self) -> None:
        pass
