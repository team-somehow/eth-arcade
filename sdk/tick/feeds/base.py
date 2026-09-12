"""What every feed is, and the two ways to read one.

A feed is a source of `PriceTick`. It has exactly three methods:

    poll(dt, now) -> list[PriceTick]     non-blocking; returns what has arrived
    close()                              stop threads, drop sockets
    .name / .status                      words for the screen

`poll` is non-blocking on purpose. A game runs a frame loop at 30 FPS; a feed
that blocks waiting for the next block drops frames, and a dropped frame on a
handheld is felt immediately. Live feeds therefore do their waiting on a worker
thread and hand finished ticks over a queue.

For anything that is not a game -- a script, a bot, a terminal ticker -- the
blocking generator `stream()` is there instead, so you never write a poll loop
by hand just to print prices.
"""
from __future__ import annotations

import time
from typing import Iterator, Protocol, runtime_checkable

from ..ticks import Asset, PriceTick


@runtime_checkable
class Feed(Protocol):
    name: str
    status: str
    asset: Asset

    def poll(self, dt: float, now: float) -> list[PriceTick]: ...
    def close(self) -> None: ...


class BaseFeed:
    """Shared plumbing. Subclasses implement `poll` and `close`."""

    name = 'FEED'
    status = ''
    asset: Asset

    def poll(self, dt: float, now: float) -> list[PriceTick]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    # ---- reading a feed without a game loop ------------------------------
    def stream(self, interval: float = 0.05, limit: int | None = None) -> Iterator[PriceTick]:
        """Blocking generator of ticks. For scripts, bots and terminal tickers.

        `interval` is how long to sleep when nothing has arrived, not the tick
        rate: a block or a trade is handed over the moment it lands.
        """
        sent = 0
        last = time.monotonic()
        try:
            while limit is None or sent < limit:
                now = time.monotonic()
                dt, last = now - last, now
                got = self.poll(dt, now)
                if not got:
                    # A finite feed (a replay) ends the generator rather than
                    # sleeping forever on a file that has run out.
                    if getattr(self, 'done', False):
                        return
                    time.sleep(interval)
                    continue
                for tick in got:
                    yield tick
                    sent += 1
                    if limit is not None and sent >= limit:
                        return
        finally:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
