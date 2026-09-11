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

/** The Raspberry Pi 5's top face: 85 x 56 mm. */
export function piTop() {
  const { c, x, W, H } = canvas(85, 56);
  const at = map(W, H);
  x.fillStyle = '#186b37';
  x.fillRect(0, 0, W, H);

  // ground pour: a slightly lighter field with a hatched edge, as on a real board
  x.fillStyle = '#1c7a3e';
  x.fillRect(px(3), px(3), W - px(6), H - px(6));
  x.strokeStyle = 'rgba(255,255,255,.035)';
  x.lineWidth = px(.35);
  for (let i = -H; i < W; i += px(1.6)) {
    x.beginPath(); x.moveTo(i, 0); x.lineTo(i + H, H); x.stroke();
  }

  // routed copper: long traces fanning out of the SoC, just visible under the mask
  x.strokeStyle = 'rgba(255,214,130,.10)';
  x.lineWidth = px(.25);
  for (let i = 0; i < 90; i++) {
    const [sx, sy] = at(-12.5 + (Math.random() - .5) * 16, -1 + (Math.random() - .5) * 16);
    const a = Math.random() * Math.PI * 2, len = px(6 + Math.random() * 22);
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

  // gold pads under the 40-pin header, pin 1 square and called out
  for (let col = 0; col < 20; col++) {
    for (const row of [0, 1]) {
      const mx = -35.5 + col * 2.54, my = row ? 24.04 : 21.5;
      if (col === 0 && row === 0) pad(mx, my, 1.9, 1.9);
      else pad(mx, my, 1.9, 1.9, .9);
    }
  }
  outline(-35.5, 21.5, 3.2, 3.2);
  silk('1', -37.9, 19.3, 1.7, 'center');
  silk('40', 12.5, 26.2, 1.7, 'center');

  // the wordmark and the usual board legends
  silk('Raspberry Pi 5', -39, 8.5, 3.2);
  silk('Model B  © 2023', -39, 4.8, 1.9);
  silk('GPIO', 16, 22.8, 1.9);
  silk('CAM/DISP 0', 4, -20.5, 1.5);
  silk('CAM/DISP 1', 14.5, -20.5, 1.5);
  silk('PCIe', -37.5, -6, 1.5, 'left', -Math.PI / 2);
  silk('FAN', 30, 15.5, 1.5);
  silk('UART', -30, -12, 1.5);
  silk('PWR', -40, -19, 1.5);

  // component outlines, so the silicon is seated on printed footprints
  outline(-12.5, -1, 16.5, 16.5);
  outline(-29, 2, 12, 12);
  outline(10, -9, 13, 13);
  outline(-31, 16.5, 13, 11);
  outline(-31.3, -25, 10, 8);

  // mounting-hole rings
  for (const [mx, my] of [[-39, -24.5], [19, -24.5], [-39, 24.5], [19, 24.5]] as [number, number][]) {
    const [cx, cy] = at(mx, my);
    x.fillStyle = '#c9c2a8';
    x.beginPath(); x.arc(cx, cy, px(2.7), 0, 7); x.fill();
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
  x.fillText('CAPACITIVE TOUCH  SPI 48MHz', tx, ty);
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
