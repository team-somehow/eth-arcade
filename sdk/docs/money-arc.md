# Real money, without asking anyone to trust the box

A game with paper money is a demo. The moment it holds real funds, four
questions appear, and they have to be answered in the design rather than in a
disclaimer:

1. How does money get **in**, from a wallet the device has never met?
2. How does a ten-second round settle **without a transaction per bet**?
3. How does a player get their money **out**, without trusting the device?
4. What stops the screen promising a payout that cannot be funded?

This page is how the SDK answers them, and how you point it at your own chain
or your own contract.

---

## The session model

```
  player's wallet ──(1) plain USDC send──▶ device address
                                             │
                                    (2) openFor(player, amount, device)
                                             ▼
                                        TickEscrow  ── holds the deposit, in the player's name,
                                             │         plus reserved house money for the win
                       (3) rounds run on the device, off-chain, for as long as they play
                                             │
                                    (4) close(sessionId, finalBalance)
                                             ▼
                                   payout ──────────▶ player's wallet
```

**One deposit in, one settlement out.** Everything between is the device's, and
that is deliberate: a ten-second round cannot wait for a block, and nobody will
approve forty transactions an hour. Sessions are what make an arcade cadence
possible on-chain at all.

---

## 1. Money in: a send, not a connect

The device shows **its own address as a QR code** (EIP-681, so scanning it
opens a send screen prefilled with the right chain). The player sends USDC from
their own wallet. No dApp, no WalletConnect, no signature prompt on a 480×320
screen, no app to install.

```python
funding.qr_text      # 'ethereum:0x11ab...@5042002'
```

The device watches the chain for transfers to itself, keeps a small fixed gas
fee, and locks the rest in escrow **in the sender's name**:

```python
sid, deposit, reserve, tx = chain.open_for(player=sender, amount=amount)
```

Two details that make this work in practice:

* **USDC is the gas token**, so the device never needs a second coin and a
  player never has to be told to "get some ETH first". The fee kept from each
  deposit (`TICK_GAS_FEE_USDC`, 0.01 by default) pays for the open and the
  close.
* Every USDC movement — a plain native send *and* an ERC-20 transfer — is
  logged as a `Transfer` from one system address. Watching that catches both
  kinds exactly once. Watching the token contract's own log would miss the
  plain send, which is exactly what a wallet's send screen produces.

Deposits the house cannot back are **sent straight home**, not held:

```python
if house.paused or amount > house.max_deposit or reserve > house.free:
    chain.transfer(sender, amount)        # refunded, with the reason recorded
```

## 2. Rounds run off-chain

Bets are placed, topped up and settled entirely on the device against
`wallet.balance`. The chain sees none of it, which is why a round can be ten
seconds long.

This is the honest trade: the device is trusted to run the rounds for the
length of a session, and the contract is trusted with the money. If you need
the rounds trusted too, the seam to use is a signed price attestation the
escrow checks at close — the settlement path already takes a signature (see
below), so that is an extension rather than a redesign.

## 3. Money out: the contract pays, not the device

```python
funding.cash_out(wallet)     # the worker closes each session at the final balance
```

`close(sessionId, finalBalance)` pays **the address the USDC came from**. The
device cannot redirect it, cannot skim it, and cannot keep it: the payout
target was fixed when the session opened.

Two safety valves in the contract matter to your game's UX:

* The device can either send `close` itself, or sign an EIP-712
  `Close(sessionId, finalBalance)` that anyone submits — so a device with no
  gas left can still settle.
* If a device never closes at all, the player can `reclaim` their deposit after
  a timeout fixed when the session opened. A bricked handheld is an
  inconvenience, not a loss.

## 4. The cap: never promise what cannot be paid

Opening a session reserves house money — `deposit × winCapBps`, 4x by default —
so a win is always payable. That ceiling is exposed all the way up to your
game:

```python
wallet.cap                 # deposit + reserve, or None with no session open
ctx.would_exceed_cap(...)  # would one more bet's best case go past it?
```

and `ctx.bet` refuses with `MAX WIN REACHED / CASH OUT` before taking the
stake. Without this check the screen quotes a 20x payout the contract will cap,
and the player finds out at settlement — which is the single worst moment to
discover it.

---

## Using it

```bash
pip install -e ".[chain]"

cat >> .env <<'EOF'
TICK_FUNDING=arc-testnet
TICK_STAKE_USDC=0.001          # real money: make the stakes small while you test
EOF

python mygame.py
```

Your game code does not change. `TICK_FUNDING` swaps the wallet's funding
backend; `ctx.wallet` behaves identically either way.

```python
# the only place a game usually cares:
if ctx.wallet.onchain:
    draw_qr(screen, ctx.wallet.funding.qr_text)
```

### State, restarts, and threads

* Every chain call runs on **one worker thread**. The game thread only drains a
  queue in `sync()`. A slow RPC can never cost a frame, and a dropped frame on
  a handheld is felt immediately.
* Open sessions, the balance and the last block read are saved atomically under
  `.tick/`. A restart resumes play and **finishes an interrupted cash-out**
  rather than stranding a session.
* The device key is created on first run in `.tick/device.json`, mode 0600, and
  never leaves. It is not the player's key and holds nothing but gas.

### Pointing it somewhere else

```python
# tick/chain.py
NETWORKS['my-chain'] = Network(
    name='MY CHAIN', chain_id=1234,
    rpc='https://rpc.example', explorer='https://explorer.example',
    usdc='0x...', escrow='0x...')
```

or, without touching code:

```bash
TICK_ARC_RPC=https://my-rpc TICK_ESCROW_ADDRESS=0xMyEscrow python mygame.py
```

The escrow interface the SDK needs is four calls — `openFor`, `close`,
`sessions`, and the house view (`freeHouse`, `winCapBps`, `maxSessionDeposit`,
`paused`) — so a different contract with the same shape drops in.

---

## Testing it without a chain

Every on-chain call sits behind `Chain`, so the whole money state machine is
testable offline with a fake:

```python
class FakeChain:
    def block(self): return self.head
    def incoming(self, first, last): ...
    def house(self): return House(free, cap_bps, most, paused)
    def open_for(self, player, amount): ...
    def close(self, sid, final): ...

funding = EscrowFunding('arc-testnet', chain=FakeChain(), start=False)
funding.step()
```

[`tests/test_escrow.py`](../tests/test_escrow.py) covers, in milliseconds and
with no network: a deposit opening a session in the sender's name, the same
transfer never being taken twice, dust below the gas fee, money the house
cannot back going home, cash-out paying the final balance, an interrupted
cash-out finishing after a restart, and a session closed while the device was
off being forgotten.

That is the argument for the seam. The path that touches real money is the one
you least want to test by hand on a testnet.
