# Giving your players a name

A leaderboard of `0x7ee8…CCac` is a leaderboard nobody reads. A player cannot
recognise themselves on it, cannot point at it, and cannot show it to anyone.

The usual fix is an account system: a sign-up, a database, a server. For a
handheld you hand to a stranger at a table, that is three things too many — and
all three die the day you stop paying for them.

The SDK does it with ENS instead. Every wallet that plays gets a readable
subname, and that player's record lives in the name's own text records. The
leaderboard is then **derived, not stored**: read the registry, read each name,
sort.

---

## What a player gets

```
0x7ee85B080701330bf53Be62B7E72fcDD034eCCac
        ▼
amber-otter.tick.eth
        ├── addr                 0x7ee8…CCac        (points back at the wallet)
        ├── tick.sessions        7
        ├── tick.wins            4
        ├── tick.pnl             12.4
        ├── tick.best            8.1
        ├── tick.last_tx         0x97c9…bfaf
        ├── avatar               (theirs to set)
        └── description          (theirs to set)
```

The name is a real ENS name. It resolves in any ENS client, it outlives the
game, and the record belongs to the name rather than to your backend.

---

## The handle is derived from the address

This is the part worth stealing.

```python
from tick.identity import handle, name_of

handle('0x7ee85B08...')        # 'amber-otter'
name_of('0x7ee85B08...')       # 'amber-otter.tick.eth', or None
```

`handle()` hashes the wallet and indexes two word lists. It is deterministic,
so **the device can work out which name to look for without an index, an API,
or a lookup service** — it computes the candidate and asks the resolver whether
that name points back at this wallet:

```python
for attempt in range(4):
    name = f'{handle(address, attempt)}.{parent}'
    if addr_of(resolver, name).lower() == address.lower():
        return name          # trusted: the name points back
    if addr_of(resolver, name) == ZERO:
        return None          # unregistered, so no later attempt is this wallet's
```

Collisions fall through to `-2`, `-3`. And because a name is trusted **only**
when its `addr` record resolves back to the wallet, squatting a handle gains
nothing: the device simply moves to the next one.

That "points back" check is the whole trust model, and it is two lines.

---

## Who may write what

Two sets of records, split by who can write them:

| Records | Written by | Why |
|---|---|---|
| `tick.sessions`, `tick.wins`, `tick.pnl`, `tick.best`, `tick.last_tx` | the scorekeeper only | a player who can write their own score has no score |
| `avatar`, `description`, `url`, `com.twitter` | the player | it is their name |

Enforced by resolver roles, not by convention. The scorekeeper holds the key
with permission to write the `tick.*` keys; a player holds their name and can
write the profile keys.

**Everything in `tick.identity` is read-only.** Writing stats is a privileged,
single-instance job — one scorekeeper per deployment, not one per device, or
two of them race to register the same name — and deliberately does not live on
the handheld.

---

## Reading it back

One name's records, in **one call**:

```python
from tick.chain import Rpc
from tick.identity import ens, records_of

rpc = Rpc(ens().rpc)
records_of(rpc, 'amber-otter.tick.eth')
# {'tick.sessions': '7', 'tick.wins': '4', 'tick.pnl': '12.4', ...}
```

That goes through ENS's Universal Resolver with a `multicall`, so seven records
cost one round trip rather than seven. On a handheld drawing a leaderboard of a
dozen players, that is the difference between a board and a spinner.

The whole board:

```python
from tick.identity import Standings

for row in Standings().read():
    print(row.name, row.pnl, row.wins, row.sessions)
```

`Standings` finds registered names from the registry's own `LabelRegistered`
logs and remembers its block cursor, so a refresh asks only for blocks it has
not read.

```bash
tick board
```

## On a device, without stalling a frame

```python
from tick.identity import Leaderboard

class MyGame(Game):
    def setup(self, ctx):
        self.board = Leaderboard()

    def on_action(self, ctx, action):
        if action.name == 'B':
            self.board.showing = True
            self.board.want()          # starts the reader thread on first use

    def draw(self, ctx, screen):
        for row in self.board.rows or []:
            ...
        if self.board.rows is None:
            say(screen, self.board.error or 'READING ENS...', 240, 150, 16, MUTED)
```

Nothing is read until it is first wanted; it refreshes while the board is on
screen and sleeps while it is not; and when the RPC is unreachable it **keeps
the last rows and says so** rather than blanking a board that was fine a second
ago.

---

## Pointing it at your own name

Nothing in `tick.identity` is hardcoded to one parent:

```bash
TICK_ENS_PARENT=mygame.eth
TICK_ENS_RPC=https://ethereum-sepolia-rpc.publicnode.com
TICK_ENS_REGISTRY=0x...        # your parent's subname registry
TICK_ENS_RESOLVER=0x...        # the one resolver every subname uses
TICK_ENS_SINCE=11684278        # first block: where a leaderboard starts reading
```

or in code:

```python
from tick.identity import Ens, Standings
mine = Ens('mygame.eth', rpc, chain_id, registry, resolver, since)
Standings(net=mine).read()
```

You can change the stat keys too — `Standings(keys=('mygame.score', ...))` —
since `records_of` takes whatever list you give it.

---

## Why names live on their own chain

Names and records sit on a cheap public chain; the money settles wherever your
escrow is. They are deliberately independent:

* Identity is **public and permanent** and wants to be read by things that are
  not your game. Settlement is **fast and private to a session** and wants to
  be cheap.
* A leaderboard being briefly unreachable must never stop a player cashing out,
  and a settlement chain being busy must never stop a name resolving.

ENSIP-11 gives you the crossing point when you want one: an EVM chain's coin
type is `0x80000000 | chain_id`, so a name can carry an address record for the
chain the money is actually on.

```python
from tick.identity import coin_type
coin_type(5042002)      # the settlement chain's coin type for an addr record
```

---

## The one rule

**Never let the device write a score.** Read names on the device, write them
from one service that holds the key. The device is a thing you hand to
strangers; treat anything it can sign as public.
