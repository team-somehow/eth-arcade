import { useCallback, type ReactNode } from 'react';
import { Stage } from '../three/Stage';
import { bindFilm, useChapter } from '../scroll';

const RAIL = ['Intro', 'The knob', 'The game', 'Inside', 'The sound', 'The numbers'];

function Rail({ chapter }: { chapter: number }) {
  const go = (i: number) => {
    const film = document.querySelector<HTMLElement>('.film');
    if (film) window.scrollTo({ top: film.offsetTop + i * window.innerHeight, behavior: 'smooth' });
  };
  return (
    <nav className="rail" aria-label="Chapters">
      {RAIL.map((label, i) => (
        <button key={label} className={i === chapter ? 'on' : ''} onClick={() => go(i)} aria-current={i === chapter}>
          <span>{label}</span><i />
        </button>
      ))}
    </nav>
  );
}

/** A nameplate: the machine's own way of stating a fact. */
function Plate({ rows, wide }: { rows: [string, string][]; wide?: boolean }) {
  return (
    <dl className={'plate' + (wide ? ' wide' : '')}>
      {rows.map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  );
}

function Chapter({ i, hero, chapter, children }: { i: number; hero?: boolean; chapter: number; children: ReactNode }) {
  const cls = ['chapter', hero ? 'hero' : '', chapter === i ? 'in' : ''].filter(Boolean).join(' ');
  return (
    <div className={cls} style={{ top: `${i * 100}vh` }} id={i === 0 ? 'top' : undefined}>
      <div className="copy"><div className="eyebrow">{hero ? <><span className="status-dot" /> A pocket-sized market arcade</> : <><span>{String(i).padStart(2, '0')}</span> / {RAIL[i]}</>}</div>{children}</div>
      {hero && <div className="scrollcue"><span aria-hidden>↓</span> Scroll to meet ETH Arcade.fun</div>}
    </div>
  );
}

export function Film() {
  const ref = useCallback((el: HTMLDivElement | null) => bindFilm(el), []);
  const chapter = useChapter();
  return (
    <div className="film" ref={ref}>
      <div className="stage">
        <div className="stage-word" aria-hidden>PLAY.</div>
        <Stage />
        <div className="stage-caption"><span>FIG. {String(chapter + 1).padStart(2, '0')} / {RAIL[chapter]}</span><span>DESIGNED TO BE PLAYED.</span></div>
        <div className="glow" />
        <div className="frame" aria-hidden><span /><span /><span /><span /></div>
        <Rail chapter={chapter} />
      </div>

      <Chapter i={0} hero chapter={chapter}>
        <h1>The market.<br />Now <span className="hero-accent">in play.</span></h1>
        <p className="lead">
          Meet ETH Arcade.fun. A tiny handheld that turns the ETH price into an arcade.
          One knob. Two buttons. Ten seconds to make your move.
        </p>
        <div className="ctas">
          <a className="key hot big" href="#demo">Let’s play <span aria-hidden>↗</span></a>
          <a className="text-link" href="#reserve">I want one <span aria-hidden>→</span></a>
        </div>
        <div className="hero-facts"><span><b>10s</b> per round</span><span><b>100%</b> open source</span></div>
      </Chapter>

      <Chapter i={1} chapter={chapter}>
        <h2>One knob, and no menu.</h2>
        <p>
          The knob on the right wall moves a box up and down the price, eighteen cents a click. That is
          the whole control scheme, and it is the point: you place a bet by feel, with your thumb, while
          the price is still moving. Once you buy, the knob locks out until the bell — the box you bought
          is the box that settles.
        </p>
        <Plate rows={[
          ['encoder', 'KY-040, read raw'],
          ['pins', 'CLK 21 · DT 20 · SW 16'],
          ['one click', '$0.18 at $2,500 ETH'],
          ['full reach', '± $2.12 from the open'],
        ]} />
      </Chapter>

      <Chapter i={2} chapter={chapter}>
        <h2>A $1.41 box. Ten seconds.</h2>
        <p>
          The window clock never stops. Park the box on the price and it pays a little over its stake;
          crank it out of reach and the same box pays the cap. Nothing about the box changes — only how
          far you put it from where the price is now.
        </p>
        <figure className="ladder">
          <div className="row"><span className="where">on the price</span><span className="track"><i className="box" style={{ '--at': 'calc(50% - 12px)' } as React.CSSProperties} /></span><span className="pays">1.5×</span></div>
          <div className="row"><span className="where">one box out</span><span className="track"><i className="box" style={{ '--at': 'calc(70% - 12px)' } as React.CSSProperties} /></span><span className="pays">5×</span></div>
          <div className="row"><span className="where">two boxes out</span><span className="track"><i className="box" style={{ '--at': 'calc(90% - 12px)' } as React.CSSProperties} /></span><span className="pays">25×</span></div>
          <figcaption>
            Typical quotes on a calm ETH tape. Every box is priced from the volatility the device has
            just measured, so the ladder moves with the market. 25× is the cap.
          </figcaption>
        </figure>
      </Chapter>

      <Chapter i={3} chapter={chapter}>
        <h2>Two printed parts. No screws.</h2>
        <p>
          The shell is a body and a lid that press together on a 5 mm lip running the whole perimeter.
          Inside: a Raspberry Pi Zero W, a 3.5-inch panel on the first 26 header pins, the encoder
          bolted through the right wall, two 12 mm switches with two leads each, seven jumpers, and a rear-mounted speaker. Nothing is glued down —
          small printed L-brackets stop the board where you want it.
        </p>
        <Plate rows={[
          ['case', '104 × 110 × 40 mm'],
          ['wall', '2.5 mm, 3 mm fillet'],
          ['join', '5 mm lip, 0.3 mm clearance'],
          ['board', 'Raspberry Pi Zero W'],
        ]} />
      </Chapter>

      <Chapter i={4} chapter={chapter}>
        <h2>You can play it without looking.</h2>
        <p>
          A swoop when the price crosses into your box, another when it leaves. A countdown pitched high
          while you are winning and low while you are not, doubling in tempo for the last two seconds.
          Three chiptune beds that thicken as the money goes on. Hit three in a row and the rider on the
          screen catches fire.
        </p>
        <Plate rows={[
          ['synthesis', 'square wave, at boot'],
          ['samples', 'none'],
          ['beds', 'idle · live · final'],
          ['out', 'rear-mounted speaker'],
        ]} />
      </Chapter>

      <Chapter i={5} chapter={chapter}>
        <h2>What&rsquo;s in it.</h2>
        <Plate wide rows={[
          ['window', '10 seconds, rolling'],
          ['box height', '$1.41 at $2,500 ETH'],
          ['payout range', '1.05× to 25×'],
          ['display', '3.5″ IPS, 480 × 320'],
          ['computer', 'Raspberry Pi Zero W, 512 MB'],
          ['shell', '104 × 110 × 40 mm'],
          ['money', 'demo USDC, paper bets'],
          ['feed', 'read-only ETH, 5 Hz'],
        ]} />
      </Chapter>
    </div>
  );
}
