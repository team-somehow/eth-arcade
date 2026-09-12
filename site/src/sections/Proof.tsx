import type { ReactNode } from 'react';

const REPO = 'https://github.com/Jovian-Dsouza/ethonline-2026';
const ARC = 'https://testnet.arcscan.app';
const SEPOLIA = 'https://sepolia.etherscan.io';
const ESCROW = '0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627';
const REGISTRY = '0xD25ACD4eB42A40D8145E3A7F1feFB17D09649cAa';
const RESOLVER = '0xDBe98b10176aBf0BD2DFEE86fD3ee59A7630FAa8';
const CLOSE_TX = '0x97c982d75198b90af0f29a7cc1e05a49e7283e06c28c851d5e8724078f04bfaf';
const STATS_TX = '0x5e93cabcc92da633c1bf9ebbf82bef0265359b0745fe594fa23327d3a7b86ceb';
const code = (path: string) => `${REPO}/blob/main/${path}`;

function Link({ href, children }: { href: string; children: ReactNode }) {
  return <a className="proof-link" href={href} target="_blank" rel="noopener noreferrer">{children}<span aria-hidden>↗</span></a>;
}

export function SponsorStrip() {
  return (
    <nav className="sponsor-strip" aria-label="Explore sponsor integrations">
      <div className="strip-heading"><span>BUILT AT ETHONLINE 2026</span><b>Three integrations.<br />One playable system.</b></div>
      <a href="#graph"><b>The Graph <span aria-hidden>↗</span></b><span>The price behind every round</span></a>
      <a href="#circle"><b>Circle / Arc <span aria-hidden>↗</span></b><span>The USDC behind every session</span></a>
      <a href="#ens"><b>ENSv2 <span aria-hidden>↗</span></b><span>The identity behind every score</span></a>
    </nav>
  );
}

export function Proof() {
  return (
    <section className="doc" id="proof" aria-labelledby="proof-title">
      <div className="head">
        <div className="eyebrow">03 / THE INTEGRATIONS THAT MAKE IT WORK</div>
        <h2 id="proof-title">Real infrastructure.<br />A little more play.</h2>
        <p className="lead">The Graph supplies the market. Circle’s Arc settles USDC sessions.
          ENSv2 makes the player record portable. Box Run brings them together on ETH Arcade;
          the SDK exposes the same building blocks for the next game.</p>
      </div>

      <figure className="system-map" aria-labelledby="architecture-title">
        <figcaption id="architecture-title"><span>THE SYSTEM / ARCHITECTURE</span><b>From market data to a player’s record.</b></figcaption>
        <ol>
          <li><span className="map-number">01 / THE GRAPH</span><b>Live pool prices</b><p>Standardized subgraphs → composed Substreams → HTTP relay</p><span className="map-arrow" aria-hidden>→</span></li>
          <li><span className="map-number">02 / ETH ARCADE</span><b>Box Run + SDK</b><p>Price aggregation, odds, inputs, sound, and off-chain rounds</p><span className="map-arrow" aria-hidden>→</span></li>
          <li><span className="map-number">03 / CIRCLE · ARC</span><b>USDC settlement</b><p>Wallet → device → escrow → payout to the player</p><span className="map-arrow" aria-hidden>→</span></li>
          <li><span className="map-number">04 / ENSv2</span><b>Identity + standings</b><p>Arc events → scorekeeper → ENS records → leaderboard</p></li>
        </ol>
        <p className="map-note">The device and scorekeeper run the integrated flow. The browser demo above uses simulated prices and paper USDC; it does not send transactions.</p>
      </figure>

      <article className="sponsor-story graph-story" id="graph" aria-labelledby="graph-title">
        <header className="sponsor-heading"><span className="sponsor-name">The Graph<span className="sponsor-role">MARKET DATA</span></span><span className="network-pill">Arbitrum + Base data</span></header>
        <div className="sponsor-layout">
          <div>
            <p className="bounty">TARGET TRACK / Best Use of Composable or Standardized Graph Products</p>
            <h3 id="graph-title">One query pattern.<br />One pipeline. More markets.</h3>
            <p className="sponsor-lead">A ten-second game needs a price that keeps moving. ETH Arcade combines multiple pools across two chains, instead of letting one quiet pool dictate the round.</p>
            <div className="integration-points">
              <div><b>Discover once, reuse across protocols.</b><p>The same Messari standardized DEX query retrieves pool metadata for Uniswap v3 and Sushiswap v3. Token order and decimals arrive in a shared schema, so a supported protocol needs configuration rather than another parser.</p></div>
              <div><b>Compose the event decoding.</b><p><code>tick_eth_price</code> imports Pinax’s <code>uniswap_v3</code> and <code>uniswap_v4</code> Substreams packages. The same compiled module runs on Arbitrum and Base with different pool lists.</p></div>
              <div><b>Put the result into gameplay.</b><p>The relay streams block-timestamped pool prices to the SDK. Its consumer rejects outliers more than 0.5% from the weighted median, then calculates a liquidity-weighted price used by the market and round engine.</p></div>
            </div>
          </div>
          <aside className="sponsor-evidence">
            <span className="evidence-label">RECORDED PIPELINE OBSERVATION</span>
            <div className="proof-metric"><b>12</b><span>pools across 2 chains</span></div>
            <dl className="evidence-stats"><div><dt>Price changes / minute</dt><dd>41</dd></div><div><dt>Longest unchanged interval</dt><dd>2s</dd></div><div><dt>Single-pool disagreement</dt><dd>$3.47</dd></div></dl>
            <p className="evidence-caption">A one-minute observation recorded in the integration README, not a live counter or a guaranteed rate.</p>
            <Link href={code('substreams/README.md')}>Pipeline, providers & observations</Link>
            <Link href={code('substreams/substreams.yaml')}>Inspect both package imports</Link>
            <Link href={code('substreams/pools.py')}>Inspect the standardized query</Link>
            <Link href={code('sdk/tick/feeds/substreams.py')}>Follow the price into the SDK</Link>
          </aside>
        </div>
        <details className="implementation-detail"><summary>Provider path and scope</summary><p>Pool discovery calls The Graph gateway with a Graph API key. Substreams runs against StreamingFast endpoints with a Substreams key, and the relay keeps those credentials off the device. The v4 and Slipstream pools are configured manually; the standardized discovery claim applies to the supported Messari subgraphs. The module emits pool prices; aggregation happens in the consumer. This reduces dependence on a single venue, but is not a claim of manipulation-proof pricing.</p></details>
      </article>

      <article className="sponsor-story circle-story" id="circle" aria-labelledby="circle-title">
        <header className="sponsor-heading"><span className="sponsor-name">Circle / Arc<span className="sponsor-role">PROGRAMMABLE USDC</span></span><span className="network-pill">Arc testnet · 5042002</span></header>
        <div className="sponsor-layout">
          <div>
            <p className="bounty">TARGET TRACK / Best DeFi/Onchain Finance Application</p>
            <h3 id="circle-title">Play many rounds.<br />Settle one session.</h3>
            <p className="sponsor-lead">USDC is the stake, the payout, and the gas token on Arc. A player can fund the handheld without acquiring a second token, while fast rounds stay off-chain.</p>
            <div className="integration-points">
              <div><b>Fund → reserve → play → pay out.</b><p>The device receives USDC, retains a configured gas fee, and calls <code>openFor</code> to lock the rest in the player’s name. The contract also reserves house funds to cover the session’s maximum permitted win.</p></div>
              <div><b>Enforce the money rules on-chain.</b><p>Only the designated device can close the session, directly or with an EIP-712 signature. Payouts go to the player address stored at opening. House withdrawals are blocked while any session remains open.</p></div>
              <div><b>Give a stalled session a way out.</b><p>The player can reclaim their deposit after the fixed one-day timeout. The owner cannot extend an already-open session’s deadline.</p></div>
            </div>
          </div>
          <aside className="sponsor-evidence">
            <span className="evidence-label">RECORDED DEVICE FLOW / ARC TESTNET</span>
            <div className="proof-metric"><b>USDC</b><span>one asset from funding to payout</span></div>
            <dl className="evidence-stats"><div><dt>Player sent</dt><dd>0.050</dd></div><div><dt>Gas fee retained</dt><dd>0.010</dd></div><div><dt>Deposit locked</dt><dd>0.040</dd></div><div><dt>House reserve</dt><dd>0.160</dd></div><div><dt>Paid to player</dt><dd>0.045</dd></div></dl>
            <Link href={`${ARC}/address/${ESCROW}`}>Inspect the escrow contract</Link>
            <Link href={`${ARC}/tx/${CLOSE_TX}`}>Inspect the session payout</Link>
            <Link href={code('contracts/results/arc-testnet-device-flow-20260911.md')}>Read the end-to-end run report</Link>
            <Link href={code('contracts/src/TickEscrow.sol')}>Read the settlement rules</Link>
          </aside>
        </div>
        <details className="implementation-detail"><summary>Deployment and trust model</summary><p>Current deployment: Arc testnet. Mainnet deployment has not been completed. The recorded device flow sends its own transactions and pays gas in USDC. The contract additionally supports a relayer submitting <code>closeWithSig</code>; that capability does not make the current device flow gasless. The designated device is trusted to report the final game balance; the escrow enforces authorization, the payout cap, recipient, reserves, and refunds, rather than verifying each round. This integration uses Arc and USDC; it does not claim App Kits, Circle Wallets, CCTP, or Gateway.</p></details>
      </article>

      <article className="sponsor-story ens-story" id="ens" aria-labelledby="ens-title">
        <header className="sponsor-heading"><span className="sponsor-name">ENSv2<span className="sponsor-role">PLAYER IDENTITY</span></span><span className="network-pill">ENSv2 beta · Sepolia</span></header>
        <div className="sponsor-layout">
          <div>
            <p className="bounty">TARGET TRACK / Best Use of ENSv2</p>
            <h3 id="ens-title">Your name carries<br />your score.</h3>
            <p className="sponsor-lead">ENS is the source of the leaderboard. The device enumerates registered player names and resolves their stats, so standings can be read without a separate leaderboard database.</p>
            <div className="integration-points">
              <div><b>A registry built for players.</b><p>A <code>UserRegistry</code> under <code>tick.eth</code> issues wallet-owned subnames. Names are registered without transfer rights and expire at the configured season end. A shared <code>PermissionedResolver</code> holds their records.</p></div>
              <div><b>Permissions are part of the game rules.</b><p>ENSv2 Enhanced Access Control grants the scorekeeper access to seven named stats keys. Each player receives permission to edit their own profile keys. Players cannot edit their score; the scorekeeper’s grants do not let it edit profiles.</p></div>
              <div><b>A settled session becomes a public record.</b><p>The scorekeeper watches Arc escrow events and updates ENS text records. The device’s LEADERS screen reads names and scores through the Universal Resolver, including a link back to each player’s last Arc close.</p></div>
            </div>
          </div>
          <aside className="sponsor-evidence">
            <span className="evidence-label">ENHANCED ACCESS CONTROL</span>
            <div className="permission-grid" role="table" aria-label="ENS record permissions">
              <div role="row"><b role="columnheader">Role</b><b role="columnheader">Stats</b><b role="columnheader">Profile</b></div>
              <div role="row"><span role="rowheader">Player</span><span role="cell">Read</span><span role="cell">Own only</span></div>
              <div role="row"><span role="rowheader">Scorekeeper</span><span role="cell">Write</span><span role="cell">Read</span></div>
              <div role="row"><span role="rowheader">Team admin</span><span role="cell">Admin</span><span role="cell">Admin</span></div>
            </div>
            <p className="evidence-caption">One shared resolver, permissions scoped by text key and name. The team retains administrative authority.</p>
            <Link href={`${SEPOLIA}/address/${REGISTRY}`}>Inspect the player registry</Link>
            <Link href={`${SEPOLIA}/address/${RESOLVER}`}>Inspect the shared resolver</Link>
            <Link href={code('ens/scorekeeper.py')}>Inspect grants & event-driven writes</Link>
            <Link href={code('firmware/names.py')}>Inspect leaderboard resolution</Link>
            <Link href={code('ens/README.md')}>Read the ENSv2 integration</Link>
          </aside>
        </div>
        <details className="implementation-detail"><summary>Why the ENSv2 features matter</summary><p>The hierarchical registry makes player issuance and season expiry programmable. Enhanced Access Control separates trusted score updates from player-controlled profile records on the shared resolver. Both contracts were created through ENS’s VerifiableFactory. The scorekeeper has its own <code>scorekeeper.tick.eth</code> name and an <code>agent-context</code> record, but is a deterministic service, not an AI agent. <code>tick.eth</code> remains the deployed namespace after the ETH Arcade product rename.</p></details>
      </article>

      <figure className="session-proof">
        <figcaption><div className="eyebrow">A RECORDED CROSS-CHAIN SESSION</div><h3>Follow the payout.<br />Find it on the name.</h3><p>For <code>rusty-mink.tick.eth</code>, the recorded 0.040 USDC deposit closed at 0.045 USDC. The scorekeeper wrote one session, one winning session, and +0.005 USDC session P&amp;L to ENS. These are historical transaction records, not a live leaderboard. P&amp;L excludes the funding fee and gas.</p></figcaption>
        <div className="session-receipts"><Link href={`${ARC}/tx/${CLOSE_TX}`}>01 / Arc · 0.045 USDC payout</Link><span aria-hidden>↓</span><Link href={`${SEPOLIA}/tx/${STATS_TX}`}>02 / Sepolia · stats updated</Link><Link href={code('ens/README.md')}>Reproduce the event → record flow</Link></div>
      </figure>
      <div className="judge-actions"><a className="key" href="#demo">Play Box Run</a><a className="key" href="#sdk">Build with the SDK</a><Link href={REPO}>Review the repository</Link></div>
    </section>
  );
}
