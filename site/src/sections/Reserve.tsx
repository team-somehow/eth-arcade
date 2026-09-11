import { useEffect, useState } from 'react';

/** The inbox that should receive reservation requests. Set this before sharing the page. */
const PREORDER_EMAIL = 'orders@example.com';
const PRICE = 150;

export function Reserve() {
  const [qty, setQty] = useState(1);
  const [email, setEmail] = useState('');
  const [reserved, setReserved] = useState<string | null>(null);
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
    const body = `Reservation request — TICK handheld\n\nQuantity: ${qty}\nTotal on delivery: $${qty * PRICE}\nContact: ${email.trim()}\n\nReserved from the landing page on ${new Date().toISOString().slice(0, 10)}.`;
    setReserved(body);
    try { localStorage.setItem('tick-reservation', JSON.stringify({ qty, email: email.trim(), at: Date.now() })); } catch { /* ignore */ }
    location.href = `mailto:${PREORDER_EMAIL}?subject=${encodeURIComponent(`TICK reservation × ${qty}`)}&body=${encodeURIComponent(body)}`;
  };

  const copy = async () => {
    try { await navigator.clipboard.writeText(reserved ?? ''); setCopied('ok'); } catch { setCopied('fail'); }
    setTimeout(() => setCopied('idle'), 1600);
  };

  return (
    <section className="doc" id="reserve">
      <div className="head">
        <p className="eyebrow">Pre-order</p>
        <h2>RESERVE ONE.</h2>
      </div>
      <div className="reserve">
        <div>
          <div className="price">${PRICE}<small>early build · assembled handheld</small></div>
          <ul className="includes">
            <li><b>The handheld</b><span>Two-part printed shell, Raspberry Pi 5, 3.5″ capacitive touch display, KY-040 crank encoder, red and yellow arcade buttons.</span></li>
            <li><b>BOX RUN, installed</b><span>Ten-second windows on a live read-only ETH feed. Demo USDC wallet preloaded.</span></li>
            <li><b>The sounds</b><span>Full cue set and the three reactive chiptune beds. Pair a Bluetooth speaker or fit a DAC.</span></li>
            <li><b>Everything open</b><span>Firmware, odds engine, CAD and STL. Every dimension and every rule is a named constant you can change.</span></li>
          </ul>
        </div>
        <div className={'card' + (reserved ? ' reserved' : '')}>
          <h3>Hold your place</h3>
          <p className="lede">A reservation, not a charge. Nothing is billed — build slots are confirmed by email in order of reservation.</p>
          {!reserved ? (
            <form onSubmit={submit} noValidate>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" name="email" type="email" required autoComplete="email" placeholder="you@somewhere.eth" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="qty">Quantity</label>
                <div className="qty">
                  <button type="button" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Fewer">−</button>
                  <output id="qty">{qty}</output>
                  <button type="button" onClick={() => setQty((q) => Math.min(10, q + 1))} aria-label="More">+</button>
                </div>
              </div>
              <div className="total"><span>Total on delivery</span><b>${(qty * PRICE).toLocaleString('en-US')}</b></div>
              <button className="btn primary reservebtn" type="submit"><span className="dot" />Reserve</button>
              <p className="fineprint">Reserving opens a prefilled email with your request. Prototype hardware; nothing ships until your slot is confirmed.</p>
            </form>
          ) : (
            <div className="done">
              <div className="tick">✓</div>
              <h3>Reserved</h3>
              <p className="lede">Your request is drafted in your mail app — send it and you are in the queue. If nothing opened, copy it below.</p>
              <pre>{reserved}</pre>
              <div className="row">
                <button className="btn ghost" type="button" onClick={copy}>{copied === 'ok' ? 'Copied' : copied === 'fail' ? 'Select and copy above' : 'Copy request'}</button>
                <button className="btn ghost" type="button" onClick={() => { setReserved(null); setQty(1); }}>Reserve another</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
