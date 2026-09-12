"""Keeps the scorekeeper up alongside the game, so nobody has to remember to start it.

The scorekeeper (ens/scorekeeper.py) is what names players and writes their
stats; without it the leaderboard stays empty however well the money works. It
is one service, not one per device: it holds the TICK key that owns tick.eth
and the escrow, so two of them would race to register the same name. Hence the
guards here: both keys must already be on this machine, a python that can run
it must exist, and a lock file means only the first launcher starts one.
"""
from __future__ import annotations

import atexit
import fcntl
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SCOREKEEPER = ROOT / 'ens' / 'scorekeeper.py'
KEEPER_KEY = ROOT / 'ens' / '.tick' / 'scorekeeper.json'
LOCK = ROOT / 'ens' / '.tick' / 'scorekeeper.lock'
LOG = ROOT / 'ens' / '.tick' / 'scorekeeper.log'
VENV = ROOT / 'firmware' / '.venv' / 'bin' / 'python'


def interpreter() -> str | None:
    """A python that can run the scorekeeper: it needs eth-abi and eth-account.

    The display bootstrap re-execs into the system python on the Pi, which may
    or may not be the one the libraries were installed for, so ask before
    spawning something that would only fail out of sight in the log.
    """
    for python in (str(VENV), sys.executable):
        if python == str(VENV) and not VENV.exists():
            continue
        try:
            probe = subprocess.run([python, '-c', 'import eth_abi, eth_account'],
                                   capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return python
    return None


def wanted() -> bool:
    """Off for demo (paper) play, and off when TICK_SCOREKEEPER says so."""
    if os.environ.get('TICK_SCOREKEEPER', '1') in ('0', 'no', 'off'):
        return False
    return os.environ.get('TICK_FUNDING', 'demo') != 'demo'


def missing() -> str:
    """What this machine lacks to score, in words, or '' when it has everything.

    Both keys must already exist here. The scorekeeper key especially: a missing
    one is not an error downstream, it is a freshly invented account with no gas
    and none of the resolver roles, whose every write reverts in a retry loop.
    """
    from envfile import load_env_file
    load_env_file(ROOT / 'contracts' / '.env')
    key = os.environ.get('ARC_DEPLOYER_KEY', '')
    if not SCOREKEEPER.exists():
        return f'no {SCOREKEEPER}'
    if not (key.startswith('0x') and len(key) == 66):
        return 'no ARC_DEPLOYER_KEY in contracts/.env'
    if not KEEPER_KEY.exists():
        return f'no {KEEPER_KEY} (copy it from the machine that ran deploy)'
    return ''


def claim() -> object | None:
    """The lock, or None while a scorekeeper on this machine holds it.

    It is handed to the scorekeeper itself, not kept here: the lock then says
    "one is running", not "one was started", so a launcher that is killed
    without its atexit leaves no orphan that a later launch would double.
    """
    LOCK.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = LOCK.open('w')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:        # a scorekeeper on this machine is already running
        handle.close()
        return None
    return handle


def start() -> subprocess.Popen | None:
    """Start the scorekeeper beside the game. Never gets in the way of play."""
    if not wanted():
        return None
    lacking = missing()
    if lacking:
        print(f'no scorekeeper here: {lacking}', flush=True)    # the game plays on regardless
        return None
    handle = claim()
    if handle is None:
        return None
    python = interpreter()
    if python is None:
        print('no scorekeeper here: no python with eth-abi and eth-account', flush=True)
        handle.close()
        return None
    try:
        with LOG.open('a') as log:
            # The lock's fd goes with it and is released only when it exits.
            child = subprocess.Popen([python, '-u', str(SCOREKEEPER), 'run'],
                                     cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
                                     pass_fds=(handle.fileno(),))
    except OSError as exc:    # no scorekeeper is better than no game
        print(f'scorekeeper did not start: {exc}', flush=True)
        return None
    finally:
        handle.close()
    print(f'scorekeeper running (pid {child.pid}), logging to {LOG}', flush=True)
    atexit.register(stop, child)
    return child


def stop(child: subprocess.Popen) -> None:
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
