export function Nav() {
  return (
    <nav className="topbar" aria-label="Main navigation">
      <a className="wordmark" href="#top">TIC<em>K</em></a>
      <span className="brand-note">Small device. Big little moments.</span>
      <div className="baraction">
        <a className="key ghostable" href="#proof">Under the hood</a>
        <a className="key ghostable" href="#demo">Play the demo</a>
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
      <span className="wordmark">TIC<em>K</em></span>
      <p>
        Built at ETHOnline 2026. Prices are read-only. Every bet on this page is paper and its
        balance is demo money; on the device, money is paper by default and real USDC only on Arc
        testnet. Nothing here runs on mainnet. Firmware, odds engine, contracts and CAD are open
        source.
      </p>
    </footer>
  );
}
