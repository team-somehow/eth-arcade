/**
 * Open the back: the three chains the device actually talks to.
 *
 * Everything here is checkable. Addresses are the deployed ones, the example
 * session is a real one, and the numbers come from the module's own
 * measurements — see substreams/README.md and ens/README.md. Nothing here is a
 * placeholder, and nothing here claims mainnet.
 */

const ARC = 'https://testnet.arcscan.app';
const SEPOLIA = 'https://sepolia.etherscan.io';

const ESCROW = '0x4FA3D366A08aD06D60A0aB141FFb9981EDeE8627';
const REGISTRY = '0xD25ACD4eB42A40D8145E3A7F1feFB17D09649cAa';
const RESOLVER = '0xDBe98b10176aBf0BD2DFEE86fD3ee59A7630FAa8';
const CLOSE_TX = '0x97c982d75198b90af0f29a7cc1e05a49e7283e06c28c851d5e8724078f04bfaf';
const STATS_TX = '0x5e93cabcc92da633c1bf9ebbf82bef0265359b0745fe594fa23327d3a7b86ceb';

const short = (a: string) => `${a.slice(0, 6)}…${a.slice(-4)}`;

/** A hairline connector between two stations on a signal path. */
function Hop() {
  return (
    <svg className="hop" viewBox="0 0 34 8" aria-hidden focusable="false">
      <path d="M0 4h25" />
      <path d="m25.5 1.5 4 2.5-4 2.5" />
    </svg>
  );
}

type Station = { name: string; sub?: string };
type Fact = { k: string; v: string };
type Ref = { label: string; addr: string; href: string };

function Lane({
  tag, title, stations, facts, refs, children,
}: {
  tag: string; title: string; stations: Station[];
  facts: Fact[]; refs?: Ref[]; children: React.ReactNode;
}) {
  return (
    <section className="lane">
      <div className="lane-tag" aria-hidden>{tag}</div>

      <div className="lane-body">
        <h3>{title}</h3>
        <ol className="path">
          {stations.map((s, i) => (
            <li key={s.name + i}>
              {i > 0 && <Hop />}
              <span className="station">
                <b>{s.name}</b>
                {s.sub && <i>{s.sub}</i>}
              </span>
            </li>
          ))}
        </ol>
        <p className="lane-note">{children}</p>
      </div>

      <aside className="evidence">
        <dl className="facts">
          {facts.map((f) => (
            <div key={f.k}><dt>{f.k}</dt><dd>{f.v}</dd></div>
          ))}
        </dl>
        {refs?.map((r) => (
          <a key={r.addr} className="ref" href={r.href} target="_blank" rel="noreferrer">
            <b>{r.label}</b>
            <i>{short(r.addr)}</i>
          </a>
        ))}
      </aside>
    </section>
  );
}

export function Proof() {
  return (
    <section className="doc" id="proof">
      <div className="head">
        <h2>Open the back.</h2>
        <p className="lead">
          Three chains do three jobs for this machine, and none of them is decoration. The price it
          settles on is built in a Substreams pipeline, the money it holds sits in an escrow contract
          on Arc, and every player&rsquo;s record lives on an ENSv2 name. All of it is deployed on
          testnets right now, and every address below opens in a block explorer.
        </p>
      </div>

      <div className="lanes">
        <Lane
          tag="Price"
          title="Twelve pools, two chains, one number."
          stations={[
            { name: 'ETH/USDC pools', sub: 'Arbitrum + Base' },
            { name: 'Pinax packages', sub: 'uniswap_v3 · v4' },
            { name: 'tick_eth_price', sub: 'one module, both chains' },
            { name: 'the device', sub: 'liquidity-weighted' },
          ]}
          facts={[
            { k: 'pools', v: '12' },
            { k: 'chains', v: 'Arbitrum · Base' },
            { k: 'protocols', v: 'Uniswap v3 · v4 · Slipstream' },
            { k: 'moves in a minute', v: '41' },
            { k: 'longest still', v: '2 s' },
            { k: 'widest disagreement', v: '$3.47' },
          ]}
        >
          A bet settles on one number, so that number has to move often and be expensive to push.
          Over one minute the twelve pools together moved the price <b>41 times</b> and never stood
          still for more than two seconds &mdash; while single pools sat quiet and disagreed with each
          other by as much as <b>$3.47</b>, more than twice the height of a box. The module decodes no
          logs of its own: it composes Pinax&rsquo;s <span className="mn">uniswap_v3</span> and{' '}
          <span className="mn">uniswap_v4</span> packages, and the pool list comes from Messari&rsquo;s
          standardized subgraphs &mdash; one query, sent unchanged to every protocol, because the
          schema is shared. The same compiled module runs on Arbitrum and Base; only the pool list
          changes.
        </Lane>

        <Lane
          tag="Money"
          title="The device holds nothing."
          stations={[
            { name: 'your wallet', sub: 'scan, send USDC' },
            { name: 'TickEscrow', sub: 'Arc testnet' },
            { name: 'the device', sub: 'signs the close' },
            { name: 'your wallet', sub: 'cash out' },
          ]}
          facts={[
            { k: 'chain', v: 'Arc testnet · 5042002' },
            { k: 'asset', v: 'USDC' },
            { k: 'win cap reserved', v: '4× the deposit' },
            { k: 'close', v: 'EIP-712, device-signed' },
            { k: 'device gas', v: 'none' },
            { k: 'reclaim after', v: '1 day' },
          ]}
          refs={[{ label: 'TickEscrow · source verified', addr: ESCROW, href: `${ARC}/address/${ESCROW}` }]}
        >
          Bets run off-chain on the handheld; the chain holds both sides&rsquo; money and settles the
          session in one transaction. Opening a session reserves the house&rsquo;s share of a maximum
          win, so a payout is always covered, and the house cannot withdraw while any session is open.
          The device closes by signing a message anyone can submit, so it never needs gas &mdash; and
          if it never closes, you <span className="mn">reclaim</span> your deposit after a day. The
          owner cannot close your session, and cannot touch your deposit.
        </Lane>

        <Lane
          tag="Names"
          title="The leaderboard is the names."
          stations={[
            { name: 'a session closes', sub: 'on Arc' },
            { name: 'scorekeeper', sub: 'the only writer' },
            { name: 'tick.eth resolver', sub: 'ENSv2, Sepolia' },
            { name: 'LEADERS', sub: 'read back from ENS' },
          ]}
          facts={[
            { k: 'chain', v: 'Ethereum Sepolia' },
            { k: 'name', v: '<handle>.tick.eth' },
            { k: 'registry', v: 'own UserRegistry' },
            { k: 'resolver', v: 'own PermissionedResolver' },
            { k: 'stats records', v: '7, scorekeeper-only' },
            { k: 'player keeps', v: 'avatar · url · twitter' },
          ]}
          refs={[
            { label: 'tick.eth registry', addr: REGISTRY, href: `${SEPOLIA}/address/${REGISTRY}` },
            { label: 'Permissioned resolver', addr: RESOLVER, href: `${SEPOLIA}/address/${RESOLVER}` },
          ]}
        >
          Every wallet that plays for real gets <span className="mn">&lt;handle&gt;.tick.eth</span> on
          ENSv2 &mdash; its own registry and its own permissioned resolver, both made through
          ENS&rsquo;s <span className="mn">VerifiableFactory</span> and hung under{' '}
          <span className="mn">.eth</span>. Stats are text records only the scorekeeper key may write,
          while the player keeps <span className="mn">avatar</span>,{' '}
          <span className="mn">description</span>, <span className="mn">url</span> and{' '}
          <span className="mn">com.twitter</span> on their own name. There is no database behind the
          board: it lists the registry&rsquo;s own registration events and reads each name through the
          Universal Resolver. Players never touch Sepolia, never hold ETH there, and never sign
          anything.
        </Lane>
      </div>

      <figure className="endtoend">
        <div className="e2e-head">
          <h3>One session, both chains.</h3>
          <p className="lane-note">
            The money moved on Arc and the name&rsquo;s records followed on Sepolia &mdash;{' '}
            <span className="mn">tick.sessions</span> and <span className="mn">tick.wins</span> to 1,{' '}
            <span className="mn">tick.pnl</span> to <span className="mn">0.005</span>, and{' '}
            <span className="mn">tick.last_tx</span> pointing back at the close it came from. You can
            open both halves.
          </p>
          <div className="e2e-refs">
            <a className="ref" href={`${ARC}/tx/${CLOSE_TX}`} target="_blank" rel="noreferrer">
              <b>The close, on Arc</b><i>{short(CLOSE_TX)}</i>
            </a>
            <a className="ref" href={`${SEPOLIA}/tx/${STATS_TX}`} target="_blank" rel="noreferrer">
              <b>The stats, on Sepolia</b><i>{short(STATS_TX)}</i>
            </a>
          </div>
        </div>
        <div className="tape">
          <div className="tape-row"><span className="t-k">player</span><span className="t-v mn">rusty-mink.tick.eth</span></div>
          <div className="tape-row"><span className="t-k">deposited</span><span className="t-v mn">0.040 USDC</span></div>
          <div className="tape-row"><span className="t-k">cashed out</span><span className="t-v mn">0.045 USDC</span></div>
          <div className="tape-row net"><span className="t-k">net</span><span className="t-v mn">+0.005</span></div>
        </div>
      </figure>
    </section>
  );
}
