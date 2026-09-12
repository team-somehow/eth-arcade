# ETHarcade sponsor showcase — submission notes

This audit compares the repository implementation with the sponsor requirements supplied in the task. It does not certify eligibility or independently re-run funded transactions.

## What the landing page now shows

- Sponsor links in the hero, a sponsor overview, and named sections for The Graph, Circle / Arc, and ENSv2.
- An architecture diagram linking price discovery and streaming, the game/SDK, USDC settlement, and ENS records.
- Target bounty names, product value, source links, explorer links, and recorded evidence.
- A clear distinction between the simulated browser game and the integrated device flow.

## Evidence and accurate scope

### The Graph

Sources: `substreams/substreams.yaml`, `substreams/pools.py`, `substreams/README.md`, `sdk/tick/feeds/substreams.py`.

The manifest composes both Pinax v3 and v4 event modules. Pool discovery uses the Messari standardized DEX schema through The Graph gateway. The same compiled module runs on Arbitrum and Base with different configuration. The consumer filters outliers against a weighted median, then takes a liquidity-weighted average. v4 and Slipstream pool lists are manually configured, not discovered from Messari subgraphs.

The 12 pools / 41 changes per minute / 2-second longest still / $3.47 disagreement are a recorded observation in the README, not live counters or guarantees. A live provider-backed demonstration remains required for judging: show `pools.py --dry-run`, the Substreams manifest, the authenticated relay stream, and the device or SDK consuming it. Do not show API keys in the recording. No live provider run was performed during this landing-page update.

### Circle / Arc

Sources: `contracts/src/TickEscrow.sol`, `firmware/arc.py`, `sdk/tick/escrow.py`, `contracts/results/arc-testnet-device-flow-20260911.md`.

Current recorded device flow sends its own `openFor` and `close` transactions, with a USDC gas fee. Contract support for `closeWithSig` is a separate relayed-close capability. The device briefly receives funds before escrow; describing it as never holding funds or never needing gas would be incorrect.

The contract enforces reserves, a payout cap, fixed payout recipient, authorized device, blocked house withdrawals during open sessions, and a fixed timeout refund. The device remains trusted for the final game balance. Do not present round outcomes as verified by the contract.

Arc testnet is documented; mainnet is not deployed. The supplied bounty reserves $2,500 of its $3,500 total for the same project deploying to Arc Mainnet by September 30. This has not been satisfied by the current testnet deployment, and no mainnet deployment was attempted here. App Kits, Circle Wallets, CCTP, and Gateway are not claimed.

### ENSv2

Sources: `ens/scorekeeper.py`, `ens/README.md`, `firmware/names.py`, `sdk/tick/identity.py`.

There is one UserRegistry under tick.eth and one shared PermissionedResolver. Players do not each receive their own registry or resolver. ENSv2 Enhanced Access Control scopes scorekeeper grants to seven stats text keys and player grants to their own profile records. The team retains administrative rights. Names are issued without transfer rights and with configured season expiry.

The scorekeeper derives updates from Arc events; the leaderboard enumerates registry events and reads through the Universal Resolver. The scorekeeper is deterministic, not an AI agent, even though it has an agent-context text record. The deployed tick.eth namespace intentionally remains unchanged by the ETHarcade brand rename.

## Remaining submission assets / checks

1. Public repository access: anonymous retrieval of the supplied GitHub URL returned 404 during this task. Confirm that the repository and source links are public before judging. Visibility was not changed.
2. Video: user will provide later. Use a 2–4 minute integrated demonstration to cover The Graph's requested duration, ENS registration/permissions and changing stats, and Arc funding/settlement. Do not substitute the simulated browser demo for live sponsor evidence.
3. Circle presentation: still needs the requested video/presentation; the landing page now supplies an architecture diagram and integration documentation links.
4. Live provider demonstration: run the configured Graph provider pipeline and show current data in the integrated game; historical observations alone are not proof of a currently running feed.
5. Explorer verification: transaction IDs were matched to the repository's recorded run reports. The web fetch tool could not independently retrieve the explorer pages in this session.

The repository docs are the requested documentation destination. No video URL or hosted docs URL has been invented. Gameplay and SDK behavior were not modified for presentation.
