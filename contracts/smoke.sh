#!/usr/bin/env bash
# One real session on Arc testnet: fund the house if it is too small, open a
# session for a throwaway device key, have the device sign its final balance,
# and settle it with closeWithSig. Along the way it checks the house is locked
# while the session is open and free after it closes. Writes a report to results/.
#
# This is the end-to-end check against Arc's real USDC. Foundry cannot simulate
# it locally (every transfer calls an Arc-only precompile), and cast sends
# straight to the chain. Costs about a cent of gas.
#
#   ./smoke.sh <TickEscrow address>
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

BOOK=${1:?usage: ./smoke.sh <TickEscrow address>}
RPC=${ARC_RPC:-https://rpc.testnet.arc.io}
EXPLORER=${ARC_EXPLORER:-https://testnet.arcscan.app}
USDC=${USDC:-0x3600000000000000000000000000000000000000}
# Amounts in 6-decimal units. The seed stays in the house, withdrawable by the owner; only gas is spent.
SEED=${SEED_USDC:-100000}         # 0.1 USDC into the house, only if it is too small
DEPOSIT=${SESSION_USDC:-10000}    # 0.01 USDC into the session
FINAL=$((DEPOSIT * 3 / 2))        # the device ends 50% up: a win paid by the house

KEY=$ARC_DEPLOYER_KEY
ME=$(cast wallet address --private-key "$KEY")
# The device only signs, never sends, so its key needs no USDC. It is not saved.
DEVICE_KEY=0x$(openssl rand -hex 32)
DEVICE=$(cast wallet address --private-key "$DEVICE_KEY")

mkdir -p results
OUT=results/arc-testnet-$(date -u +%Y%m%dT%H%M%SZ).md
ERR=$(mktemp)
trap 'rm -f "$ERR"' EXIT
GAS_WEI=0   # native gas is USDC with 18 decimals

call() { cast call --rpc-url "$RPC" "$@" | cut -d' ' -f1; }
usdc() { python3 -c 'import sys; print(f"{int(sys.argv[1]) / 1e6:.6f}")' "$1"; }
gas() { python3 -c 'import sys; print(f"{int(sys.argv[1]) / 1e18:.6f}")' "$1"; }
addr() { echo "[\`$1\`]($EXPLORER/address/$1)"; }

# Simulates the owner withdrawing the whole house, without sending anything.
# Prints ok, SessionsOpen, or the unexpected error.
SESSIONS_OPEN=$(cast sig 'SessionsOpen()')
try_withdraw() {
  local out
  if out=$(cast call --rpc-url "$RPC" --from "$ME" "$BOOK" 'withdraw(uint256,address)' \
      "$(call "$BOOK" 'houseBalance()(uint256)')" "$ME" 2>&1); then
    echo ok
  elif grep -qi "${SESSIONS_OPEN#0x}" <<< "$out"; then
    echo SessionsOpen
  else
    echo "$out" | tr '\n|' '  '
  fi
}

# send <step> <what> <cast send args...>: one transaction, one row in the report.
send() {
  local step=$1 what=$2 receipt hash status wei
  shift 2
  if ! receipt=$(cast send --rpc-url "$RPC" --private-key "$KEY" --json "$@" 2>"$ERR"); then
    echo "| $step | $what | **failed** | | $(tr '\n|' '  ' < "$ERR") |" >> "$OUT"
    echo "$step failed:" >&2; cat "$ERR" >&2
    exit 1
  fi
  read -r hash status wei < <(python3 -c '
import json, sys
r = json.load(sys.stdin)
print(r["transactionHash"], int(r["status"], 16), int(r["gasUsed"], 16) * int(r["effectiveGasPrice"], 16))' <<< "$receipt")
  GAS_WEI=$((GAS_WEI + wei))
  if [ "$status" != 1 ]; then
    echo "| $step | $what | **reverted** | $(gas "$wei") | [\`${hash:0:6}…${hash: -4}\`]($EXPLORER/tx/$hash) |" >> "$OUT"
    echo "$step reverted: $EXPLORER/tx/$hash" >&2
    exit 1
  fi
  echo "| $step | $what | success | $(gas "$wei") | [\`${hash:0:6}…${hash: -4}\`]($EXPLORER/tx/$hash) |" >> "$OUT"
  echo "$step: success  $EXPLORER/tx/$hash"
}

BEFORE=$(call "$USDC" 'balanceOf(address)(uint256)' "$ME")
cat > "$OUT" <<EOF
# Smoke test: Arc testnet, $(date -u '+%Y-%m-%d %H:%M UTC')

One real TickEscrow session against Arc's USDC, run by \`smoke.sh\`.

- Contract: $(addr "$BOOK")
- Player and house owner: $(addr "$ME")
- Device: $(addr "$DEVICE"), a fresh key that only signs and never holds USDC

| Step | What | Status | Gas (USDC) | Tx |
|---|---|---|---|---|
EOF

send Approve "Player lets the contract pull up to $(usdc $((SEED + DEPOSIT))) USDC" \
  "$USDC" 'approve(address,uint256)' "$BOOK" $((SEED + DEPOSIT))

SEEDED=0
RESERVE=$((DEPOSIT * $(call "$BOOK" 'winCapBps()(uint256)') / 10000))
if [ "$(call "$BOOK" 'freeHouse()(uint256)')" -lt "$RESERVE" ]; then
  send Fund "Owner funds the house with $(usdc "$SEED") USDC" \
    "$BOOK" 'fund(uint256)' "$SEED"
  SEEDED=$SEED
fi

ID=$(call "$BOOK" 'nextSessionId()(uint256)')
send Open "Session $ID: $(usdc "$DEPOSIT") USDC locked, $(usdc "$RESERVE") of house money reserved" \
  "$BOOK" 'open(uint256,address)' "$DEPOSIT" "$DEVICE"
LOCKED=$(try_withdraw)

DIGEST=$(call "$BOOK" 'closeDigest(uint256,uint256)(bytes32)' "$ID" "$FINAL")
SIG=$(cast wallet sign --no-hash --private-key "$DEVICE_KEY" "$DIGEST")
send Close "Device signs a final balance of $(usdc "$FINAL"); the player submits it" \
  "$BOOK" 'closeWithSig(uint256,uint256,bytes)' "$ID" "$FINAL" "$SIG"
UNLOCKED=$(try_withdraw)

AFTER=$(call "$USDC" 'balanceOf(address)(uint256)' "$ME")
OPEN=$(cast call --rpc-url "$RPC" "$BOOK" \
  'sessions(uint256)(address,address,uint96,uint96,uint64,bool)' "$ID" | sed -n 6p)
HOUSE=$(call "$BOOK" 'houseBalance()(uint256)')
RESERVED=$(call "$BOOK" 'reserved()(uint256)')
PLAYER_FUNDS=$(call "$BOOK" 'playerFunds()(uint256)')
# The 6-decimal balance truncates the 18-decimal one, so allow 2 micro-USDC.
EXPECTED=$((BEFORE - SEEDED - DEPOSIT + FINAL - GAS_WEI / 1000000000000))
DIFF=$((AFTER - EXPECTED)); DIFF=${DIFF#-}
if [ "$OPEN" = false ] && [ "$DIFF" -le 2 ] && [ "$LOCKED" = SessionsOpen ] && [ "$UNLOCKED" = ok ]; then
  RESULT="**PASS**: session $ID is closed, the player's balance moved by exactly the seed, deposit, payout and gas, and the house could withdraw only once the session closed."
else
  RESULT="**FAIL**: session open = $OPEN; expected the player at $(usdc "$EXPECTED") USDC, found $(usdc "$AFTER"); house withdraw while open = $LOCKED, after close = $UNLOCKED."
fi

cat >> "$OUT" <<EOF

## After

| | |
|---|---|
| Player USDC | $(usdc "$BEFORE") → $(usdc "$AFTER") |
| Win paid from the house | $(usdc $((FINAL - DEPOSIT))) USDC |
| Session $ID open | $OPEN |
| House withdraw while the session was open | $LOCKED |
| House withdraw after it closed | $UNLOCKED |
| House balance | $(usdc "$HOUSE") USDC |
| Reserved / player funds | $(usdc "$RESERVED") / $(usdc "$PLAYER_FUNDS") USDC |
| Total gas | $(gas "$GAS_WEI") USDC |

$RESULT
EOF

echo "report: $OUT"
case $RESULT in "**PASS**"*) echo PASS ;; *) echo FAIL; exit 1 ;; esac
