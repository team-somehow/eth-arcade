import { useEffect, useRef, useState } from 'react';
import { Game } from '../game/engine';
import { sfx } from '../game/sfx';

export function Demo() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const deviceRef = useRef<HTMLDivElement>(null);
  const dialRef = useRef<HTMLDivElement>(null);
  const needleRef = useRef<HTMLElement>(null);
  const gameRef = useRef<Game | null>(null);
  const visible = useRef(false);
  const dialAngle = useRef(0);
  const [ledger, setLedger] = useState({ bal: '100.00', hits: '0/0' });
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
      onChange: () => setLedger({ bal: game.fmt(game.model.balance), hits: `${game.model.hits}/${game.model.rounds}` }),
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
        <h2>Play it here first.</h2>
        <p className="lead">
          The same rules, the same odds engine and the same sounds the device runs, on a simulated ETH
          feed. You start with 100 demo USDC. Crank, buy, wait for the bell.
        </p>
      </div>
      <div className="arcade">
        <div>
          <div
            className={'device' + (focused ? ' focus' : '')}
            ref={deviceRef}
            tabIndex={0}
            aria-label="TICK handheld. Use arrow keys to crank, Enter to buy."
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
            <div className="devtag">TICK</div>
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
            <div className="ledger">Balance <b>{ledger.bal}</b> &nbsp; Hits <b>{ledger.hits}</b></div>
          </div>
        </div>
      </div>
    </section>
  );
}
