import { useEffect, useState } from 'react';
import { saveSignup } from '../signups';

/**
 * What an assembled unit would cost to build and send. This is an indication,
 * not an offer: no unit has been sold, nothing is in production, and nothing
 * below creates a queue, a slot, or an obligation to build anything.
 */
const PRICE = 150;

/** A reference the sender can quote back. Generated here, so it is never a claim about an order. */
function reference() { return `EA-${crypto.randomUUID()}`; }

export function Reserve() {
  const [qty, setQty] = useState(1);
  const [email, setEmail] = useState('');
  const [reserved, setReserved] = useState<{ body: string; ref: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('tick-reservation') || 'null');
      if (saved?.email) setEmail(saved.email);
    } catch { /* storage unavailable */ }
  }, []);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const input = e.currentTarget.elements.namedItem('email') as HTMLInputElement;
    if (!input.checkValidity()) { input.focus(); input.reportValidity(); return; }
    if (saving) return;
    setSaving(true);
    setError('');
    const ref = reference();
    const body = `I'd want an ETH Arcade handheld\n\nReference: ${ref}\nHow many: ${qty}\nIndicative cost: $${qty * PRICE} (not an order, nothing owed)\nContact: ${email.trim()}\n\nSent from the ETH Arcade page on ${new Date().toISOString().slice(0, 10)}.`;
    try {
      await saveSignup(email, qty, ref);
      setReserved({ body, ref });
    try { localStorage.setItem('tick-reservation', JSON.stringify({ qty, email: email.trim(), ref, at: Date.now() })); } catch { /* ignore */ }
    } catch {
      setError('We couldn’t save your signup. Please check your connection and try again.');
    } finally { setSaving(false); }
  };

  return (
    <section className="doc" id="reserve">
      <div className="head">
        <div className="eyebrow">04 / THE NEXT CHAPTER</div>
        <h2>Should I build more than one?</h2>
        <p className="lead">
          One exists. Help decide what comes next. An assembled ETH Arcade would cost about <b>$150</b>
          in parts and time. Leave a note if you’d like one — this is an expression of interest,
          with no payment, order, queue, or promise of production.
        </p>
      </div>
      <div className="reserve">
        <ul className="includes">
          <li>
            <b>The handheld, built and flashed</b>
            <span>Two-part printed shell, Raspberry Pi Zero W, 3.5″ panel, KY-040 knob, red and yellow switches, lithium-ion battery, and charging circuit.</span>
          </li>
          <li>
            <b>Box Run, installed</b>
            <span>Ten-second windows on a read-only ETH feed, with the demo USDC wallet preloaded.</span>
          </li>
          <li>
            <b>The sound</b>
            <span>The whole cue set and the three reactive beds. Played through the speaker on the back.</span>
          </li>
          <li>
            <b>Everything open</b>
            <span>Firmware, odds engine, CAD and STLs. Every dimension and every rule is a named constant you can change.</span>
          </li>
        </ul>

        <div className="ticket">
          {!reserved ? (
            <form onSubmit={submit} noValidate>
              <h3>Say you want one</h3>
              <p className="lede">
                Leave your email for ETH Arcade updates. Nothing is charged, now or later.
              </p>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" name="email" type="email" maxLength={254} disabled={saving} required autoComplete="email" placeholder="you@somewhere.eth" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor="qty">How many</label>
                <div className="qty">
                  <button type="button" disabled={saving} onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="One fewer">−</button>
                  <output id="qty">{qty}</output>
                  <button type="button" disabled={saving} onClick={() => setQty((q) => Math.min(10, q + 1))} aria-label="One more">+</button>
                </div>
              </div>
              <div className="perf" aria-hidden />
              <div className="stub">
                <div><span>unit</span><b>ETH Arcade handheld</b></div>
                <div><span>how many</span><b>{qty}</b></div>
                <div><span>charged now</span><b>$0</b></div>
                <div><span>charged later</span><b>$0</b></div>
                <div className="due"><span>would cost about</span><b>${(qty * PRICE).toLocaleString('en-US')}</b></div>
              </div>
              <button className="key hot big reservebtn" type="submit" disabled={saving}><span className="cap" />{saving ? 'Saving…' : 'Keep me updated'}</button>
              {error && <p role="alert">{error}</p>}
              <p className="fineprint">
                We’ll save your email and interest so we can contact you about ETH Arcade. This is not an order or a production commitment.
              </p>
            </form>
          ) : (
            <div className="done" role="status">
              <div className="mark" aria-hidden>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m5 12.5 4.5 4.5L19 7.5" />
                </svg>
              </div>
              <h3>You’re on the list.</h3>
              <p className="lede">
                Your signup is saved. We’ll email you when there’s news about ETH Arcade.
              </p>
              <div className="perf" aria-hidden />
              <div className="stub">
                <div><span>reference</span><b>{reserved.ref}</b></div>
                <div><span>how many</span><b>{qty}</b></div>
                <div className="due"><span>would cost about</span><b>${(qty * PRICE).toLocaleString('en-US')}</b></div>
              </div>

            </div>
          )}
        </div>
      </div>
    </section>
  );
}
