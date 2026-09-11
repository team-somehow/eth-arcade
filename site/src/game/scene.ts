/**
 * BOX RUN scenery — a night city, a one-wheel rider and the bits that fly off.
 * Ported from firmware/games/box_scene.py: everything is drawn in code, no
 * image assets. Nothing here knows about money or prices; engine.ts says where
 * things are and what happened.
 */

export type RGB = [number, number, number];

const SKY_TOP: RGB = [5, 10, 22];
const SKY_LOW: RGB = [24, 40, 66];
const FAR: RGB = [17, 31, 49];
const NEAR: RGB = [11, 21, 34];
const STREET: RGB = [8, 14, 22];
const KERB: RGB = [38, 56, 70];
const LANE: RGB = [52, 68, 80];
const WARM: RGB = [150, 122, 58];
const COOL: RGB = [66, 116, 138];
const DIM: RGB = [62, 64, 54];
export const FLAME: RGB = [255, 138, 40];

const TYRE: RGB = [30, 32, 38];
const RIM: RGB = [86, 96, 106];
const HUB: RGB = [176, 184, 190];
const STEEL: RGB = [160, 168, 176];
const GRIP: RGB = [38, 42, 48];
const PANTS: RGB = [84, 130, 196];
const SHIRT: RGB = [214, 74, 68];
const SHIRT_FAR: RGB = [160, 52, 50];
const SKIN: RGB = [240, 196, 158];
const HAIR: RGB = [112, 72, 44];
const SHOE: RGB = [24, 26, 30];

export const CREAM: RGB = [244, 236, 210];
export const YELLOW: RGB = [255, 204, 72];
export const RED: RGB = [233, 100, 91];

export const rgb = (c: RGB, a = 1) => (a >= 1 ? `rgb(${c[0]},${c[1]},${c[2]})` : `rgba(${c[0]},${c[1]},${c[2]},${a})`);
export const mix = (a: RGB, b: RGB, f: number): RGB =>
  [Math.round(a[0] + (b[0] - a[0]) * f), Math.round(a[1] + (b[1] - a[1]) * f), Math.round(a[2] + (b[2] - a[2]) * f)];

/** Deterministic scenery: the same city every load, like the device's seeded Random. */
function rng(seed: number) {
  let s = (seed >>> 0) || 1;
  return () => {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
const pick = <T,>(r: () => number, xs: readonly T[]) => xs[Math.floor(r() * xs.length) % xs.length];

function surface(w: number, h: number) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return { c, x: c.getContext('2d')! };
}

function rotatePoint(dx: number, dy: number, degrees: number): [number, number] {
  // Where (dx, dy) lands after a counter-clockwise rotation of `degrees`.
  const r = (degrees * Math.PI) / 180;
  return [dx * Math.cos(r) + dy * Math.sin(r), -dx * Math.sin(r) + dy * Math.cos(r)];
}

/** Sky, two parallax rows of buildings and a street, rendered once at boot. */
export class Skyline {
  private sky: HTMLCanvasElement;
  private stars: [number, number, number][] = [];
  private layers: { art: HTMLCanvasElement; speed: number; blinkers: [number, number, RGB][] }[] = [];

  constructor(private width: number, private horizon: number, private streetBottom: number, seed = 7) {
    const r = rng(seed);
    const { c, x } = surface(width, horizon);
    for (let y = 0; y < horizon; y++) {
      x.fillStyle = rgb(mix(SKY_TOP, SKY_LOW, y / Math.max(1, horizon - 1)));
      x.fillRect(0, y, width, 1);
    }
    for (let i = 0; i < 50; i++) {
      const sx = Math.floor(r() * width), sy = Math.floor(r() * (horizon / 2)), b = r();
      this.stars.push([sx, sy, b]);
      x.fillStyle = rgb(mix(SKY_TOP, CREAM, .25 + .5 * b));
      x.fillRect(sx, sy, 1, 1);
    }
    // A moon, with a crescent bitten out of it by the sky behind.
    x.fillStyle = 'rgb(226,220,196)';
    x.beginPath(); x.arc(400, 64, 13, 0, 7); x.fill();
    x.fillStyle = rgb(mix(SKY_TOP, SKY_LOW, 59 / horizon));
    x.beginPath(); x.arc(394, 60, 12, 0, 7); x.fill();
    this.sky = c;
    this.layers = [this.row(r, FAR, 60, 136, DIM, DIM, .12, .2),
                   this.row(r, NEAR, 30, 96, WARM, COOL, .3, .45)];
  }

  private row(r: () => number, color: RGB, low: number, high: number, warm: RGB, cool: RGB,
              lit: number, speed: number) {
    const { c, x } = surface(this.width, this.horizon);
    const blinkers: [number, number, RGB][] = [];
    let bx = 0;
    while (bx < this.width) {
      const w = 18 + Math.floor(r() * 29), h = low + Math.floor(r() * (high - low + 1));
      const top = this.horizon - h;
      for (const ox of [bx, bx - this.width]) {
        x.fillStyle = rgb(color);
        x.fillRect(ox, top, w, h);
        if (r() < .3) x.fillRect(ox + Math.floor(w / 2), top - 8, 1, 8);   // antenna
      }
      const wr = rng(bx * 31 + low);                // the same windows on both copies
      for (let wx = bx + 4; wx < bx + w - 3; wx += 5) {
        for (let wy = this.horizon - h + 5; wy < this.horizon - 4; wy += 7) {
          const roll = wr();
          if (roll < lit) {
            x.fillStyle = rgb(roll < lit * .7 ? warm : cool);
            for (const ox of [0, -this.width]) x.fillRect(wx + ox, wy, 2, 3);
          } else if (roll > .985) blinkers.push([wx, wy, warm]);
        }
      }
      bx += w + Math.floor(r() * 7);
    }
    return { art: c, speed, blinkers };
  }

  /** `travel` is how far the world has scrolled, in pixels. */
  draw(x: CanvasRenderingContext2D, travel: number, clock: number) {
    x.drawImage(this.sky, 0, 0);
    x.fillStyle = rgb(CREAM);
    this.stars.slice(0, 12).forEach(([sx, sy, b], i) => {
      if (Math.sin(clock * (1.5 + b) + i) > .7) x.fillRect(sx, sy, 1, 1);
    });
    for (const { art, speed, blinkers } of this.layers) {
      const off = Math.floor(travel * speed) % this.width;
      x.drawImage(art, -off, 0);
      x.drawImage(art, this.width - off, 0);
      blinkers.forEach(([bx, by, tone], i) => {
        if (Math.floor(clock * .7 + i * 1.7) % 3 === 0) {
          x.fillStyle = rgb(tone);
          x.fillRect((((bx - off) % this.width) + this.width) % this.width, by, 2, 3);
        }
      });
    }
    x.fillStyle = rgb(STREET);
    x.fillRect(0, this.horizon, this.width, this.streetBottom - this.horizon);
    x.fillStyle = rgb(KERB);
    x.fillRect(0, this.horizon - 1, this.width, 2);
    // The street is nearer than the price line, so it runs faster than it.
    const laneY = this.streetBottom - 5;
    x.fillStyle = rgb(LANE);
    for (let lx = (-Math.floor(travel * 1.6) % 32) - 32; lx < this.width; lx += 32) x.fillRect(lx, laneY, 14, 2);
  }
}

type Move = { kind: keyof typeof MOVES; t: number };
const MOVES = { hop: .7, flip: .9, wobble: 1.4, cheer: 2.2 };

/**
 * A kid in a cap on a one-wheeler. The rider balances on a single wheel because
 * the price line is jagged: legs or a two-wheeled base need flat ground and
 * would visibly clip into the line; one wheel touches it at exactly one point.
 */
export class Rider {
  static WHEEL = 8;
  tilt = 0;
  age = 0;
  fire = false;
  private move: Move | null = null;

  react(kind: keyof typeof MOVES) { this.move = { kind, t: 0 }; }

  /** `slope` is the line's angle under the wheel, degrees, uphill positive. */
  update(dt: number, slope: number, fire: boolean) {
    this.age += dt;
    if (this.move) {
      this.move.t += dt;
      if (this.move.t >= MOVES[this.move.kind]) this.move = null;
    }
    // Lean into the slope, capped so a spike cannot stand him on his head.
    // On fire he rides leaned back: the one-wheel version of a wheelie.
    const target = Math.max(-22, Math.min(22, slope * .7)) + (fire ? 16 : 0);
    this.tilt += (target - this.tilt) * (1 - Math.exp(-dt * 7));
    this.fire = fire;
  }

  /** (lift px, extra rotation, pivot height above the hub, arms). */
  private pose(): [number, number, number, 'bars' | 'up' | 'flail'] {
    const balance = 2.4 * Math.sin(this.age * 2.3);      // never quite still
    if (!this.move) return [0, balance, 0, 'bars'];
    const { kind, t } = this.move;
    const p = t / MOVES[kind];
    if (kind === 'hop') return [22 * 4 * p * (1 - p), balance, 0, 'up'];
    if (kind === 'flip') return [38 * 4 * p * (1 - p), 360 * (3 * p * p - 2 * p * p * p), 22, 'up'];
    if (kind === 'cheer') {
      const q = Math.min(1, p * 2.5);
      return [30 * 4 * q * (1 - q), balance, 0, 'up'];
    }
    // wobble: nearly thrown off, arms windmilling, settling back down
    return [0, 18 * Math.sin(t * 17) * Math.exp(-2.6 * t), 0, 'flail'];
  }

  /** Hub position and total rotation for a wheel resting on (x, y). */
  placement(x: number, y: number): [number, number, number] {
    const [lift, extra, pivot] = this.pose();
    const angle = this.tilt + extra;
    if (!pivot) return [x, y - Rider.WHEEL - lift, angle];
    // Spin about the body, not the axle, or the flip swings him under the wheel.
    const [px, py] = rotatePoint(0, pivot, angle);
    return [x + px, y - Rider.WHEEL - lift - pivot + py, angle];
  }

  /** The jetpack nozzle in screen space, for the flames. */
  back(x: number, y: number): [number, number] {
    const [hx, hy, angle] = this.placement(x, y);
    const [dx, dy] = rotatePoint(-9, -24, angle);
    return [hx + dx, hy + dy];
  }

  draw(c: CanvasRenderingContext2D, x: number, y: number, spin: number) {
    const [, , , arms] = this.pose();
    const [hubX, hubY, angle] = this.placement(x, y);
    c.save();
    c.translate(Math.round(hubX), Math.round(hubY));
    c.rotate((-angle * Math.PI) / 180);
    c.lineCap = 'round';

    const line = (x0: number, y0: number, x1: number, y1: number, color: RGB, w: number) => {
      c.strokeStyle = rgb(color); c.lineWidth = w;
      c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke();
    };
    const dot = (dx: number, dy: number, r: number, color: RGB) => {
      c.fillStyle = rgb(color); c.beginPath(); c.arc(dx, dy, r, 0, 7); c.fill();
    };
    const box = (dx: number, dy: number, w: number, h: number, color: RGB) => {
      c.fillStyle = rgb(color); c.fillRect(dx, dy, w, h);
    };

    // Wheel: tyre, rim, a hub and spokes that turn with the scroll.
    const r = Rider.WHEEL;
    dot(0, 0, r, TYRE);
    c.strokeStyle = rgb(RIM); c.lineWidth = 2; c.beginPath(); c.arc(0, 0, r - 1, 0, 7); c.stroke();
    for (let k = 0; k < 2; k++) {
      const a = spin + (k * Math.PI) / 2;
      line(-Math.cos(a) * 5, -Math.sin(a) * 5, Math.cos(a) * 5, Math.sin(a) * 5, [120, 130, 138], 1);
    }
    dot(0, 0, 2, HUB);
    c.strokeStyle = 'rgb(110,122,132)'; c.lineWidth = 2;
    c.beginPath(); c.arc(0, 0, 11, -(Math.PI - .35), -.35); c.stroke();

    // Deck and steering post.
    line(-8, -11, 8, -11, [96, 106, 116], 3);
    line(4, -11, 9, -33, STEEL, 2);
    line(7, -34, 12, -34, GRIP, 3);

    const shoulder: [number, number] = [3, -35];
    const grip: [number, number] = [9, -33];
    let nearHand: [number, number], farHand: [number, number];
    if (arms === 'up') { nearHand = [7, -52]; farHand = [-3, -51]; }
    else if (arms === 'flail') {
      const a = this.age * 22;
      nearHand = [3 + 9 * Math.cos(a), -35 - 9 * Math.sin(a)];
      farHand = [3 - 9 * Math.cos(a + 1), -35 + 9 * Math.sin(a + 1)];
    } else { nearHand = grip; farHand = grip; }
    line(shoulder[0], shoulder[1], farHand[0], farHand[1], SHIRT_FAR, 3);

    if (this.fire) {
      box(-9, -37, 5, 12, [126, 134, 142]);
      box(-10, -26, 6, 3, [70, 76, 84]);
    }

    // Legs, shoes, body.
    line(-3, -12, -1, -25, PANTS, 4);
    line(2, -12, 1, -25, PANTS, 4);
    box(-6, -14, 5, 3, SHOE);
    box(1, -14, 5, 3, SHOE);
    line(0, -24, 2, -36, SHIRT, 7);
    line(shoulder[0], shoulder[1], nearHand[0], nearHand[1], SHIRT, 3);
    dot(nearHand[0], nearHand[1], 2, GRIP);

    // Head: face, big nose, a tuft of hair and a red cap with a brim.
    dot(4, -43, 5, SKIN);
    dot(9, -42, 2, SKIN);
    line(-1, -44, 0, -39, HAIR, 2);
    box(6, -44, 1, 1, SHOE);
    c.fillStyle = rgb(SHIRT);
    c.beginPath(); c.arc(4, -45, 5, Math.PI, 2 * Math.PI); c.fill();
    line(6, -45, 12, -45, SHIRT, 2);
    c.restore();
  }
}

type Spark = { x: number; y: number; vx: number; vy: number; age: number; life: number; color: RGB; size: number; g: number; square: boolean };

/** Short-lived particles: coins, shards, flames and smoke. */
export class Sparks {
  items: Spark[] = [];
  private r = rng(5);

  emit(x: number, y: number, vx: number, vy: number, color: RGB, life: number, size: number, g = 0, square = false) {
    this.items.push({ x, y, vx, vy, age: 0, life, color, size, g, square });
  }

  burst(x: number, y: number, count: number, colors: readonly RGB[], speed: number, life: number,
        size: number, g = 320, square = false, drift = 0) {
    for (let i = 0; i < count; i++) {
      const a = this.r() * 2 * Math.PI, v = (.35 + this.r() * .65) * speed;
      this.emit(x, y, Math.cos(a) * v + drift, Math.sin(a) * v - speed * .4,
                pick(this.r, colors), life * (.7 + this.r() * .4), size, g, square);
    }
  }

  flame(x: number, y: number, drift: number) {
    for (let i = 0; i < 2; i++) {
      this.emit(x, y + (this.r() * 4 - 2), -(70 + this.r() * 50) + drift, this.r() * 32 - 18,
                pick(this.r, [YELLOW, FLAME, FLAME, RED]), .22 + this.r() * .16, 3 + this.r() * 2);
    }
  }

  update(dt: number) {
    for (const p of this.items) { p.x += p.vx * dt; p.y += p.vy * dt; p.vy += p.g * dt; p.age += dt; }
    this.items = this.items.filter((p) => p.age < p.life);
  }

  draw(c: CanvasRenderingContext2D) {
    for (const p of this.items) {
      const left = 1 - p.age / p.life;
      c.fillStyle = rgb(p.color);
      if (p.square) {
        // Coins flicker edge-on as they tumble.
        const w = Math.max(1, Math.round(p.size * Math.abs(Math.cos(p.age * 14))));
        c.fillRect(Math.round(p.x) - (w >> 1), Math.round(p.y), w, Math.round(p.size));
      } else {
        c.beginPath(); c.arc(Math.round(p.x), Math.round(p.y), Math.max(1, Math.round(p.size * left)), 0, 7); c.fill();
      }
    }
  }
}

type Floater = { text: string; x: number; y: number; rise: number; age: number; life: number; color: RGB; size: number };

/** Words that pop up and drift away: payouts, HIT/MISS, HAT TRICK. */
export class Floaters {
  items: Floater[] = [];

  add(text: string, x: number, y: number, color: RGB, size = 18, life = 1.4, rise = 26) {
    this.items.push({ text, x, y, rise, age: 0, life, color, size });
  }

  update(dt: number) {
    for (const f of this.items) { f.y -= f.rise * dt; f.age += dt; }
    this.items = this.items.filter((f) => f.age < f.life);
  }

  draw(c: CanvasRenderingContext2D, font: (size: number) => string) {
    c.textAlign = 'center';
    c.textBaseline = 'middle';
    for (const f of this.items) {
      const fade = Math.min(1, (f.life - f.age) / .4);
      const pop = 1 + .5 * Math.max(0, 1 - f.age / .15);       // lands with a punch
      c.globalAlpha = fade;
      c.font = font(Math.round(f.size * pop));
      c.fillStyle = '#000';
      c.fillText(f.text, Math.round(f.x) + 2, Math.round(f.y) + 2);
      c.fillStyle = rgb(f.color);
      c.fillText(f.text, Math.round(f.x), Math.round(f.y));
    }
    c.globalAlpha = 1;
    c.textAlign = 'left';
    c.textBaseline = 'top';
  }
}
