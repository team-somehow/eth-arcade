import { useEffect, useRef, useState } from 'react';
import { Game, type Result } from '../game/engine';
import { sfx } from '../game/sfx';

/** How many settled windows the readout keeps. Enough to show a run, short
 *  enough that the panel never grows the page under you. */
const LOG_LEN = 6;

export function Demo() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const deviceRef = useRef<HTMLDivElement>(null);
  const dialRef = useRef<HTMLDivElement>(null);
  const needleRef = useRef<HTMLElement>(null);
  const gameRef = useRef<Game | null>(null);
  const visible = useRef(false);
  const dialAngle = useRef(0);
  const [ledger, setLedger] = useState({ bal: '100.00', hits: '0/0' });
  const [log, setLog] = useState<Result[]>([]);
  /** The best multiple actually paid this session — a quoted multiple that
   *  missed paid nothing, so it is not a best. */
  const [best, setBest] = useState(0);
  const seenRounds = useRef(0);
  const [sound, setSound] = useState(false);
  const [focused, setFocused] = useState(false);
  const [redDown, setRedDown] = useState(false);
  const [yellowDown, setYellowDown] = useState(false);

  const crank = (steps: number) => {
    gameRef.current?.crank(steps);
    dialAngle.current += steps * 15;
    if (needleRef.current) needleRef.current.style.transform = `rotate(${dialAngle.current}deg)`;
    dialRef.current?.setAttribute('aria-valuenow', String(Math.round(dialAngle.current / 15)));
  };
  const flash = (set: (v: boolean) => void) => { set(true); setTimeout(() => set(false), 110); };
  const pressYellow = () => { gameRef.current?.buy(); flash(setYellowDown); };
  const pressRed = () => { gameRef.current?.note('RED IS BACK ON THE DEVICE', 1.5); flash(setRedDown); };

  useEffect(() => {
    const canvas = canvasRef.current!, device = deviceRef.current!;
    const game = new Game(canvas, sfx, {
      seed: 3,
      onChange: () => {
        const m = game.model;
        setLedger({ bal: game.fmt(m.balance), hits: `${m.hits}/${m.rounds}` });
        // rounds only ever increases, and only when a window has settled — so
        // it, not `last`, is what tells us a new result is worth recording.
        if (m.rounds > seenRounds.current && m.last) {
          seenRounds.current = m.rounds;
          const r = m.last;
          setLog((prev) => [r, ...prev].slice(0, LOG_LEN));
          if (r.hit) setBest((b) => Math.max(b, r.multiple));
        }
      },
    });
    gameRef.current = game;
    let raf = 0, last = performance.now() / 1000;
    const t0 = last;
    const loop = () => {
      const now = performance.now() / 1000, dt = Math.min(.1, now - last);
      last = now;
      game.step(dt, now);
      if (visible.current || now - t0 < 4) game.draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    const io = new IntersectionObserver((es) => es.forEach((e) => { visible.current = e.isIntersecting; }), { threshold: .2 });
    io.observe(device);

    const onKey = (e: KeyboardEvent) => {
      if (!visible.current) return;
      const t = e.target as HTMLElement | null;
      if (t && /INPUT|TEXTAREA/.test(t.tagName)) return;
      switch (e.key) {
        case 'ArrowUp': case 'w': case 'W': e.preventDefault(); crank(1); break;
        case 'ArrowDown': case 's': case 'S': e.preventDefault(); crank(-1); break;
        case 'Enter': case ' ': case 'ArrowRight': if (e.repeat) return; e.preventDefault(); pressYellow(); break;
        case 'ArrowLeft': if (e.repeat) return; e.preventDefault(); pressRed(); break;
      }
    };
    addEventListener('keydown', onKey);

    let wheelAcc = 0;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      wheelAcc += e.deltaY;
      while (Math.abs(wheelAcc) >= 40) { crank(wheelAcc > 0 ? -1 : 1); wheelAcc -= Math.sign(wheelAcc) * 40; }
    };
    const screen = canvas.parentElement!;
    screen.addEventListener('wheel', onWheel, { passive: false });

    const dial = dialRef.current!;
    let dragging = false, lastA = 0, carry = 0;
    const angleOf = (e: PointerEvent) => {
      const r = dial.getBoundingClientRect();
      return (Math.atan2(e.clientY - (r.top + r.height / 2), e.clientX - (r.left + r.width / 2)) * 180) / Math.PI;
    };
    const down = (e: PointerEvent) => { dragging = true; lastA = angleOf(e); carry = 0; dial.setPointerCapture(e.pointerId); device.focus({ preventScroll: true }); };
    const move = (e: PointerEvent) => {
      if (!dragging) return;
      let d = angleOf(e) - lastA;
      if (d > 180) d -= 360; if (d < -180) d += 360;
      lastA += d; carry += d;
      while (Math.abs(carry) >= 15) { crank(carry > 0 ? 1 : -1); carry -= Math.sign(carry) * 15; }
    };
    const up = () => { dragging = false; };
    dial.addEventListener('pointerdown', down);
    dial.addEventListener('pointermove', move);
    dial.addEventListener('pointerup', up);
    dial.addEventListener('pointercancel', up);
    const dialKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowUp' || e.key === 'ArrowRight') { e.preventDefault(); crank(1); }
      if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') { e.preventDefault(); crank(-1); }
    };
    dial.addEventListener('keydown', dialKey);

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      removeEventListener('keydown', onKey);
      screen.removeEventListener('wheel', onWheel);
      dial.removeEventListener('pointerdown', down);
      dial.removeEventListener('pointermove', move);
      dial.removeEventListener('pointerup', up);
      dial.removeEventListener('pointercancel', up);
      dial.removeEventListener('keydown', dialKey);
      sfx.disable();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleSound = () => {
    if (sfx.enabled) { sfx.disable(); setSound(false); }
    else { sfx.enable(); sfx.play('enter'); setSound(true); }
  };

  return (
    <section className="doc" id="demo">
      <div className="head">
        <div className="eyebrow">01 / A GAME BUILT WITH THE SDK</div>
        <h2>Meet Box Run.</h2>
        <p className="lead">
          Our game, built with the ETH Arcade SDK. Place a box on the ETH price, crank the dial,
          and wait for the bell. Try it here on a simulated feed with 100 demo USDC.
        </p>
      </div>
      <div className="demo-mode"><span className="mode-dot" aria-hidden />Browser demo · Simulated prices · Paper USDC<a href="#proof">Explore the device’s on-chain integrations <span aria-hidden>↗</span></a></div>
      <div className="arcade">
        <div>
          <div
            className={'device' + (focused ? ' focus' : '')}
            ref={deviceRef}
            tabIndex={0}
            aria-label="ETH Arcade handheld. Use arrow keys to crank, Enter to buy."
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onClick={() => deviceRef.current?.focus({ preventScroll: true })}
          >
            <div className="bezel" />
            <div className="screen"><canvas ref={canvasRef} width={480} height={320} /></div>
            <button className={'pbtn red' + (redDown ? ' down' : '')} onClick={pressRed} aria-label="Red button: back"><i /><span>BACK</span></button>
            <button className={'pbtn yellow' + (yellowDown ? ' down' : '')} onClick={pressYellow} aria-label="Yellow button: buy the next 10 seconds"><i /><span>BUY 10</span></button>
            <div className="dial" ref={dialRef} role="slider" aria-label="Crank dial" aria-valuemin={-12} aria-valuemax={12} aria-valuenow={0} tabIndex={0}>
              <div className="knurl" /><i ref={needleRef} />
            </div>
            <div className="devtag">ETH Arcade</div>
          </div>
        </div>
        <div>
          <div className="controls">
            <div><span className="k">crank</span><span className="v"><kbd>↑</kbd><kbd>↓</kbd>, scroll over the screen, or drag the knob</span></div>
            <div><span className="k">buy</span><span className="v"><kbd>Enter</kbd> or the yellow button. Press again to add another $10 at the odds on offer then.</span></div>
            <div><span className="k">watch</span><span className="v">Your box rides in from the right. The rider is the price; the post he reaches is the bell.</span></div>
            <div><span className="k">win</span><span className="v">The rider inside the box at the bell. The boundary counts. Three in a row and he catches fire.</span></div>
          </div>
          <div className="sound">
            <button className={'toggle' + (sound ? ' on' : '')} onClick={toggleSound} aria-pressed={sound}><span className="led" />{sound ? 'Sound on' : 'Sound off'}</button>
          </div>

          <div className="readout">
            <dl className="plate">
              <div><dt>balance</dt><dd>{ledger.bal} <span className="unit">demo USDC</span></dd></div>
              <div><dt>hit / played</dt><dd>{ledger.hits}</dd></div>
              <div><dt>best so far</dt><dd>{best ? `${best.toFixed(1)}×` : '—'}</dd></div>
            </dl>

            <h3 className="rd-title">Settled windows</h3>
            {log.length === 0 ? (
              <p className="rd-empty">
                Nothing has settled yet. Crank the knob to move the box, then press buy &mdash; the
                first bell is ten seconds later.
              </p>
            ) : (
              <ol className="rd-log">
                {log.map((r, i) => (
                  <li key={seenRounds.current - i} className={r.hit ? 'hit' : 'miss'}>
                    <span className="rd-mult">{r.multiple.toFixed(1)}×</span>
                    <span className="rd-flow">
                      {(r.stake / 1e6).toFixed(0)}
                      <svg className="rd-arrow" viewBox="0 0 20 8" aria-hidden focusable="false">
                        <path d="M0 4h13" /><path d="m13.5 1.5 4 2.5-4 2.5" />
                      </svg>
                      {(r.payout / 1e6).toFixed(0)}
                    </span>
                    <span className="rd-verdict">{r.hit ? 'paid' : 'lost'}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
