# contracts — TickEscrow on Arc

`TickEscrow` is a USDC escrow for TICK play sessions, with the owner as the house. Bets run off-chain on the device; the chain holds both sides' money and settles each session in one transaction.

- **The house** is the owner's USDC, funded with `fund` (a small bankroll, $10–20 on mainnet). A player's loss stays with the house; a win is paid from it.
- **A session** is one player's USDC locked for one device. When play ends, the player is paid the device's final balance.
- **A device can open for its player.** `openFor(player, amount, device)` locks the caller's USDC in `player`'s name, and every payout or refund goes to `player`, never to the caller. This is how the device puts USDC a player sent it into escrow.
- **Opening a session reserves** `deposit × winCapBps` of house money (4x by default), so a win is always payable. Concurrent sessions each reserve their own share, and a session that does not fit reverts. A close above deposit + reserve is capped.
- **The house is locked while any session is open.** `withdraw` reverts until every session has closed, and even then it can only take house money, never a player's deposit. To drain the house, `setPaused(true)` stops new sessions; open ones still close.
- **The device closes** either by sending `close` itself, or by signing an EIP-712 `Close(sessionId, finalBalance)` that anyone submits with `closeWithSig` — so the device never needs gas. The owner cannot close a session.
- **If a device never closes**, the player can `reclaim` the deposit after `sessionTimeout` (1 day). The deadline is fixed when the session opens, so the owner cannot push it back.

```
player ── open(amount, device) ──────────────▶ TickEscrow ◀── fund / withdraw (no open sessions) ── owner
device ── signs Close(id, final) ─▶ anyone ── closeWithSig ─▶ TickEscrow ── payout ─▶ player
```

## Setup

```sh
curl -L https://foundry.paradigm.xyz | bash && foundryup
forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts@v5.4.0 --no-git
cp .env.example .env   # then set ARC_DEPLOYER_KEY
```

## Test

```sh
forge test
```

Unit tests run against a 6-decimal mock USDC: opening reserves house money and concurrent sessions cannot over-reserve it, pausing stops new sessions but not closes, losses go to the house, wins are paid from it and capped, the house cannot withdraw during a session or more than it holds, only the owner can fund, withdraw, pause or set limits, signatures bind the balance and cannot be replayed, reclaim waits for a timeout the owner cannot extend, and a fuzz test checks the contract always holds what it owes and no money is created or lost.

Several players at once: two players with their own devices settle independently (one wins, one loses, each paid exactly), one device cannot close another player's session or reuse a signature across sessions, a player cannot reclaim someone else's deposit, and one stuck session keeps the house locked until it is reclaimed.

[`TickEscrowInvariant.t.sol`](test/TickEscrowInvariant.t.sol) goes further: three players and the house make random opens, closes (direct and signed, including above the cap), reclaims, withdrawals, top-ups and drains (pause, end every session, withdraw, unpause) in random order, and after every call the contract must be solvent, its totals must match the open sessions, every payout must be exact, no USDC may be created or lost, the house must never have withdrawn while a session was open, and it must always have been able to withdraw once none were. Each run must also have had two players' sessions open at once and used every way out, so a run that skipped everything cannot pass.

## Deploy to Arc testnet

```sh
forge script script/Deploy.s.sol --rpc-url arc_testnet --broadcast
./smoke.sh <TickEscrow address>
```

`smoke.sh` runs one real session against Arc's USDC: it funds the house if needed (`SEED_USDC`), opens a session (`SESSION_USDC`) for a throwaway device key, has that key sign a final balance 50% up, and settles it with `closeWithSig`. While the session is open it simulates the owner withdrawing and expects `SessionsOpen`; after the close it expects the same withdraw to succeed. Each run writes a report to [`results/`](results/) with every transaction's status, gas and explorer link, the house's state afterwards, and a PASS/FAIL check that the player's balance moved by exactly the seed, deposit, payout and gas.

| Network | TickEscrow | Deploy tx |
|---|---|---|
| Arc testnet (5042002) | [`0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627`](https://testnet.arcscan.app/address/0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627) — source verified | [`0x2e59…3047`](https://testnet.arcscan.app/tx/0x2e59a2a3cf398edba3441cbc08ede7dd8980cd253c7c2f3d3c63a81293543047) |
| Arc mainnet | not deployed yet | |

Owner (the house) on testnet: [`0x7ee85B080701330bf53Be62B7E72fcDD034eCCac`](https://testnet.arcscan.app/address/0x7ee85B080701330bf53Be62B7E72fcDD034eCCac). After deploying, the owner funded the house with 10 USDC ([tx](https://testnet.arcscan.app/tx/0x49772362e0598d814a0d67561eccc3137ad328cbdf00e6cd638b1854a23bb646)) and set a 2.5 USDC maximum deposit, keeping the 4x win cap and 1-day timeout ([tx](https://testnet.arcscan.app/tx/0xe02d69013a1f51b7132557d2255b409f97c998d3a656cae1ff28b48fed72f870)), so four full-size sessions fit at once.

Earlier testnet deploys are retired and empty: [`0xC50d…1b3B`](https://testnet.arcscan.app/address/0xC50dC94A6b9AB85A5B541Da9DB5df83870A41b3B), the same contract without `openFor` (house withdrawn in [this tx](https://testnet.arcscan.app/tx/0xa68c72369dbf87ceb36bb185817131d409e8125dd97dd6b94e9e1f84117797f8)), and two ERC-4626 vaults where outside LPs would have funded the house for share tokens, [`0xbddd…1daC`](https://testnet.arcscan.app/address/0xbddd8233a65b6f329245dEaFc917543EF48e1daC) (`sHOUSE`) and [`0xb268…016c`](https://testnet.arcscan.app/address/0xb268Df5120649A296A2EBe5fb0F367f68c7C016c) (`tvUSDC`). With only the team funding the house, the share token had no job, so it was dropped.

### Device flow on testnet

What the game does with real funds (`TICK_FUNDING=arc-testnet` in [`firmware/`](../firmware/)), run end to end against this deploy ([report](results/arc-testnet-device-flow-20260911.md)):

| Step | What happened | Tx |
|---|---|---|
| Deposit | The player sends the device 0.05 USDC as a plain native send, as MetaMask's send screen does | [`0xfff4…79f9`](https://testnet.arcscan.app/tx/0xfff4ea8c3a983b718b0606f54061acb1ec1ca71bfa5926a1a58583d668d779f9) |
| Open | 8.4 s later the device has approved the escrow once and called `openFor`: session 1, 0.04 locked in the player's name after a 0.01 gas fee, 0.16 of house money reserved | [`0x24f3…c0ec`](https://testnet.arcscan.app/tx/0x24f3990c01acc45b0e23462b346b0c249d090bd77f5c6c47ddb82102d92cc0ec) |
| Close | The device closes at 0.045 (a 0.005 win) and the escrow pays it straight to the player | [`0x97c9…bfaf`](https://testnet.arcscan.app/tx/0x97c982d75198b90af0f29a7cc1e05a49e7283e06c28c851d5e8724078f04bfaf) |

The player's balance moved by exactly −0.05 + 0.045 − 0.0005 gas. The device kept the 0.01 fee and paid its own gas (0.007) out of it.

### First smoke session, on the previous deploy (`smoke.sh`)

One full session against Arc's real USDC ([report](results/arc-testnet-20260911T150436Z.md)). The device key ([`0x1EBa…5DA8`](https://testnet.arcscan.app/address/0x1EBaba2e05D833C654c0cb8595A2F09D18445DA8)) never held funds or sent a transaction; it only signed the close.

| Step | What happened | Tx |
|---|---|---|
| Approve | Player lets the contract pull USDC | [`0x70fa…0555`](https://testnet.arcscan.app/tx/0x70fa1cfc1105c177ba9d11c7ac6aac44bb02c44fa914d8f6249e9116129a0555) |
| Fund | Owner funds the house with 0.1 USDC | [`0xaa78…402e`](https://testnet.arcscan.app/tx/0xaa78326e715ecb60a44fef795f1883205d9d2c73d50ea2eaeb25ba4509c0402e) |
| Open | Session 1: 0.01 USDC locked, 0.04 of house money reserved; an owner withdraw now reverts with `SessionsOpen` | [`0xc41a…f850`](https://testnet.arcscan.app/tx/0xc41a184aeef8216d882a8e705bc0789eb5e0aef1efde77d8db255677434df850) |
| Close | Device signs a final balance of 0.015; the player submits it; 0.005 win paid from the house; an owner withdraw now succeeds | [`0x0ec3…13bd`](https://testnet.arcscan.app/tx/0x0ec3721c841ac54381864ea9d2b64c41c6001a38c9754a2cec6025fb802213bd) |

Afterwards the house held 0.095 USDC (0.1 seed − 0.005 win) with nothing reserved, and the four transactions cost 0.0085 USDC of gas together.

## Arc notes

- USDC's ERC-20 interface is at `0x3600000000000000000000000000000000000000` with **6 decimals**. It is the same balance as the 18-decimal native gas token; every amount in this contract uses the 6-decimal view.
- **Foundry cannot simulate Arc's USDC locally.** Each transfer calls an Arc-only precompile (`0x1800…0001`, `isBlocklisted`) that Foundry's EVM lacks, so fork tests and scripts that move USDC fail before broadcast. Unit tests use a mock, the deploy script makes no USDC calls, and `smoke.sh` checks the real token on-chain with `cast`.
- Transactions need `maxFeePerGas` of at least 20 gwei; the RPC's own estimate is above that.
