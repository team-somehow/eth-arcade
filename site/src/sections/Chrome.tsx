export function Nav() {
  return (
    <nav className="topbar">
      <a className="wordmark" href="#top">TIC<em>K</em></a>
      <div className="baraction">
        <a className="key ghostable" href="#proof">What it runs on</a>
        <a className="key ghostable" href="#demo">Play the demo</a>
        <a className="key hot" href="#reserve">Want one?</a>
      </div>
      {/* the rule under the bar is one ten-second window, running whether or
          not anyone is playing — the same clock the device keeps */}
      <div className="window" aria-hidden><i /><b>ten-second window</b></div>
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
