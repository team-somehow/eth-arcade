"""`tick` -- start a game, watch the data, check the machine.

    tick doctor                 what is installed, configured and reachable
    tick new mygame             scaffold a game you can run immediately
    tick run mygame.py          start a game file
    tick prices --source coinbase --limit 20      print the feed
    tick pools                  print every pool in the on-chain stream
    tick record -o eth.ndjson --seconds 120       save a market
    tick replay eth.ndjson --speed 10             play one back
    tick board                  the leaderboard, read from ENS
    tick docs                   build the documentation site and open it

`prices` and `pools` exist because the first question anyone has is "is the
data actually arriving?", and the answer should not require writing a game.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import sys
import time

TEMPLATE = Path(__file__).parent / 'templates' / 'game.py'


def cmd_doctor(args) -> int:
    from . import __version__
    from .env import load_env_file
    load_env_file()
    print(f'tick-sdk {__version__}   python {sys.version.split()[0]}')
    for module, why in (('pygame', 'the screen and sound'),
                        ('eth_account', 'real funds and ENS'),
                        ('eth_abi', 'real funds and ENS'),
                        ('qrcode', 'the deposit QR code'),
                        ('gpiozero', 'the dial and buttons (Pi only)')):
        found = importlib.util.find_spec(module) is not None
        print(f'  [{"ok" if found else "--"}] {module:<14} {why}')
    print('settings')
    for key, default in (('TICK_MARKET_SOURCE', 'sim'), ('TICK_ASSET', 'eth'),
                         ('TICK_FUNDING', 'demo'), ('TICK_STAKE_USDC', '10'),
                         ('TICK_WINDOW_S', '(game)'), ('TICK_ROTATE', 'auto'),
                         ('SUBSTREAMS_BASE_URL', 'http://localhost:8787')):
        value = os.environ.get(key)
        print(f'  {key:<20} {value if value else default + "  (default)"}')
    source = os.environ.get('TICK_MARKET_SOURCE', 'sim')
    print(f'feed: {source}')
    try:
        from .feeds import open_feed
        feed = open_feed(source)
        deadline = time.monotonic() + 6
        last = time.monotonic()
        got = []
        while time.monotonic() < deadline and not got:
            now = time.monotonic()
            got = feed.poll(now - last, now)
            last = now
            time.sleep(0.05)
        feed.close()
        print(f'  {feed.status}')
        print(f'  {"got " + str(len(got)) + " ticks, last " + str(got[-1].price) if got else "no ticks in 6s"}')
    except Exception as exc:
        print(f'  feed failed: {exc}')
        return 1
    return 0


def cmd_new(args) -> int:
    name = args.name
    target = Path(args.into or '.') / (name if name.endswith('.py') else f'{name}.py')
    if target.exists() and not args.force:
        print(f'{target} exists; pass --force to overwrite')
        return 1
    title = Path(name).stem.replace('_', ' ').replace('-', ' ').upper()
    body = TEMPLATE.read_text().replace('GAME_TITLE', title)
    body = body.replace('ClassName', ''.join(w.capitalize() for w in Path(name).stem.replace('-', '_').split('_')))
    target.write_text(body)
    print(f'wrote {target}')
    print(f'run it:  python {target}')
    return 0


def load_game(path: str):
    """Import a file and return its single `Game` subclass, instantiated."""
    from .game import Game
    file = Path(path).resolve()
    if not file.exists():
        raise SystemExit(f'no such file: {file}')
    spec = importlib.util.spec_from_file_location(file.stem, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[file.stem] = module
    sys.path.insert(0, str(file.parent))
    spec.loader.exec_module(module)
    found = [value for value in vars(module).values()
             if isinstance(value, type) and issubclass(value, Game) and value is not Game]
    if not found:
        raise SystemExit(f'{file} defines no Game subclass')
    return found[-1]()


def cmd_run(args) -> int:
    from .runtime import run
    if args.source:
        os.environ['TICK_MARKET_SOURCE'] = args.source
    if args.stake:
        os.environ['TICK_STAKE_USDC'] = args.stake
    run(load_game(args.path), seed=args.seed)
    return 0


def cmd_prices(args) -> int:
    from .feeds import open_feed
    feed = open_feed(args.source, seed=args.seed, **({'path': args.file} if args.file else {}))
    print(f'{feed.name}: {feed.status}', file=sys.stderr)
    started = time.time()
    try:
        for tick in feed.stream(limit=args.limit):
            print(f'{time.time() - started:8.2f}s  {tick.price:>14,.4f}  '
                  f'seq {tick.sequence:>6}  age {tick.source_age:.2f}s', flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        feed.close()
    return 0


def cmd_pools(args) -> int:
    from .feeds import PoolStream
    stream = PoolStream(args.url)
    print(f'reading {stream.url}', file=sys.stderr)
    seen = 0
    try:
        for block in stream.blocks():
            seen += 1
            age = block.age(time.time())
            print(f'{block.chain:<10} block {block.number:<12} {age:5.1f}s old  '
                  f'{len(block.prices)} pools', flush=True)
            if args.verbose:
                for pool in block.prices:
                    print(f'    {pool.pool[:10]}  {pool.price:>12,.4f}  liq {pool.liquidity:.3e}')
            if args.limit and seen >= args.limit:
                return 0
    except KeyboardInterrupt:
        pass
    return 0


def cmd_record(args) -> int:
    from .feeds import Recorder, open_feed
    feed = Recorder(open_feed(args.source, seed=args.seed), args.out)
    print(f'recording {args.source} to {args.out} for {args.seconds}s', file=sys.stderr)
    deadline = time.monotonic() + args.seconds
    last = time.monotonic()
    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            feed.poll(now - last, now)
            last = now
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        feed.close()
    print(f'wrote {feed.count} ticks to {args.out}', file=sys.stderr)
    return 0


def cmd_replay(args) -> int:
    from .feeds import ReplayFeed
    feed = ReplayFeed(args.file, speed=args.speed)
    print(feed.status, file=sys.stderr)
    try:
        for tick in feed.stream():
            print(f'{tick.price:>14,.4f}  seq {tick.sequence}', flush=True)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_docs(args) -> int:
    """Build the documentation site and, unless told not to, serve it."""
    import subprocess
    builder = Path(__file__).resolve().parent.parent / 'web' / 'build.py'
    if not builder.exists():
        print(f'no docs builder at {builder} (installed without the web/ folder?)')
        return 1
    command = [sys.executable, str(builder)]
    if not args.build_only:
        command.append('--serve')
        command += ['--port', str(args.port)]
        if args.no_open:
            command.append('--no-open')
    return subprocess.call(command, cwd=str(builder.parent))


def cmd_board(args) -> int:
    from .identity import Standings
    rows = Standings().read()
    if not rows:
        print('no ranked players yet')
        return 0
    print(f'{"#":>2}  {"name":<28} {"pnl":>12} {"best":>10} {"wins":>5} {"plays":>5}')
    for rank, row in enumerate(rows, 1):
        print(f'{rank:>2}  {row.name:<28} {row.pnl:>12} {row.best:>10} '
              f'{row.wins:>5} {row.sessions:>5}')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='tick', description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest='command', required=True)

    subs.add_parser('doctor', help='what is installed and whether the feed answers'
                    ).set_defaults(func=cmd_doctor)

    new = subs.add_parser('new', help='scaffold a game')
    new.add_argument('name')
    new.add_argument('--into', default='.')
    new.add_argument('--force', action='store_true')
    new.set_defaults(func=cmd_new)

    run_ = subs.add_parser('run', help='run a game file')
    run_.add_argument('path')
    run_.add_argument('--source')
    run_.add_argument('--stake')
    run_.add_argument('--seed', type=int)
    run_.set_defaults(func=cmd_run)

    prices = subs.add_parser('prices', help='print ticks from a feed')
    prices.add_argument('--source', default=None)
    prices.add_argument('--limit', type=int, default=0)
    prices.add_argument('--seed', type=int)
    prices.add_argument('--file', help='recording, with --source replay')
    prices.set_defaults(func=cmd_prices)

    pools = subs.add_parser('pools', help='print the on-chain pool stream')
    pools.add_argument('--url', default=os.environ.get('SUBSTREAMS_BASE_URL',
                                                       'http://localhost:8787'))
    pools.add_argument('--limit', type=int, default=0)
    pools.add_argument('-v', '--verbose', action='store_true')
    pools.set_defaults(func=cmd_pools)

    record = subs.add_parser('record', help='save a market to a file')
    record.add_argument('-o', '--out', required=True)
    record.add_argument('--source', default='coinbase')
    record.add_argument('--seconds', type=float, default=120)
    record.add_argument('--seed', type=int)
    record.set_defaults(func=cmd_record)

    replay = subs.add_parser('replay', help='play a recording back')
    replay.add_argument('file')
    replay.add_argument('--speed', type=float, default=1.0)
    replay.set_defaults(func=cmd_replay)

    subs.add_parser('board', help='the leaderboard, read from ENS'
                    ).set_defaults(func=cmd_board)

    docs = subs.add_parser('docs', help='build and serve the documentation site')
    docs.add_argument('--port', type=int, default=8000)
    docs.add_argument('--build-only', action='store_true', help='write web/dist and stop')
    docs.add_argument('--no-open', action='store_true')
    docs.set_defaults(func=cmd_docs)

    args = parser.parse_args(argv)
    limit = getattr(args, 'limit', None)
    if limit == 0:
        args.limit = None
    return args.func(args) or 0


if __name__ == '__main__':
    raise SystemExit(main())
