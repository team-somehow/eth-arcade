/**
 * BOX RUN — the rules and the 480x320 screen, ported from the device firmware
 * (firmware/games/box_model.py, box.py and box_scene.py). Same geometry, same
 * odds engine, same realized-volatility estimator, same status lines, and the
 * same night-city world: the rider is "now", history scrolls away behind him
 * and every bell rides in from the right.
 *
 * Money is integer micro-USDC here exactly as on the device, so a payout can
 * never round up into money the book did not owe.
 */
import type { Sfx } from './sfx';
import { Floaters, Rider, Skyline, Sparks, mix, rgb, FLAME, type RGB } from './scene';

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

export const MICRO = 1_000_000;

export interface Tick { price: number; seq: number; t: number }
export interface Order { level: number; half: number; low: number; high: number; stake: number; payout: number; multiple: number }
export interface Result { hit: boolean; price: number; stake: number; payout: number; multiple: number; low: number; high: number; voided: boolean }

/** Two decimals by default — as many as the stake needs, like the device. */
export const usdc = (micro: number, places = 2) =>
  (micro / MICRO).toLocaleString('en-US', { minimumFractionDigits: places, maximumFractionDigits: places });

/* ---------------- market: simulated ETH at live-like volatility ---------------- */
export class Feed {
  price = 2500;
  seq = 0;
  private acc = 0;
  private s: number;
  /** ETH's volatility per square-root second, as the device's sim uses. */
  static SIGMA = 0.00009;
  constructor(seed = 7) { this.s = (seed >>> 0) || 1; }
  rand() {
    this.s ^= this.s << 13; this.s >>>= 0;
    this.s ^= this.s >>> 17;
    this.s ^= this.s << 5; this.s >>>= 0;
    return this.s / 4294967296;
  }
  gauss() {
    let u = 0, v = 0;
    while (!u) u = this.rand();
    while (!v) v = this.rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  /** 20 Hz ticks, accumulated so the same wall time yields the same ticks at any frame rate. */
  poll(dt: number, now: number): Tick[] {
    this.acc += Math.max(0, dt);
    const out: Tick[] = [];
    while (this.acc >= .05) {
      this.acc -= .05;
      this.seq++;
      this.price *= Math.exp(this.gauss() * Feed.SIGMA * Math.sqrt(.05));
      out.push({ price: this.price, seq: this.seq, t: now });
    }
    return out;
  }
}

/* ---------------- rules ---------------- */
function erf(x: number) {
  const s = Math.sign(x); x = Math.abs(x);
  const t = 1 / (1 + .3275911 * x);
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - .284496736) * t + .254829592) * t) * Math.exp(-x * x);
  return s * y;
}
const Phi = (x: number) => .5 * (1 + erf(x / Math.SQRT2));
const DEFAULT_VAR = (.55 * .55) / 31_536_000;

/** A real price change, not float noise: a thousandth of a basis point. */
const moved = (before: number, after: number) => Math.abs(after - before) > before * 1e-7;

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const h = s.length >> 1;
  return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
};

export class BoxModel {
  readonly WINDOW = 10;
  readonly STAKE = 10 * MICRO;
  readonly MAXX = 25;
  readonly MIN_MULTIPLE = 1.05;
  readonly STALE_AFTER = 4;
  readonly VOID_AFTER = 4;
  readonly VOL_WINDOW_S = 60;
  readonly MIN_MOVES = 10;
  readonly READ_S = 3;
  readonly SPIKE_CAP = 4;
  readonly PRIOR_S = 10;
  readonly QUIET_AFTER = 15;
  /** Geometry quoted for a 20-second window and scaled by the square root of time. */
  readonly SCALE = Math.sqrt(10 / 20);

  balance = 100 * MICRO;
  tick: Tick | null = null;
  history: Tick[] = [];
  measured = false;              // seen enough of the feed to price from it
  lastMoveAt = -Infinity;        // when the price last actually changed
  refused = '';
  aim = 0; open = 0; half = 0; step = 0; reach = 0; view = 0;
  live: Order | null = null;
  pending: Order | null = null;
  windowEnd = 0;
  settling = false;              // expired, waiting for a price to settle on
  started = false;
  windows = 0; rounds = 0; hits = 0;
  last: Result | null = null;
  private variance = 0;

  get price() { return this.tick ? this.tick.price : 0; }
  /** Once the next window is bought the position is fixed; only money is still open. */
  get locked() { return !!this.pending; }
  get move() { return this.started ? this.price - this.open : 0; }
  /** Is the price inside the live bet's box right now? null when no bet. */
  get inside(): boolean | null {
    return this.live && this.live.stake ? this.price >= this.live.low && this.price <= this.live.high : null;
  }
  remaining(now: number) { return Math.max(0, this.windowEnd - now); }
  canBuy() { return this.balance >= this.STAKE; }
  fresh(now: number) { return !!this.tick && now - this.tick.t <= this.STALE_AFTER; }
  /** True when the price has sat on one value for QUIET_AFTER seconds. */
  quiet(now: number) { return this.started && now - this.lastMoveAt >= this.QUIET_AFTER; }

  /**
   * Size the box and the view from the window's opening price — taken from the
   * price rather than from volatility, so a placed box is never redrawn at a
   * different size than it was bought at.
   */
  private geom() {
    const b = (this.open / 10000) * this.SCALE;
    this.half = b * 4;      // BOX_BPS 8, halved
    this.step = b;          // STEP_BPS 1
    this.reach = b * 12;    // REACH_BPS 12
    this.view = b * 16;     // reach + half a box: the cursor can never leave the band
  }
  private inReach(v: number) { return clamp(v, this.open - this.reach, this.open + this.reach); }

  /**
   * Realized variance over the last minute of wall time, stillness included.
   * Time spent on one price counts as exactly that — a book nobody traded in is
   * a calm market, and the bell settles on that same price. Each move is capped
   * at SPIKE_CAP median moves so one bad print cannot resize the odds.
   */
  private measure() {
    const pts: Tick[] = [];
    const end = this.history.length ? this.history[this.history.length - 1].t : 0;
    for (let i = this.history.length - 1; i >= 0; i--) {
      if (end - this.history[i].t > this.VOL_WINDOW_S) break;
      pts.push(this.history[i]);
    }
    pts.reverse();
    const moves: number[] = [];
    for (let i = 1; i < pts.length; i++) {
      if (moved(pts[i - 1].price, pts[i].price)) moves.push(Math.log(pts[i].price / pts[i - 1].price));
    }
    const span = pts.length ? pts[pts.length - 1].t - pts[0].t : 0;
    if (moves.length && (moves.length >= this.MIN_MOVES || span >= this.READ_S)) this.measured = true;
    if (!this.measured) return DEFAULT_VAR;
    let total = 0;
    if (moves.length) {
      const cap = (this.SPIKE_CAP * median(moves.map(Math.abs))) ** 2;
      for (const r of moves) total += Math.min(r * r, cap);
    }
    // A minute of real data outweighs the prior six to one.
    const variance = (total + DEFAULT_VAR * this.PRIOR_S) / (span + this.PRIOR_S);
    return Math.max(variance, DEFAULT_VAR / 20);
  }

  sigma(h: number) { return this.price * Math.sqrt((this.variance || DEFAULT_VAR) * Math.max(h, .001)); }
  probability(level: number, half: number, h: number) {
    const s = this.sigma(h);
    if (s <= 0 || this.price <= 0) return 0;
    return Math.max(0, Phi((level + half - this.price) / s) - Phi((level - half - this.price) / s));
  }
  /** Return multiple for a box bought now; the horizon runs to the bell being bought. */
  quote(level: number, now: number, half = this.half) {
    const p = this.probability(level, half, this.remaining(now) + this.WINDOW);
    return p <= 0 ? 0 : Math.min(this.MAXX, 1 / p);
  }

  /** A bought box cannot be repositioned, so the dial does nothing until the bell. */
  crank(steps: number) {
    if (!steps || !this.started || this.locked) return false;
    this.aim = this.inReach(this.aim + steps * this.step);
    return true;
  }

  /**
   * One stake on the next window at the cursor. The first press fixes that
   * window's level; later presses add stake at the odds available when they are
   * made, so a box cannot be topped up at a stale multiple.
   */
  buy(now: number) {
    this.refused = '';
    if (!this.started || !this.fresh(now) || this.settling || this.quiet(now) || !this.measured) return false;
    const level = this.pending ? this.pending.level : this.aim;
    const half = this.pending ? this.pending.half : this.half;
    const m = this.quote(level, now, half);
    if (m < this.MIN_MULTIPLE) { this.refused = 'under'; return false; }
    if (this.balance < this.STAKE) return false;
    this.balance -= this.STAKE;
    if (!this.pending) this.pending = { level, half, low: level - half, high: level + half, stake: 0, payout: 0, multiple: 0 };
    this.pending.stake += this.STAKE;
    this.pending.payout += this.STAKE * m;
    this.pending.multiple = this.pending.payout / this.pending.stake;
    return true;
  }

  onTick(t: Tick, now: number) {
    if (!isFinite(t.price) || t.price <= 0) return;
    if (this.tick && t.seq <= this.tick.seq) return;
    if (now - t.t > this.STALE_AFTER) return;
    if (!this.tick || moved(this.tick.price, t.price)) this.lastMoveAt = t.t;
    this.tick = t;
    this.history.push(t);
    if (this.history.length > 2400) this.history.shift();
    this.variance = this.measure();
    if (!this.started) {
      this.started = true;
      this.aim = this.open = t.price;
      this.geom();
      this.windowEnd = now + this.WINDOW;
    }
    this.update(now);
  }

  /** A quote from before expiry is not an expiry price, however fresh it looks. */
  private settleable() { return !!this.tick && this.tick.t >= this.windowEnd; }

  /** Roll the window clock. Safe every frame; time-driven only. */
  update(now: number) {
    if (!this.started) return;
    while (now >= this.windowEnd) {
      const o = this.live;
      if (o && o.stake) {
        if (!this.settleable() || !this.fresh(now)) {
          if (now - this.windowEnd <= this.VOID_AFTER) { this.settling = true; return; }
          this.voidOut(o);
        } else this.settle(o);
      }
      this.settling = false;
      this.live = this.pending;
      this.pending = null;
      this.windows++;
      this.windowEnd += this.WINDOW;
      // The new window opens here, and the cursor — free again — is pulled
      // back into reach of the new anchor.
      this.open = this.price;
      this.geom();
      this.aim = this.inReach(this.aim);
    }
  }

  private settle(o: Order) {
    const hit = this.price >= o.low && this.price <= o.high;
    const payout = hit ? Math.floor(o.payout) : 0;    // truncated to micro-USDC
    this.balance += payout;
    this.rounds++;
    if (hit) this.hits++;
    this.last = { hit, price: this.price, stake: o.stake, payout, multiple: o.multiple, low: o.low, high: o.high, voided: false };
  }

  /** No usable expiry price: return the stake, record nothing as won. */
  private voidOut(o: Order) {
    this.balance += o.stake;
    this.rounds++;
    this.last = { hit: false, price: this.price, stake: o.stake, payout: o.stake, multiple: o.multiple, low: o.low, high: o.high, voided: true };
  }
}

/* ---------------- the device screen, 480 x 320 ---------------- */
export const PAL = {
  NAVY: '#0C1924', PANEL: '#162833', GRID: '#1E323D', CREAM: '#F4ECD2', MUTED: '#90A7AD',
  YELLOW: '#FFCC48', MINT: '#7FE4B8', RED: '#E9645B',
};
const C_CREAM: RGB = [244, 236, 210];
const C_MUTED: RGB = [144, 167, 173];
const C_YELLOW: RGB = [255, 204, 72];
const C_MINT: RGB = [127, 228, 184];
const C_RED: RGB = [233, 100, 91];
const OPEN_LINE = 'rgb(74,96,103)';
const POST: RGB = [40, 58, 76];
const POST_NOW = 'rgb(88,110,128)';
const GLOW = 'rgb(44,80,98)';
const SHADE = 'rgba(80,170,210,0.12)';

// Time is one horizontal scale across the whole screen: the rider sits at
// RIDER_X at "now", history is to the left, and every bell is a post ahead
// that slides toward him at PX_PER_S.
const PLAY = { left: 0, top: 34, right: 480, bottom: 242, w: 480, h: 208 };
const STREET_BOTTOM = 274;
const MID_Y = 138, HALF_PX = 92;
const BAND_TOP = PLAY.top + 4, BAND_BOTTOM = PLAY.bottom - 4;
const RIDER_X = 120, PX_PER_S = 16, BOX_W = 44;
const FONT = '"IBM Plex Mono", Menlo, Consolas, monospace';
const font = (size: number) => `700 ${size}px ${FONT}`;

const easeOut = (p: number) => 1 - (1 - clamp(p, 0, 1)) ** 3;

export interface GameOpts { seed?: number; onChange?: () => void }

export class Game {
  ctx: CanvasRenderingContext2D;
  model = new BoxModel();
  feed: Feed;
  clock = 0;
  message = ''; messageUntil = 0; flashUntil = 0;
  streak = 0;                       // hits in a row; three sets the rider on fire
  onChange: () => void;

  private skyline = new Skyline(PLAY.w, PLAY.bottom, STREET_BOTTOM);
  private rider = new Rider();
  private sparks = new Sparks();
  private floaters = new Floaters();
  // Everything on screen eases toward where the model says it is, in price
  // terms, so a tick or a detent is a glide and not a jump.
  private anchor = 0;               // eased window open: the camera
  private ridePrice = 0;            // eased spot: the wheel
  private aimPrice = 0;             // eased cursor: the dashed box
  private trail: [number, number][] = [];
  private settled: { r: Result; bell: number }[] = [];
  private ghost: { level: number; half: number; bell: number; since: number } | null = null;
  private aimInAt = -99; private popAt = -99; private shakeAt = -99;
  private wasInside: boolean | null = null;
  private wasFresh = true;
  private lastBell = '';
  private lastSound = 0;

  constructor(public canvas: HTMLCanvasElement, public sfx: Sfx | null, opts: GameOpts = {}) {
    this.ctx = canvas.getContext('2d')!;
    this.feed = new Feed(opts.seed ?? 7);
    this.onChange = opts.onChange ?? (() => {});
  }

  note(t: string, s = 2) { this.message = t; this.messageUntil = this.clock + s; }
  play(n: string) { this.sfx?.play(n); }
  fmt(micro: number) { return usdc(micro); }
  stakeText(micro = this.model.STAKE) { return usdc(micro, 0); }

  /** Calm with nothing down, driving with money live, tense at the bell. */
  bedForNow() {
    const m = this.model;
    if (m.live && m.live.stake) return m.remaining(this.clock) <= 3 ? 'final' : 'live';
    return m.pending ? 'live' : 'idle';
  }

  /* ---- input ---- */
  crank(steps: number) {
    const m = this.model;
    if (m.locked) {
      // The bet is placed: the dial does nothing until the bell.
      if (this.clock - this.lastSound > .25) { this.play('warn'); this.lastSound = this.clock; }
      this.shakeAt = this.clock;
      this.note(`LOCKED / YELLOW ADDS ${this.stakeText()}`, 1.5);
      return;
    }
    const above = m.aim - m.price;
    const did = m.crank(steps);
    if (did && above * (m.aim - m.price) < 0) this.play('crossline');    // passed over spot
    if (did && this.clock - this.lastSound > .04) {
      if (this.sfx && m.reach) this.play(this.sfx.detent(Math.abs(m.aim - m.open) / m.reach));
      this.lastSound = this.clock;
    }
  }

  buy() {
    const m = this.model;
    if (!m.canBuy()) {
      // The device opens its wallet screen here; the web demo just tops up the
      // paper balance so nothing blocks a first play.
      m.balance += 100 * MICRO;
      this.note('+100 DEMO USDC LOADED');
      this.play('coin');
      this.onChange();
      return;
    }
    if (m.buy(this.clock)) {
      // Each stacked press on the same box answers a note higher.
      const presses = Math.min(3, Math.max(1, Math.round(m.pending!.stake / m.STAKE)));
      this.play('buy' + presses);
      this.message = '';
      // The dashed box turns solid where it stands, with a pop.
      this.aimPrice = m.pending!.level;
      this.popAt = this.clock;
      this.sparks.burst(this.xAt(m.windowEnd + m.WINDOW), this.yOf(m.pending!.level), 10,
                        [C_CREAM, C_YELLOW], 110, .45, 3, 0, false, -PX_PER_S);
      this.onChange();
    } else if (!m.fresh(this.clock)) this.note('NO LIVE PRICE / NOT PLACED');
    else if (m.settling) this.note('SETTLING LAST WINDOW');
    else if (m.quiet(this.clock)) this.note('MARKET QUIET / NO BETS');
    else if (!m.measured) this.note('READING THE MARKET...');
    else if (m.refused === 'under') this.note(`UNDER ${m.MIN_MULTIPLE.toFixed(2)}x / NOT SOLD`);
  }

  /* ---- time ---- */
  step(dt: number, now: number) {
    this.clock = now;
    const m = this.model, rounds = m.rounds, windows = m.windows;
    for (const t of this.feed.poll(dt, now)) m.onTick(t, now);
    m.update(now);

    if (m.rounds !== rounds && m.last) {
      const r = m.last;
      if (r.voided) this.play('void');
      else this.play(r.hit ? (r.multiple >= 15 ? 'jackpot' : r.multiple >= 5 ? 'win_big' : 'win_small') : 'miss');
      this.flashUntil = now + 1.6;
      this.onResult(r, m.windowEnd - m.WINDOW);
      this.onChange();
    } else if (m.windows !== windows) {
      // The empty-window heartbeat; a result speaks for the bell instead.
      this.play('bell');
    }
    if (m.windows !== windows) {
      if (!m.live) {
        // Nobody bought the box on its way in: it fades out on its post while a
        // fresh one slides in from the right for the next bell.
        this.ghost = { level: this.aimPrice, half: m.half, bell: m.windowEnd, since: now };
      }
      this.aimInAt = now;
    }

    // Crossing into or out of a live box is the whole tension of a window.
    const inside = m.inside;
    if (inside !== null && this.wasInside !== null && inside !== this.wasInside) this.play(inside ? 'hot' : 'cold');
    this.wasInside = inside;

    // Last seconds: ticks pitched by whether the money is currently winning,
    // and doubling in rate inside the final two so the bell rushes at you.
    const left = m.remaining(now);
    const slot = left > 2 ? 's' + Math.floor(left) : 'h' + Math.floor(left * 2);
    if (inside !== null && left > 0 && left <= 3 && slot !== this.lastBell) this.play(inside ? 'tick_in' : 'tick_out');
    this.lastBell = slot;

    const fresh = m.fresh(now);
    if (this.wasFresh && !fresh) this.play('stale');
    this.wasFresh = fresh;

    this.sfx?.music(this.sfx.enabled ? this.bedForNow() : 'off');
    this.animate(dt);
  }

  /** A box just reached the wheel: make it land. */
  private onResult(r: Result, bell: number) {
    this.settled.push({ r, bell });
    if (this.settled.length > 4) this.settled.shift();
    const y = this.yOf((r.low + r.high) / 2);
    if (r.voided) { this.floaters.add('VOID', RIDER_X + 64, y - 30, C_MUTED); return; }
    if (r.hit) {
      this.streak++;
      this.sparks.burst(RIDER_X, y, 20, [C_YELLOW, C_YELLOW, C_CREAM], 180, 1.1, 5, 320, true, -PX_PER_S);
      this.floaters.add(`+${usdc(r.payout)}`, RIDER_X + 64, y - 36, C_MINT, 20);
      if (this.streak >= 3) {
        // Low over the city, clear of the rider, the boxes and their tags.
        this.floaters.add(this.streak === 3 ? 'HAT TRICK!' : `${this.streak} IN A ROW!`,
                          300, BAND_BOTTOM - 30, C_YELLOW, 28, 2.2, 10);
        const [bx, by] = this.rider.back(RIDER_X, this.riderY());
        this.sparks.burst(bx, by, 26, [C_YELLOW, FLAME, C_RED], 150, .6, 5, -60);
        this.play('hattrick');
      }
      this.rider.react(r.multiple >= 5 ? 'flip' : this.streak === 3 ? 'cheer' : 'hop');
      return;
    }
    if (this.streak >= 3) {
      const [bx, by] = this.rider.back(RIDER_X, this.riderY());
      this.sparks.burst(bx, by, 16, [[96, 104, 112], [70, 76, 84]], 60, 1, 6, -50);
      this.play('fizzle');
    }
    this.streak = 0;
    this.sparks.burst(RIDER_X, y, 14, [C_RED, [140, 60, 56]], 150, .8, 4, 320, true, -PX_PER_S);
    this.floaters.add('MISS', RIDER_X + 64, y - 34, C_RED, 20);
    this.rider.react('wobble');
  }

  /** Ease the camera, the wheel and the cursor; run the rider and sparks. */
  private animate(dt: number) {
    const m = this.model;
    const ease = (rate: number) => 1 - Math.exp(-rate * dt);
    if (m.started) {
      if (!this.anchor) { this.anchor = m.open; this.ridePrice = m.price; this.aimPrice = m.aim; }
      // The camera anchors on the window's open — it just glides there at the
      // bell instead of snapping.
      this.anchor += (m.open - this.anchor) * ease(5);
      this.ridePrice += (m.price - this.ridePrice) * ease(12);
      this.aimPrice += (m.aim - this.aimPrice) * ease(24);
      this.trail.push([this.clock, this.ridePrice]);
      while (this.trail.length > 2 && this.clock - this.trail[0][0] > .6) this.trail.shift();
    }
    let slope = 0;
    if (this.trail.length > 1 && m.view > 0) {
      const [t0, p0] = this.trail[0];
      const rise = ((this.ridePrice - p0) / m.view) * HALF_PX;
      slope = (Math.atan2(rise, Math.max(4, (this.clock - t0) * PX_PER_S)) * 180) / Math.PI;
    }
    this.rider.update(dt, slope, this.streak >= 3);
    if (this.streak >= 3) {
      const [bx, by] = this.rider.back(RIDER_X, this.riderY());
      this.sparks.flame(bx, by, -PX_PER_S);
    }
    this.sparks.update(dt);
    this.floaters.update(dt);
  }

  /* ---- drawing ---- */
  /** Price to screen, anchored on the window's opening price. */
  private yOf(price: number) {
    const m = this.model;
    if (m.view <= 0) return MID_Y;
    return MID_Y - ((price - (this.anchor || m.open)) / m.view) * HALF_PX;
  }
  /** Time to screen: the rider is now, a bell is a post ahead of him. */
  private xAt(t: number) { return RIDER_X + (t - this.clock) * PX_PER_S; }
  private riderY() {
    if (!this.model.started) return PLAY.bottom - 1;      // parked on the street
    return clamp(this.yOf(this.ridePrice), BAND_TOP + 2, BAND_BOTTOM);
  }
  private spin() { return (this.clock * PX_PER_S) / Rider.WHEEL; }

  /** A label with a drop shadow, so it reads over the city. */
  private say(words: string, x: number, y: number, size = 16, color = PAL.CREAM, center = false) {
    const c = this.ctx;
    c.font = font(size);
    c.textAlign = center ? 'center' : 'left';
    c.textBaseline = 'top';
    c.fillStyle = '#000';
    c.fillText(words, Math.round(x) + 1, Math.round(y) + 1);
    c.fillStyle = color;
    c.fillText(words, Math.round(x), Math.round(y));
    c.textAlign = 'left';
  }
  private sayRight(words: string, right: number, y: number, size: number, color: string) {
    this.ctx.font = font(size);
    this.say(words, right - this.ctx.measureText(words).width, y, size, color);
  }
  private fillRect(x: number, y: number, w: number, h: number, color: string) {
    this.ctx.fillStyle = color; this.ctx.fillRect(x, y, w, h);
  }

  draw() {
    const c = this.ctx, m = this.model;
    this.skyline.draw(c, this.clock * PX_PER_S, this.clock);
    if (!m.started) {
      this.rider.draw(c, RIDER_X, this.riderY(), this.spin());
      this.say('WAITING FOR THE', 280, 96, 22, PAL.YELLOW, true);
      this.say('FIRST PRICE...', 280, 128, 22, PAL.YELLOW, true);
      this.footer('< HOME', `BUY ${this.stakeText()} >`);
      return;
    }
    this.drawWorld();
    this.drawHud();
    this.drawStatus();
    this.footer('< HOME', m.canBuy() ? `BUY ${this.stakeText()} >` : 'LOAD >');
  }

  private drawHud() {
    const m = this.model;
    const price = `$${m.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    this.say(price, 10, 6, 20, PAL.CREAM);
    this.ctx.font = font(20);
    const w = this.ctx.measureText(price).width;
    const mv = (m.move >= 0 ? '+' : '') + m.move.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    this.say(mv, 22 + w, 10, 16, m.move >= 0 ? PAL.MINT : PAL.RED);
    this.sayRight(`${usdc(m.balance)} DEMO`, 470, 10, 15, PAL.MINT);
  }

  private drawWorld() {
    const c = this.ctx, m = this.model;
    const openY = Math.round(this.yOf(m.open));
    c.fillStyle = OPEN_LINE;
    for (let x = 0; x < PLAY.right; x += 10) c.fillRect(x, openY, 5, 1);
    this.say('OPEN', 4, openY + 3, 12, PAL.MUTED);

    // Bell posts, one per window, riding in toward the wheel.
    for (const k of [-1, 0, 1]) {
      const bx = Math.round(this.xAt(m.windowEnd + k * m.WINDOW));
      if (bx < -2 || bx > PLAY.right + 2) continue;
      c.fillStyle = k === 0 ? POST_NOW : rgb(POST);
      for (let y = PLAY.top + 26; y < PLAY.bottom; y += 8) c.fillRect(bx, y, 1, 3);
    }
    const bellX = this.xAt(m.windowEnd);
    if (m.settling) this.say('SETTLING', Math.max(40, bellX), PLAY.top + 5, 14, PAL.RED, true);
    else {
      const left = m.remaining(this.clock);
      this.say(String(Math.floor(left)).padStart(2, '0') + 's', bellX, PLAY.top + 2, 20,
               left <= 3 ? PAL.RED : PAL.YELLOW, true);
    }

    this.drawSettled();
    this.drawBets();
    this.drawTrace();
    this.sparks.draw(c);
    const rideY = this.riderY();
    if (rideY !== this.yOf(this.ridePrice)) this.say('OFF SCALE', RIDER_X + 18, rideY - 16, 12, PAL.YELLOW);
    this.rider.draw(c, RIDER_X, rideY, this.spin());
    this.floaters.draw(c, font);
  }

  private drawTrace() {
    const c = this.ctx, m = this.model, rideY = this.riderY();
    // History holds a minute of ticks for the volatility estimate; only the few
    // seconds behind the rider are drawn, so walk back and stop there.
    const points: [number, number][] = [];
    for (let i = m.history.length - 1; i >= 0; i--) {
      const x = this.xAt(m.history[i].t);
      // The wheel is eased; the last raw tick would put a jag under it.
      if (x < RIDER_X - 3) points.push([x, this.yOf(m.history[i].price)]);
      if (x < -4) break;
    }
    points.reverse();
    points.push([RIDER_X, rideY]);
    c.save();
    c.beginPath(); c.rect(PLAY.left, PLAY.top, PLAY.w, PLAY.h); c.clip();
    if (points.length > 1) {
      c.beginPath();
      c.moveTo(points[0][0], points[0][1]);
      for (const [x, y] of points.slice(1)) c.lineTo(x, y);
      c.lineTo(RIDER_X, PLAY.bottom);
      c.lineTo(points[0][0], PLAY.bottom);
      c.closePath();
      c.fillStyle = SHADE; c.fill();
      c.lineJoin = 'round'; c.lineCap = 'round';
      c.beginPath();
      c.moveTo(points[0][0], points[0][1]);
      for (const [x, y] of points.slice(1)) c.lineTo(x, y);
      c.strokeStyle = GLOW; c.lineWidth = 6; c.stroke();
      c.strokeStyle = PAL.CREAM; c.lineWidth = 2; c.stroke();
    }
    // Where the price is now, carried forward to read against the boxes.
    c.fillStyle = 'rgb(150,146,128)';
    for (let x = RIDER_X + 16; x < PLAY.right; x += 8) c.fillRect(x, Math.round(rideY), 3, 1);
    c.restore();
  }

  private boxRect(x: number, low: number, high: number) {
    const top = clamp(Math.round(this.yOf(high)), BAND_TOP, BAND_BOTTOM - 8);
    const bottom = clamp(Math.round(this.yOf(low)), top + 8, BAND_BOTTOM);
    return { x: Math.round(x - BOX_W / 2), y: top, w: BOX_W, h: bottom - top };
  }

  private drawBox(x: number, low: number, high: number, color: string, alpha = .19,
                  dashed = false, grow = 0, width = 3) {
    const c = this.ctx;
    const r = this.boxRect(x, low, high);
    r.x -= grow / 2; r.y -= grow / 2; r.w += grow; r.h += grow;
    if (alpha > 0) {
      c.globalAlpha = alpha; c.fillStyle = color; c.fillRect(r.x, r.y, r.w, r.h); c.globalAlpha = 1;
    }
    c.strokeStyle = color;
    if (dashed) {
      c.setLineDash([6, 6]); c.lineWidth = 2;
      c.strokeRect(r.x + 1, r.y + 1, r.w - 2, r.h - 2);
      c.setLineDash([]);
    } else {
      c.lineWidth = width;
      c.beginPath();
      c.roundRect(r.x + width / 2, r.y + width / 2, r.w - width, r.h - width, 3);
      c.stroke();
    }
    // Past the edge of the visible band: say so rather than lie about it.
    const cx = r.x + r.w / 2;
    c.fillStyle = color;
    if (this.yOf(high) < BAND_TOP) {
      c.beginPath(); c.moveTo(cx, r.y + 4); c.lineTo(cx - 6, r.y + 12); c.lineTo(cx + 6, r.y + 12); c.fill();
    }
    if (this.yOf(low) > BAND_BOTTOM) {
      const b = r.y + r.h;
      c.beginPath(); c.moveTo(cx, b - 4); c.lineTo(cx - 6, b - 12); c.lineTo(cx + 6, b - 12); c.fill();
    }
    return r;
  }

  private boxTag(r: { x: number; y: number; w: number; h: number }, text: string, color: string) {
    const y = r.y - 17 >= PLAY.top + 22 ? r.y - 17 : r.y + r.h + 3;
    this.say(text, r.x + r.w / 2, y, 14, color, true);
  }

  private drawBets() {
    const m = this.model, now = this.clock;
    if (m.live && m.live.stake) {
      const left = m.remaining(now);
      const urgent = left <= 3 && Math.floor(now * 6) % 2 === 0;
      const r = this.drawBox(this.xAt(m.windowEnd), m.live.low, m.live.high, PAL.YELLOW,
                             m.inside ? .38 : .16, false, 0, urgent ? 4 : 3);
      this.boxTag(r, `${this.stakeText(m.live.stake)} @ ${m.live.multiple.toFixed(1)}x`, PAL.YELLOW);
    }

    if (this.ghost) {
      const fade = (now - this.ghost.since) / .45;
      if (fade < 1) {
        this.drawBox(this.xAt(this.ghost.bell), this.ghost.level - this.ghost.half,
                     this.ghost.level + this.ghost.half, rgb(mix(C_YELLOW, POST, fade)), 0, true);
      } else this.ghost = null;
    }

    let nextX = this.xAt(m.windowEnd + m.WINDOW);
    if (m.locked && m.pending) {
      const p = (now - this.popAt) / .25;
      const grow = p < 1 ? Math.round(10 * (1 - p)) : 0;
      const t = now - this.shakeAt;
      if (t < .3) nextX += 4 * Math.sin(t * 60) * (1 - t / .3);
      const r = this.drawBox(nextX, m.pending.low, m.pending.high, PAL.CREAM, .19, false, grow);
      this.boxTag(r, `${this.stakeText(m.pending.stake)} @ ${m.pending.multiple.toFixed(1)}x`, PAL.CREAM);
    } else {
      // A fresh cursor slides in from the right edge after each bell.
      nextX += 60 * (1 - easeOut((now - this.aimInAt) / .45));
      const half = m.half;
      const r = this.drawBox(nextX, this.aimPrice - half, this.aimPrice + half, PAL.YELLOW, .07, true);
      if (m.quiet(now) || !m.measured) {
        // No quote on offer: a flat line is not a 2x bet.
        this.boxTag(r, m.quiet(now) ? 'QUIET' : '...', PAL.MUTED);
      } else {
        const quote = m.quote(m.aim, now);
        this.boxTag(r, `${quote.toFixed(1)}x`, quote >= m.MIN_MULTIPLE ? PAL.YELLOW : PAL.MUTED);
      }
    }
  }

  /** Boxes that already rang stay in the world and scroll away behind him. */
  private drawSettled() {
    const c = this.ctx;
    for (const { r, bell } of this.settled) {
      const x = this.xAt(bell);
      if (x < -BOX_W) continue;
      const base = r.voided ? C_MUTED : r.hit ? C_MINT : C_RED;
      const fade = clamp((this.clock - bell) / 7, 0, 1);
      const color = rgb(mix(base, POST, fade));
      this.drawBox(x, r.low, r.high, color, .27 * (1 - fade));
      // Where the price actually landed, so a miss shows by how much.
      c.fillStyle = color;
      c.beginPath(); c.arc(Math.round(x), Math.round(this.yOf(r.price)), 3, 0, 7); c.fill();
    }
  }

  /** The one line of words at the bottom, as text and colour. */
  status(): [string, string] {
    const m = this.model, r = m.last;
    if (this.clock < this.messageUntil) return [this.message, PAL.MINT];
    if (r && this.clock < this.flashUntil + 3) {
      if (r.voided) return [`VOID / ${this.stakeText(r.stake)} BACK`, PAL.MUTED];
      if (r.hit) return [`HIT / PAID ${usdc(r.payout)}`, PAL.MINT];
      return [`MISS / -${this.stakeText(r.stake)}`, PAL.RED];
    }
    if (m.live && m.live.stake) return [`${this.stakeText(m.live.stake)} IN / PAYS ${usdc(Math.floor(m.live.payout))}`, PAL.YELLOW];
    if (m.pending) return [`PLACED / YELLOW ADDS ${this.stakeText()}`, PAL.CREAM];
    if (m.quiet(this.clock)) return ['MARKET QUIET / NO BETS', PAL.MUTED];
    if (!m.measured) return ['READING THE MARKET...', PAL.MUTED];
    return [`CRANK / YELLOW BUYS ${m.WINDOW}s`, PAL.MUTED];
  }

  private drawStatus() {
    const m = this.model;
    const [text, color] = this.status();
    this.say(text.slice(0, 27), 10, PLAY.bottom + 6, 16, color);
    if (this.streak >= 2) {
      this.sayRight(`STREAK ${this.streak}`, 470, PLAY.bottom + 7, 15,
                    this.streak >= 3 ? 'rgb(255,138,40)' : PAL.YELLOW);
    } else if (m.rounds) {
      this.sayRight(`HITS ${m.hits}/${m.rounds}`, 470, PLAY.bottom + 7, 15, PAL.MUTED);
    }
  }

  private footer(back: string, go: string) {
    const c = this.ctx;
    this.fillRect(0, STREET_BOTTOM, 480, 46, PAL.PANEL);
    c.fillStyle = PAL.RED; c.beginPath(); c.arc(20, 297, 6, 0, 7); c.fill();
    c.fillStyle = PAL.YELLOW; c.beginPath(); c.arc(254, 297, 6, 0, 7); c.fill();
    c.font = font(16); c.textBaseline = 'top'; c.fillStyle = PAL.CREAM;
    c.fillText(back, 34, 286);
    c.fillText(go, 268, 286);
  }
}

/** Attract mode: a player for the screen on the 3D model. */
export class Attract {
  private target = 0; private next = 0; private bought = 0; private window = -1;
  constructor(private g: Game) {}
  step(now: number) {
    const g = this.g, m = g.model;
    if (!m.started) return;
    if (m.windows !== this.window) {
      this.window = m.windows;
      this.target = Math.round((g.feed.rand() - .5) * 14);
      this.bought = g.feed.rand() < .35 ? 2 : 1;
      this.next = now + .4;
    }
    if (now < this.next) return;
    const want = m.open + this.target * m.step;
    if (!m.locked && Math.abs(m.aim - want) > m.step * .6) {
      g.crank(Math.sign(want - m.aim));
      this.next = now + .07;
      return;
    }
    const left = m.remaining(now);
    if (this.bought > 0 && left > 1.2 && left < 8.5 && m.measured && !m.quiet(now)) {
      if (!m.canBuy()) m.balance += 100 * MICRO;
      g.buy();
      this.bought--;
      this.next = now + .5;
    }
  }
}
