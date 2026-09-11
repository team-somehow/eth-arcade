#!/usr/bin/env bash
# Streams tick_eth_price on the chains listed in .env: one `substreams run`
# per chain, merged into a single JSON-lines stream on stdout. Each line gains
# a "chain" field so a consumer can tell the sources apart.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] || { echo "no .env here: copy .env.example to .env" >&2; exit 1; }
set -a; . ./.env; set +a

# The CLI picks up .substreams.env from the working directory on its own. If
# there is none here, reuse the firmware's, so one `substreams auth` is enough.
if [ ! -f .substreams.env ] && [ -z "${SUBSTREAMS_API_TOKEN:-}${SUBSTREAMS_API_KEY:-}" ] \
   && [ -f ../firmware/.substreams.env ]; then
  set -a; . ../firmware/.substreams.env; set +a
fi

# Stop every chain's stream together, however this script ends. Each stream
# runs in a subshell, so `substreams run` is a grandchild of this script and
# killing the children alone would orphan it. Only this script's own tree is
# touched: `kill 0` would also hit whatever launched it.
stop_streams() {
  trap - INT TERM EXIT
  for child in $(pgrep -P $$); do
    pkill -TERM -P "$child" 2>/dev/null || true
    kill -TERM "$child" 2>/dev/null || true
  done
}
trap stop_streams INT TERM EXIT

IFS=',' read -ra chains <<< "${TICK_CHAINS:?set TICK_CHAINS in .env}"
for chain in "${chains[@]}"; do
  name=$(echo "$chain" | tr -d ' ' | tr '[:upper:]' '[:lower:]')
  key=$(echo "$name" | tr '[:lower:]' '[:upper:]')
  endpoint_var="TICK_ENDPOINT_$key"
  pools_var="TICK_POOLS_$key"
  endpoint=${!endpoint_var:-}
  [ -n "$endpoint" ] || { echo "unknown chain '$name': set $endpoint_var in .env" >&2; exit 1; }
  pools=$(echo "${!pools_var:-}" | tr -d ' ')
  [ -n "$pools" ] || { echo "no pools for '$name': set $pools_var in .env" >&2; exit 1; }

  substreams run ./substreams.yaml map_pool_prices -e "$endpoint" -s -1 -o jsonl \
      -p "map_pool_prices=$pools" \
    | awk -v c="$name" '{ sub(/^\{/, "{\"chain\":\"" c "\","); print; fflush() }' &
done
wait
