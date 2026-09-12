/**
 * Painted-on board detail: solder mask, copper pours, silkscreen and pads,
 * drawn to a canvas so the Pi and the display module read as real boards
 * rather than green bricks. One texture per board face, built once.
 */
import * as THREE from 'three';

const px = (mm: number) => mm * 12;            // 12 px per mm

function canvas(wmm: number, hmm: number) {
  const c = document.createElement('canvas');
  c.width = px(wmm); c.height = px(hmm);
  return { c, x: c.getContext('2d')!, W: c.width, H: c.height };
}

function texture(c: HTMLCanvasElement) {
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

/** Board-local mm (origin at the board centre, +y up) to canvas pixels. */
const map = (W: number, H: number) => (x: number, y: number): [number, number] => [W / 2 + px(x), H / 2 - px(y)];

function noise(x: CanvasRenderingContext2D, W: number, H: number, alpha: number) {
  const img = x.getImageData(0, 0, W, H);
  const d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (Math.random() - .5) * alpha;
    d[i] += n; d[i + 1] += n; d[i + 2] += n;
  }
  x.putImageData(img, 0, 0);
}

/** The Raspberry Pi Zero W's top face: 65 x 30 mm. */
export function piTop() {
  const { c, x, W, H } = canvas(65, 30);
  const at = map(W, H);
  x.fillStyle = '#186b37';
  x.fillRect(0, 0, W, H);

  // ground pour: a slightly lighter field with a hatched edge, as on a real board
  x.fillStyle = '#1c7a3e';
  x.fillRect(px(2), px(2), W - px(4), H - px(4));
  x.strokeStyle = 'rgba(255,255,255,.035)';
  x.lineWidth = px(.35);
  for (let i = -H; i < W; i += px(1.6)) {
    x.beginPath(); x.moveTo(i, 0); x.lineTo(i + H, H); x.stroke();
  }

  // routed copper: traces fanning out of the SoC, just visible under the mask
  x.strokeStyle = 'rgba(255,214,130,.10)';
  x.lineWidth = px(.25);
  for (let i = 0; i < 70; i++) {
    const [sx, sy] = at(-5 + (Math.random() - .5) * 14, -3 + (Math.random() - .5) * 12);
    const a = Math.random() * Math.PI * 2, len = px(5 + Math.random() * 16);
    x.beginPath();
    x.moveTo(sx, sy);
    x.lineTo(sx + Math.cos(a) * len * .5, sy + Math.sin(a) * len * .5);
    x.lineTo(sx + Math.cos(a) * len * .5 + Math.sign(Math.cos(a)) * len * .5, sy + Math.sin(a) * len * .5);
    x.stroke();
  }

  const silk = (s: string, mx: number, my: number, size = 2.1, align: CanvasTextAlign = 'left', rot = 0) => {
    const [cx, cy] = at(mx, my);
    x.save();
    x.translate(cx, cy);
    x.rotate(rot);
    x.fillStyle = 'rgba(238,244,240,.82)';
    x.font = `700 ${px(size)}px "Chivo Mono", monospace`;
    x.textAlign = align;
    x.textBaseline = 'middle';
    x.fillText(s, 0, 0);
    x.restore();
  };
  const outline = (mx: number, my: number, w: number, h: number) => {
    const [cx, cy] = at(mx - w / 2, my + h / 2);
    x.strokeStyle = 'rgba(238,244,240,.5)';
    x.lineWidth = px(.3);
    x.strokeRect(cx, cy, px(w), px(h));
  };
  const pad = (mx: number, my: number, w: number, h: number, r = 0) => {
    const [cx, cy] = at(mx - w / 2, my + h / 2);
    x.fillStyle = '#d9b04a';
    if (r) { x.beginPath(); x.roundRect(cx, cy, px(w), px(h), px(r)); x.fill(); }
    else x.fillRect(cx, cy, px(w), px(h));
  };

  // gold pads under the soldered 40-pin header, pin 1 square and called out
  for (let col = 0; col < 20; col++) {
    for (const row of [0, 1]) {
      const mx = -28.7 + col * 2.54, my = row ? 11.5 : 8.96;
      if (col === 0 && row === 0) pad(mx, my, 1.8, 1.8);
      else pad(mx, my, 1.8, 1.8, .85);
    }
  }
  outline(-28.7, 8.96, 3, 3);
  silk('1', -31, 6.6, 1.5, 'center');

  // the wordmark and the legends the Zero actually carries
  silk('Raspberry Pi Zero W', -30, 3, 2.4);
  silk('© 2017', -30, -.2, 1.6);
  silk('RUN', -23.5, 5.6, 1.3);
  silk('TV', -18, 5.6, 1.3);
  silk('SD', -31.5, -7.5, 1.4);
  silk('HDMI', -20.1, -10.6, 1.3, 'center');
  silk('USB', 8.9, -10.6, 1.3, 'center');
  silk('PWR IN', 21.5, -10.6, 1.3, 'center');
  silk('CAMERA', 27.5, -8, 1.2, 'center', -Math.PI / 2);

  // component footprints and the wireless module's antenna keep-out
  outline(-5, -3, 12.4, 12.4);
  outline(23, 1, 10.4, 8.4);
  x.strokeStyle = 'rgba(238,244,240,.35)';
  x.lineWidth = px(.4);
  const [ax, ay] = at(29.6, 10);
  x.strokeRect(ax - px(3.4), ay - px(2), px(6.8), px(7));

  // the two through-hole test pads, and the mounting holes
  for (const [mx, my] of [[-23.5, 3.6], [-18, 3.6]] as [number, number][]) pad(mx, my, 1.6, 1.6, .8);
  for (const [mx, my] of [[-29, -11.5], [29, -11.5], [-29, 11.5], [29, 11.5]] as [number, number][]) {
    const [cx, cy] = at(mx, my);
    x.fillStyle = '#c9c2a8';
    x.beginPath(); x.arc(cx, cy, px(2.6), 0, 7); x.fill();
    x.fillStyle = '#0b0f12';
    x.beginPath(); x.arc(cx, cy, px(1.35), 0, 7); x.fill();
  }

  noise(x, W, H, 13);
  return texture(c);
}

/** The display module's back: 92 x 60 mm of black board with white legends. */
export function panelBack() {
  const { c, x, W, H } = canvas(92, 60);
  const at = map(W, H);
  x.fillStyle = '#14181c';
  x.fillRect(0, 0, W, H);
  x.fillStyle = 'rgba(255,255,255,.03)';
  x.fillRect(px(3), px(3), W - px(6), H - px(6));
  x.fillStyle = 'rgba(233,240,236,.7)';
  x.font = `700 ${px(3)}px "Chivo Mono", monospace`;
  x.textBaseline = 'middle';
  let [tx, ty] = at(-40, 20);
  x.fillText('3.5" IPS  480 x 320', tx, ty);
  x.font = `400 ${px(2.2)}px "Chivo Mono", monospace`;
  [tx, ty] = at(-40, 14.5);
  x.fillText('SPI 48MHz  26-PIN SOCKET', tx, ty);
  [tx, ty] = at(-40, -24);
  x.fillText('TICK  BOX RUN', tx, ty);
  noise(x, W, H, 8);
  return texture(c);
}

/**
 * The printed shell's surface: faint horizontal layer lines, so the case reads
 * as an FDM print rather than moulded plastic. Used as a bump map.
 */
export function layerLines() {
  const c = document.createElement('canvas');
  c.width = 4; c.height = 64;
  const x = c.getContext('2d')!;
  for (let y = 0; y < 64; y++) {
    const v = 128 + Math.sin((y / 64) * Math.PI * 2 * 8) * 20 + (Math.random() - .5) * 4;
    x.fillStyle = `rgb(${v},${v},${v})`;
    x.fillRect(0, y, 4, 1);
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(1, 44);
  return t;
}

/** A soft diagonal sheen for the cover glass. */
export function sheen() {
  const { c, x, W, H } = canvas(92, 60);
  x.fillStyle = '#000';
  x.fillRect(0, 0, W, H);
  const g = x.createLinearGradient(0, H, W * .75, 0);
  g.addColorStop(0, 'rgba(255,255,255,0)');
  g.addColorStop(.44, 'rgba(255,255,255,0)');
  g.addColorStop(.5, 'rgba(190,225,255,.30)');
  g.addColorStop(.56, 'rgba(255,255,255,0)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g;
  x.fillRect(0, 0, W, H);
  return texture(c);
}
