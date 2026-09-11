export function Nav() {
  return (
    <nav className="topbar">
      <a className="wordmark" href="#top">TIC<em>K</em></a>
      <div className="baraction">
        <a className="key ghostable" href="#demo">Play the demo</a>
        <a className="key hot" href="#reserve">Reserve for $150</a>
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
        Built at ETHOnline 2026. Prices are read-only, every bet on this page is paper, and the
        USDC balance is demo money. Firmware, odds engine and CAD are open source.
      </p>
    </footer>
  );
}
