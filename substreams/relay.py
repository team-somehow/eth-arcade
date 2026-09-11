"""Serves stream.sh over HTTP, so a device can follow it without running Substreams.

GET /stream answers with newline-delimited JSON, one line per block per chain,
exactly as stream.sh prints it, for as long as the client stays connected. A
new client first gets the latest line that priced each pool, so it knows every
pool before that pool next trades.

Standard library only. The Substreams key stays on this machine.

    python3 relay.py [--host 0.0.0.0] [--port 8787]
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Client:
    def __init__(self):
        self.lines: queue.Queue[str] = queue.Queue(maxsize=1024)
        self.dropped = False


class Relay:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients: set[Client] = set()
        self.latest: dict[str, tuple[str, int, str]] = {}  # chain:pool -> chain, block, line

    def publish(self, line: str) -> None:
        try:
            message = json.loads(line)
            chain, block = str(message.get('chain', '')), int(message['@block'])
            prices = message['@data'].get('prices', [])
        except (ValueError, KeyError, TypeError, AttributeError):
            return
        with self.lock:
            for entry in prices:
                self.latest[f"{chain}:{entry.get('pool')}"] = (chain, block, line)
            for client in list(self.clients):
                try:
                    client.lines.put_nowait(line)
                except queue.Full:
                    # Too slow to keep up: cut it off rather than hand it a
                    # stream with holes in it. It reconnects and starts clean.
                    client.dropped = True
                    self.clients.discard(client)

    def subscribe(self) -> Client:
        client = Client()
        with self.lock:
            # In block order per chain, which is the order a reader expects.
            for line in sorted(set(self.latest.values())):
                client.lines.put_nowait(line[2])
            self.clients.add(client)
        return client

    def unsubscribe(self, client: Client) -> None:
        with self.lock:
            self.clients.discard(client)


class Pump:
    """Runs stream.sh and publishes every line it prints; restarts it if it stops."""

    def __init__(self, relay: Relay):
        self.relay = relay
        self.process: subprocess.Popen | None = None
        self.stopping = threading.Event()

    def run(self) -> None:
        while not self.stopping.is_set():
            # Its own process group, so stopping it reaches every stream under it.
            self.process = subprocess.Popen(['./stream.sh'], cwd=HERE, stdout=subprocess.PIPE,
                                            text=True, bufsize=1, start_new_session=True)
            for line in self.process.stdout:
                self.relay.publish(line.rstrip('\n'))
            self.process.wait()
            if not self.stopping.is_set():
                print(f'stream.sh exited ({self.process.returncode}); restarting in 5s',
                      file=sys.stderr)
                self.stopping.wait(5)

    def stop(self) -> None:
        self.stopping.set()
        if self.process is None:
            return
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
            self.process.wait(timeout=5)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)


def handler_for(relay: Relay):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/stream':
                self.send_error(404, 'Try /stream')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            client = relay.subscribe()
            self.log_message('client connected')
            try:
                while not client.dropped:
                    try:
                        line = client.lines.get(timeout=1)
                    except queue.Empty:
                        continue
                    self.wfile.write(line.encode() + b'\n')
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                relay.unsubscribe(client)
                self.log_message('client gone')

    return Handler


def lan_address() -> str:
    """This machine's address on the local network; nothing is sent."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(('10.255.255.255', 1))
            return probe.getsockname()[0]
        except OSError:
            return 'localhost'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args()

    relay = Relay()
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler_for(relay))
    server.daemon_threads = True
    pump = Pump(relay)
    # A plain `kill` should clean up as Ctrl+C does, streams included. SIGINT
    # is set explicitly because a shell starts background jobs ignoring it.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, signal.default_int_handler)
    threading.Thread(target=pump.run, name='stream', daemon=True).start()
    print(f'relay on http://{lan_address()}:{args.port}/stream', file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        pump.stop()


if __name__ == '__main__':
    main()
