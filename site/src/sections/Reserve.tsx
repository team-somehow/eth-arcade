import { useEffect, useState } from 'react';

/** The inbox that should receive reservation requests. Set this before sharing the page. */
const PREORDER_EMAIL = 'orders@example.com';
const PRICE = 150;

/** A reference the buyer can quote back. Generated here, so it is never a claim about an order. */
function reference() {
  const d = new Date();
  const stamp = [d.getFullYear() % 100, d.getMonth() + 1, d.getDate()].map((n) => String(n).padStart(2, '0')).join('');
  return `TK-${stamp}-${String(Math.floor(Math.random() * 9000) + 1000)}`;
}

export function Reserve() {
  const [qty, setQty] = useState(1);
  const [email, setEmail] = useState('');
  const [reserved, setReserved] = useState<{ body: string; ref: string } | null>(null);
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle');

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('tick-reservation') || 'null');
      if (saved?.email) setEmail(saved.email);
    } catch { /* storage unavailable */ }
  }, []);

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const input = e.currentTarget.elements.namedItem('email') as HTMLInputElement;
    if (!input.checkValidity()) { input.focus(); input.reportValidity(); return; }
    const ref = reference();
    const body = `Reservation request — TICK handheld\n\nReference: ${ref}\nQuantity: ${qty}\nDue on delivery: $${qty * PRICE}\nContact: ${email.trim()}\n\nReserved from the landing page on ${new Date().toISOString().slice(0, 10)}.`;
    setReserved({ body, ref });
    try { localStorage.setItem('tick-reservation', JSON.stringify({ qty, email: email.trim(), ref, at: Date.now() })); } catch { /* ignore */ }
    location.href = `mailto:${PREORDER_EMAIL}?subject=${encodeURIComponent(`TICK reservation × ${qty}`)}&body=${encodeURIComponent(body)}`;
  };

  const copy = async () => {
    try { await navigator.clipboard.writeText(reserved?.body ?? ''); setCopied('ok'); } catch { setCopied('fail'); }
    setTimeout(() => setCopied('idle'), 1600);
  };

  return (
    <section className="doc" id="reserve">
      <div className="head">
        <h2>Hold one back for me.</h2>
        <p className="lead">
          $150 an assembled unit, due when your build slot is confirmed. Reserving costs nothing and
          bills nothing — it puts you in the queue in the order the requests arrive.
        </p>
      </div>
      <div className="reserve">
        <ul className="includes">
          <li>
            <b>The handheld, built and flashed</b>
            <span>Two-part printed shell, Raspberry Pi 5, 3.5″ capacitive panel, KY-040 knob, red and yellow switches.</span>
          </li>
          <li>
            <b>BOX RUN, installed</b>
            <span>Ten-second windows on a read-only ETH feed, with the demo USDC wallet preloaded.</span>
          </li>
          <li>
            <b>The sound</b>
            <span>The whole cue set and the three reactive beds. Pair a Bluetooth speaker, or fit a DAC.</span>
          </li>
          <li>
            <b>Everything open</b>
            <span>Firmware, odds engine, CAD and STLs. Every dimension and every rule is a named constant you can change.</span>
          </li>
        </ul>

        <div className="ticket">
          {!reserved ? (
            <form onSubmit={submit} noValidate>
              <h3>Reservation</h3>
              <p className="lede">We confirm slots by email. Nothing is charged today.</p>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" name="email" type="email" required autoComplete="email" placeholder="you@somewhere.eth" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="qty">How many</label>
                <div className="qty">
                  <button type="button" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="One fewer">−</button>
                  <output id="qty">{qty}</output>
                  <button type="button" onClick={() => setQty((q) => Math.min(10, q + 1))} aria-label="One more">+</button>
                </div>
              </div>
              <div className="perf" aria-hidden />
              <div className="stub">
                <div><span>unit</span><b>TICK handheld</b></div>
                <div><span>quantity</span><b>{qty}</b></div>
                <div><span>today</span><b>$0</b></div>
                <div className="due"><span>due on delivery</span><b>${(qty * PRICE).toLocaleString('en-US')}</b></div>
              </div>
              <button className="key hot big reservebtn" type="submit"><span className="cap" />Reserve</button>
              <p className="fineprint">Reserving opens a prefilled email you send yourself. Prototype hardware: nothing ships until your slot is confirmed.</p>
            </form>
          ) : (
            <div className="done">
              <div className="mark" aria-hidden>✓</div>
              <h3>You&rsquo;re in the queue</h3>
              <p className="lede">Your request is drafted in your mail app — send it and the slot is held. If nothing opened, copy it below.</p>
              <div className="perf" aria-hidden />
              <div className="stub">
                <div><span>reference</span><b>{reserved.ref}</b></div>
                <div><span>quantity</span><b>{qty}</b></div>
                <div className="due"><span>due on delivery</span><b>${(qty * PRICE).toLocaleString('en-US')}</b></div>
              </div>
              <pre>{reserved.body}</pre>
              <div className="row">
                <button className="key" type="button" onClick={copy}>{copied === 'ok' ? 'Copied' : copied === 'fail' ? 'Select and copy above' : 'Copy the request'}</button>
                <button className="key" type="button" onClick={() => { setReserved(null); setQty(1); }}>Reserve another</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
