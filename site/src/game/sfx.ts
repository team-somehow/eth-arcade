/**
 * Square-wave arcade audio — the same cue set and the same three chiptune
 * beds the device synthesizes at boot, here on WebAudio.
 */
type Seg = [number, number, number]; // start hz, end hz, seconds
type Bed = [Array<number | null>, 'sq' | 'noise', number][];

const CLIPS: Record<string, Seg[]> = {
  bell: [[880, 880, .035], [1320, 1320, .085]],
  hot: [[600, 1020, .07]],
  cold: [[1020, 520, .09]],
  tick_in: [[920, 920, .035]],
  tick_out: [[400, 400, .05]],
  buy1: [[520, 780, .05]],
  buy2: [[660, 990, .05]],
  buy3: [[780, 1170, .06]],
  win_small: [[523, 523, .08], [659, 659, .08], [784, 784, .14]],
  win_big: [[523, 523, .06], [659, 659, .06], [784, 784, .06], [1047, 1047, .06], [1319, 1319, .22]],
  jackpot: [[523, 523, .05], [784, 784, .05], [1047, 1047, .05], [1319, 1319, .05], [1568, 1568, .05], [2093, 2093, .28]],
  // Third hit in a row: the rider catches fire.
  hattrick: [[392, 392, .06], [523, 523, .06], [659, 659, .06], [784, 1568, .32]],
  fizzle: [[900, 180, .3]],            // the streak ends
  miss: [[330, 330, .12], [247, 247, .12], [165, 165, .2]],
  void: [[200, 160, .18]],
  warn: [[240, 200, .06], [240, 200, .06]],
  stale: [[520, 300, .16]],
  crossline: [[1500, 1500, .012]],     // the box passing over spot
  nav: [[440, 440, .02]],
  back: [[588, 392, .09]],
  coin: [[988, 988, .04], [1319, 1319, .1]],
  enter: [[392, 588, .07], [784, 784, .1]],
};

const A2 = 110, C3 = 130.81, E3 = 164.81, G3 = 196, A4 = 440, C5 = 523.25, E5 = 659.25, G5 = 784, A5 = 880, N = null;
const BEDS: Record<string, Bed> = {
  idle: [
    [[A2, N, N, N, E3, N, N, N, A2, N, N, N, G3, N, N, N], 'sq', .45],
    [[A4, N, N, N, C5, N, N, N, E5, N, N, N, C5, N, N, N], 'sq', .3],
  ],
  live: [
    [[A2, N, A2, N, E3, N, E3, N, A2, N, A2, N, G3, N, G3, E3], 'sq', .5],
    [[A4, C5, E5, A5, E5, C5, A4, C5, E5, A5, C5, E5, A4, C5, E5, A5], 'sq', .3],
    [Array.from({ length: 16 }, (_, i) => (i % 2 ? null : 1)), 'noise', .18],
  ],
  final: [
    [[A2, N, A2, N, E3, N, E3, N, A2, N, A2, N, G3, N, G3, E3], 'sq', .55],
    [[A5, G5, E5, G5, A5, G5, E5, C5, A5, G5, E5, G5, A5, E5, C5, A4], 'sq', .34],
    [Array(16).fill(1), 'noise', .22],
  ],
};
void C3;

export class Sfx {
  ctx: AudioContext | null = null;
  master: GainNode | null = null;
  enabled = false;
  mode = 'off';
  private beat: number | null = null;
  private stepIdx = 0;
  private nextAt = 0;
  private noise: AudioBuffer | null = null;

  enable() {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.master = this.ctx.createGain();
      this.master.gain.value = .5;
      this.master.connect(this.ctx.destination);
    }
    if (this.ctx.state === 'suspended') void this.ctx.resume();
    this.enabled = true;
  }

  disable() {
    this.enabled = false;
    this.music('off');
  }

  private tone(segments: Seg[], level = .18) {
    if (!this.enabled || !this.ctx || !this.master) return;
    const c = this.ctx, o = c.createOscillator(), g = c.createGain();
    o.type = 'square';
    let t = c.currentTime + .005;
    o.frequency.setValueAtTime(segments[0][0], t);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(level, t + .004);
    for (const [f0, f1, d] of segments) {
      o.frequency.setValueAtTime(f0, t);
      o.frequency.linearRampToValueAtTime(f1, t + d);
      t += d;
    }
    g.gain.setValueAtTime(level, t - .02);
    g.gain.linearRampToValueAtTime(0, t);
    o.connect(g).connect(this.master);
    o.start();
    o.stop(t + .01);
  }

  play(name: string) {
    const clip = CLIPS[name];
    if (clip) return this.tone(clip);
    if (name.startsWith('detent')) {
      const hz = 300 * Math.pow(1.13, Number(name.slice(6)));
      this.tone([[hz, hz, .018]], .14);
    }
  }

  /** Clip name for a crank click at `fraction` of full reach — the pitch rises toward the risky end. */
  detent(fraction: number) {
    return 'detent' + Math.round(Math.max(0, Math.min(1, fraction)) * 7);
  }

  music(mode: string) {
    if (mode === this.mode) return;
    this.mode = mode;
    if (this.beat !== null) { clearInterval(this.beat); this.beat = null; }
    if (mode === 'off' || !this.enabled || !this.ctx) return;
    this.stepIdx = 0;
    this.nextAt = this.ctx.currentTime + .05;
    this.beat = window.setInterval(() => this.schedule(), 60);
  }

  private schedule() {
    if (!this.enabled || !this.ctx) return;
    const bed = BEDS[this.mode];
    if (!bed) return;
    while (this.nextAt < this.ctx.currentTime + .18) {
      const s = this.stepIdx % 16;
      for (const [seq, wave, lvl] of bed) {
        const hz = seq[s];
        if (hz == null) continue;
        if (wave === 'noise') this.hat(this.nextAt, lvl); else this.note(hz, this.nextAt, .11, lvl);
      }
      this.nextAt += .125;
      this.stepIdx++;
    }
  }

  private note(hz: number, t: number, dur: number, lvl: number) {
    const c = this.ctx!, o = c.createOscillator(), g = c.createGain();
    o.type = 'square';
    o.frequency.value = hz;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(lvl * .22, t + .004);
    g.gain.exponentialRampToValueAtTime(.0008, t + dur);
    o.connect(g).connect(this.master!);
    o.start(t);
    o.stop(t + dur + .02);
  }

  private hat(t: number, lvl: number) {
    const c = this.ctx!;
    if (!this.noise) {
      const b = c.createBuffer(1, c.sampleRate * .1, c.sampleRate), d = b.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      this.noise = b;
    }
    const s = c.createBufferSource(), g = c.createGain();
    s.buffer = this.noise;
    g.gain.setValueAtTime(lvl * .12, t);
    g.gain.exponentialRampToValueAtTime(.0008, t + .06);
    s.connect(g).connect(this.master!);
    s.start(t);
    s.stop(t + .07);
  }
}

/** One instance for the page: browsers allow one AudioContext per gesture, and the demo owns it. */
export const sfx = new Sfx();
