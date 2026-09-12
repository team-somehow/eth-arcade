
const resources = [
  { title: 'Start building', description: 'Install the SDK and scaffold your first game.', path: 'index.html', label: 'SDK quickstart' },
  { title: 'Write a game', description: 'From your first game class to a playable round.', path: 'writing-a-game.html', label: 'Step-by-step tutorial' },
  { title: 'Explore the API', description: 'Inputs, prices, rounds, bets, sound, and more.', path: 'api.html', label: 'API reference' },
  { title: 'Learn by playing', description: 'Explore Coinflip, Ladder, and the feed examples.', path: 'src-examples-coinflip.html', label: 'Example source code' },
];

export function SDK() {
  return (
    <section className="doc sdk" id="sdk" aria-labelledby="sdk-title">
      <div className="sdk-intro">
        <div className="head">
          <div className="eyebrow">02 / YOUR TURN TO CREATE</div>
          <h2 id="sdk-title">One machine.<br />Your next game.</h2>
          <p className="lead">Box Run is one game built with the ETH Arcade SDK. Yours could be next.
            Bring your idea; the SDK handles prices, round timing, odds, wallets, controls, and sound.</p>
          <a className="key hot big" href="/docs/">
            Open SDK docs <span aria-hidden>↗</span>
          </a>
        </div>
        <div className="sdk-terminal">
          <div className="terminal-bar"><span aria-hidden>● ● ●</span><span>YOUR NEXT GAME / PYTHON</span></div>
          <div className="terminal-body">
            <p>After installing the SDK</p>
            <pre><code><span>$</span> tick new mygame{'\n'}<span>$</span> python mygame.py</code></pre>
            <div className="terminal-note">One file. A playable game.<br />Start with simulated prices. Make it your own.</div>
          </div>
        </div>
      </div>
      <div className="sdk-resources">
        {resources.map(({title, description, path, label}) => (
          <a key={path} href={`/docs/${path}`}>
            <span className="resource-label">{label}<span aria-hidden>↗</span></span>
            <h3>{title}</h3><p>{description}</p>
          </a>
        ))}
      </div>
    </section>
  );
}
