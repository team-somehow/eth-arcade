export function Nav() {
  return (
    <nav className="topnav">
      <a className="wordmark" href="#top">TIC<b>K</b></a>
      <div className="navlinks">
        <a href="#demo">Play the demo</a>
        <a className="hot" href="#reserve">Reserve · $150</a>
      </div>
    </nav>
  );
}

export function Footer() {
  return (
    <footer>
      <span className="wordmark">TIC<b>K</b></span>
      <span>Built at ETHOnline 2026 · prices are read-only and every bet is paper · the USDC balance is demo money · firmware, odds engine and CAD are open source</span>
    </footer>
  );
}
