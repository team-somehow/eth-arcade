export function Nav() {
  return (
    <nav className="topbar" aria-label="Main navigation">
      <a className="wordmark" href="#top">ETH Arcade</a>

      <div className="baraction">
        <a className="key docs-nav" href="/docs/">Docs</a>
        <a className="key ghostable" href="#proof">Integrations</a>
        <a className="key ghostable" href="#demo">Play Box Run</a>
        <a className="key hot" href="#reserve">Get in on it <span aria-hidden>↗</span></a>
      </div>
      {/* the rule under the bar is one ten-second window, running whether or
          not anyone is playing — the same clock the device keeps */}
      <div className="window" aria-hidden><i /></div>
    </nav>
  );
}

export function Footer() {
  return (
    <footer>
      <span className="wordmark">ETH Arcade</span>
      <p>
        Built at ETHOnline 2026. Prices are read-only. Every bet on this page is paper and its
        balance is demo money; on the device, money is paper by default and real USDC only on Arc
        testnet. Nothing here runs on mainnet. Firmware, odds engine, contracts and CAD are open
        source.
      </p>
      <a className="source-link" href="https://github.com/team-somehow/eth-arcade" target="_blank" rel="noopener noreferrer">Explore the source ↗</a>
    </footer>
  );
}
