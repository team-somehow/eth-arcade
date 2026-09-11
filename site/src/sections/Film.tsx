import { useCallback, type ReactNode } from 'react';
import { Stage } from '../three/Stage';
import { bindFilm, useChapter } from '../scroll';

const RAIL = ['Intro', 'The dial', 'The game', 'Inside', 'The sound', 'The numbers'];

function Rail({ chapter }: { chapter: number }) {
  const go = (i: number) => {
    const film = document.querySelector<HTMLElement>('.film');
    if (film) window.scrollTo({ top: film.offsetTop + i * window.innerHeight, behavior: 'smooth' });
  };
  return (
    <nav className="rail" aria-label="Chapters">
      {RAIL.map((label, i) => (
        <button key={label} className={i === chapter ? 'on' : ''} onClick={() => go(i)} aria-current={i === chapter}>
          <i /><span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

function Chapter({ i, side, hero, chapter, children }: { i: number; side: 'left' | 'right'; hero?: boolean; chapter: number; children: ReactNode }) {
  const cls = ['chapter', side, hero ? 'hero' : '', chapter === i ? 'in' : ''].filter(Boolean).join(' ');
  return (
    <div className={cls} style={{ top: `${i * 100}vh` }} id={i === 0 ? 'top' : undefined}>
      <div className="copy">{children}</div>
      {hero && <div className="scrollcue"><i />scroll</div>}
    </div>
  );
}

export function Film() {
  const ref = useCallback((el: HTMLDivElement | null) => bindFilm(el), []);
  const chapter = useChapter();
  return (
    <div className="film" ref={ref}>
      <div className="stage">
        <Stage />
        <div className="glow" />
        <Rail chapter={chapter} />
      </div>

      <Chapter i={0} side="left" hero chapter={chapter}>
        <p className="eyebrow">A crank-powered handheld · ETHOnline 2026</p>
        <h1>THE MARKET,<br />AS AN ARCADE.</h1>
        <p>TICK puts a two-dollar box on the live ETH price ladder and gives you ten seconds. Crank the box into place. Press the yellow button. Where will it land?</p>
        <div className="ctas">
          <a className="btn primary" href="#demo"><span className="dot" />Play it in your browser</a>
          <a className="btn ghost" href="#reserve">Reserve one · $150</a>
        </div>
      </Chapter>

      <Chapter i={1} side="right" chapter={chapter}>
        <p className="eyebrow"><span className="idx">01</span>The control</p>
        <h2>ONE DIAL.</h2>
        <p>There is no menu. The knob on the right moves a box up and down the price ladder, about a quarter-dollar per click. That is the entire control scheme, and it is the point: you place a bet by feel, with your thumb, while the price is moving.</p>
        <p className="small">A KY-040 rotary encoder on GPIO 21, 20 and 16, read raw so no click is ever dropped or queued. Once a bet is placed the dial locks out until the bell — the box does not move.</p>
      </Chapter>

      <Chapter i={2} side="left" chapter={chapter}>
        <p className="eyebrow"><span className="idx">02</span>The game</p>
        <h2>A $2 BOX.<br />TEN SECONDS.</h2>
        <p>The window clock never stops. Park the box on the price and it pays about 1.5×. Crank it two dollars out and the same box pays 25× — odds priced live from how much the market is actually moving, not a table. Inside at the bell, you are paid. Outside, the stake is gone.</p>
        <div className="odds">
          <span>on spot</span><span>1.5×</span>
          <span>one box out</span><span>3.0×</span>
          <span>two boxes out</span><span>12.5×</span>
          <span>full reach</span><span>25×</span>
        </div>
        <p className="small">Every press of the yellow button adds $10 to the same box — priced at that moment's odds, so you cannot top up cheaply after the price walks toward you.</p>
      </Chapter>

      <Chapter i={3} side="right" chapter={chapter}>
        <p className="eyebrow"><span className="idx">03</span>The hardware</p>
        <h2>TWO PARTS.<br />NO SCREWS.</h2>
        <p>Two printed pieces that press together like a box and its lid, on a 5&nbsp;mm lip that runs the whole perimeter. Inside: a Raspberry Pi 5, a 3.5-inch capacitive touch panel on its 40-pin header, the encoder module, two arcade buttons, six jumper wires. Nothing is glued to the case — small L-brackets locate the board wherever you want it.</p>
        <p className="small">104 × 110 × 40 mm. Every part you see here is placed from the OpenSCAD model in the repo; every dimension is a named variable.</p>
      </Chapter>

      <Chapter i={4} side="left" chapter={chapter}>
        <p className="eyebrow"><span className="idx">04</span>The sound</p>
        <h2>IT TELLS YOU<br />WITHOUT LOOKING.</h2>
        <p>A swoop when the price crosses into your box, another when it leaves. A countdown pitched high when you are winning and low when you are not, doubling in tempo for the last two seconds. Three chiptune beds that thicken with the stakes. You can play it with your eyes on the room.</p>
        <p className="small">Every sound is synthesized on the device at boot — square waves, no samples. Out through Bluetooth today; an I²S DAC is the tighter option.</p>
      </Chapter>

      <Chapter i={5} side="right" chapter={chapter}>
        <p className="eyebrow"><span className="idx">05</span>The numbers</p>
        <h2>WHAT&rsquo;S IN IT.</h2>
        <div className="specs">
          <div><b>10 s</b><small>window length</small></div>
          <div><b>$1.41</b><small>box height at $2,500 ETH</small></div>
          <div><b>1.5× – 25×</b><small>payout range</small></div>
          <div><b>480 × 320</b><small>3.5″ IPS, capacitive touch</small></div>
          <div><b>Pi 5</b><small>BCM2712 · 4 GB</small></div>
          <div><b>104 × 110 × 40</b><small>mm, two printed parts</small></div>
          <div><b>USDC</b><small>demo wallet · paper bets</small></div>
          <div><b>Live</b><small>read-only ETH feed, 5 Hz</small></div>
        </div>
      </Chapter>
    </div>
  );
}
