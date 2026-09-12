/**
 * The TICK handheld, built from the CAD numbers in design/cad/tick-case-3d.scad.
 * Device space: x right, y up, z toward the viewer (front face at z = 20).
 * Every part is a <Part> with a home position and an explode vector; the
 * camera rig sets rig.explode and each part slides along its vector.
 *
 * The parts sit where the CAD says they sit: the encoder is inside the shell
 * with only its bushing and knob through the right wall, the buttons are
 * 12 mm switches behind 13 mm square openings, and the display's 2x13 socket
 * covers the first 26 header pins — which is why the jumpers leave from the
 * far end of the header.
 */
import { useMemo, useRef, type ReactNode } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { rig } from './rig';
import { cut, box } from './csg';
import { layerLines, panelBack, piTop, sheen } from './pcb';
import { Game, Attract } from '../game/engine';
import { useChapter } from '../scroll';

type V3 = [number, number, number];

/* ---------------- where every part lives ---------------- */
const HOME = {
  lid: [0, 0, -16] as V3, lidEx: [0, 0, -104] as V3,
  pi: [6.8, 11.5, -3.5] as V3, piEx: [14, -92, -18] as V3,
  panel: [0, 19, 16] as V3, panelEx: [0, 14, 80] as V3,
  enc: [46, -33, 0] as V3, encEx: [62, 0, 0] as V3,
  btnY: -33, btnZ: 20, btnEx: [0, -6, 46] as V3,
};

/* ---------------- materials, shared ---------------- */
const bump = layerLines();
const M = {
  shell: new THREE.MeshPhysicalMaterial({ color: '#e9e3d4', roughness: .62, clearcoat: .22, clearcoatRoughness: .6, bumpMap: bump, bumpScale: .5 }),
  lid: new THREE.MeshPhysicalMaterial({ color: '#8f9599', roughness: .68, clearcoat: .14, clearcoatRoughness: .7, bumpMap: bump, bumpScale: .5 }),
  dark: new THREE.MeshStandardMaterial({ color: '#14171b', roughness: .55 }),
  black: new THREE.MeshStandardMaterial({ color: '#0b0d10', roughness: .48 }),
  pcb: new THREE.MeshStandardMaterial({ color: '#17652f', roughness: .58 }),
  pcbEdge: new THREE.MeshStandardMaterial({ color: '#0f4a24', roughness: .7 }),
  pcbDark: new THREE.MeshStandardMaterial({ color: '#121619', roughness: .62 }),
  metal: new THREE.MeshStandardMaterial({ color: '#c3ccd2', roughness: .26, metalness: .95 }),
  steel: new THREE.MeshStandardMaterial({ color: '#9aa4ab', roughness: .34, metalness: .9 }),
  gold: new THREE.MeshStandardMaterial({ color: '#e0bb55', roughness: .28, metalness: .95 }),
  chip: new THREE.MeshStandardMaterial({ color: '#1a1d21', roughness: .42 }),
  chipLid: new THREE.MeshStandardMaterial({ color: '#aab3ba', roughness: .22, metalness: .9 }),
  white: new THREE.MeshStandardMaterial({ color: '#e9e9e4', roughness: .6 }),
  kapton: new THREE.MeshStandardMaterial({ color: '#c08a2e', roughness: .45, side: THREE.DoubleSide }),
  glass: new THREE.MeshPhysicalMaterial({ color: '#0a0d10', roughness: .06, clearcoat: 1, clearcoatRoughness: .04, metalness: .1, transparent: true, opacity: .55 }),
  red: new THREE.MeshPhysicalMaterial({ color: '#d4392c', roughness: .3, clearcoat: .8, clearcoatRoughness: .15 }),
  knob: new THREE.MeshPhysicalMaterial({ color: '#b8362b', roughness: .38, clearcoat: .5, clearcoatRoughness: .3 }),
  knobDark: new THREE.MeshStandardMaterial({ color: '#7d2119', roughness: .5 }),
  yellow: new THREE.MeshPhysicalMaterial({ color: '#e9b41c', roughness: .3, clearcoat: .8, clearcoatRoughness: .15 }),
  usb3: new THREE.MeshStandardMaterial({ color: '#1f5fbf', roughness: .5 }),
  led: new THREE.MeshStandardMaterial({ color: '#3d2020', emissive: '#ff4436', emissiveIntensity: 2.2, roughness: .4 }),
};

/* ---------------- helpers ---------------- */
function Part({ home, explode, rotation, children }: { home: V3; explode: V3; rotation?: V3; children: ReactNode }) {
  const ref = useRef<THREE.Group>(null!);
  const h = useMemo(() => new THREE.Vector3(...home), [home[0], home[1], home[2]]);
  const e = useMemo(() => new THREE.Vector3(...explode), [explode[0], explode[1], explode[2]]);
  useFrame(() => { ref.current.position.copy(h).addScaledVector(e, rig.explode); });
  return <group ref={ref} position={home} rotation={rotation}>{children}</group>;
}

function Callout({ position, show, title, sub }: { position: V3; show: number[]; title: string; sub?: string }) {
  const chapter = useChapter();
  const on = show.includes(chapter);
  if (!on) return null;          // off-chapter callouts leave the DOM entirely
  return (
    <Html position={position} center distanceFactor={190} zIndexRange={[30, 0]} style={{ pointerEvents: 'none' }}>
      <div className="callout on">
        <i />
        <b>{title}</b>
        {sub && <span>{sub}</span>}
      </div>
    </Html>
  );
}

function rbox(w: number, h: number, d: number, r: number, at: V3 = [0, 0, 0]) {
  const g = new RoundedBoxGeometry(w, h, d, 6, r);
  g.translate(...at);
  return g;
}

/* ---------------- BODY: the deep front shell, with its real cut-outs ---------------- */
function Body() {
  const geo = useMemo(() => cut(rbox(104, 110, 32, 3, [0, 0, 4]), [
    box(99, 105, 30.5, 0, 0, 2.25),        // cavity, open at the back
    box(79, 49, 6, 0, 19, 19),             // screen window
    box(13.3, 13.3, 6, -13, -33, 19),      // red button
    box(13.3, 13.3, 6, 13, -33, 19),       // yellow button
    box(6, 12.3, 12.3, 52, -33, 0),        // encoder square, right wall
    box(28, 6, 14, 25, 55, -5),            // cable opening, top face, right corner
  ]), []);
  return (
    <group>
      <mesh geometry={geo} material={M.shell} castShadow receiveShadow />
      <Callout position={[-54, -34, 6]} show={[3]} title="Printed body" sub="every opening is in this part" />
    </group>
  );
}

/* ---------------- LID: the shallow back dish with the grille ---------------- */
function Lid() {
  const geo = useMemo(() => {
    const cutters = [box(99, 105, 6, 0, 0, 1.5)];
    for (let c = 0; c < 9; c++) for (let r = 0; r < 7; r++) cutters.push(box(3, 2.2, 10, -28 + c * 7, -11 + r * 5, 0));
    return cut(rbox(104, 110, 8, 3), cutters);
  }, []);
  return (
    <Part home={HOME.lid} explode={HOME.lidEx}>
      <mesh geometry={geo} material={M.lid} castShadow receiveShadow />
      {[-1, 1].map((s) => (
        <group key={s} position={[s * 46, -9, 0]}>
          <mesh position={[0, 0, -.5]} material={M.lid}><boxGeometry args={[10, 25, 2]} /></mesh>
          <mesh position={[s * 4, 0, 4.5]} material={M.lid}><boxGeometry args={[2, 25, 10]} /></mesh>
        </group>
      ))}
      <Callout position={[-40, -44, 0]} show={[3]} title="Back lid" sub="presses on, 5 mm lip, no screws" />
    </Part>
  );
}

/* Rear-mounted speaker. Illustrative proportions, pending the physical driver dimensions. */
function Speaker() {
  return (
    <Part home={[0, 4, -11]} explode={[0, 0, -78]}>
      <group rotation={[Math.PI / 2, 0, 0]}>
        <mesh material={M.dark} castShadow><cylinderGeometry args={[21, 21, 3, 64]} /></mesh>
        <mesh position={[0, -2, 0]} material={M.steel} castShadow><cylinderGeometry args={[13, 18, 5, 48]} /></mesh>
        <mesh position={[0, -6, 0]} material={M.black}><cylinderGeometry args={[10, 10, 5, 48]} /></mesh>
        <mesh position={[0, 1.6, 0]} material={M.black}><cylinderGeometry args={[18, 18, .6, 64]} /></mesh>
        <mesh position={[0, 2, 0]} rotation={[Math.PI / 2, 0, 0]} material={M.dark}><torusGeometry args={[16, 1.5, 10, 64]} /></mesh>
        <mesh position={[0, 2.1, 0]} scale={[1, .3, 1]} material={M.dark}><sphereGeometry args={[7, 32, 16]} /></mesh>
      </group>
      {[-1, 1].map((side) => <mesh key={side} position={[side * 8, -16, 4]} material={M.gold}><boxGeometry args={[3, 4, .8]} /></mesh>)}
      <Callout position={[22, 18, 0]} show={[3, 4]} title="Rear speaker" sub="mounted behind the back grille" />
    </Part>
  );
}

/* ---------------- RASPBERRY PI ZERO W ----------------
   Board-local mm from the board centre: 65 x 30, the soldered 40-pin header
   along the top edge, mini-HDMI and the two micro-USBs along the bottom, the
   card slot off the left edge and the radio at the right with its antenna. */
const PIN_X0 = -28.7, PIN_ROW = [8.96, 11.5], PIN_TOP = 9.2;
function pinPos(n: number): V3 {
  const col = Math.floor((n - 1) / 2), row = (n - 1) % 2;
  return [PIN_X0 + col * 2.54, PIN_ROW[row], PIN_TOP];
}
/** Header pin n in device space, following the board's half-turn and its explode. */
function pinWorld(n: number, explode: number): THREE.Vector3 {
  const [x, y, z] = pinPos(n);
  return new THREE.Vector3(
    HOME.pi[0] - x + HOME.piEx[0] * explode,
    HOME.pi[1] - y + HOME.piEx[1] * explode,
    HOME.pi[2] + z + HOME.piEx[2] * explode,
  );
}

function Pi() {
  const top = useMemo(() => piTop(), []);
  const boardMat = useMemo(() => new THREE.MeshStandardMaterial({ map: top, roughness: .55 }), [top]);
  const pins = useMemo(() => Array.from({ length: 40 }, (_, i) => pinPos(i + 1)), []);
  return (
    // Rotated half a turn so the power micro-USB faces the top of the case and
    // the header faces the buttons, which is where the wires have to go.
    <Part home={HOME.pi} explode={HOME.piEx} rotation={[0, 0, Math.PI]}>
      {/* board: green edge, printed top */}
      <mesh material={M.pcbEdge} castShadow receiveShadow><boxGeometry args={[65, 30, 1.4]} /></mesh>
      <mesh position={[0, 0, .71]} material={boardMat}><planeGeometry args={[65, 30]} /></mesh>

      {/* the soldered 40-pin header */}
      <mesh position={[-4.57, 10.23, 1.95]} material={M.black}><boxGeometry args={[50.8, 5.08, 2.5]} /></mesh>
      {pins.map((p, i) => (
        <mesh key={i} position={[p[0], p[1], 4.3]} material={M.gold}><boxGeometry args={[.64, .64, 11.2]} /></mesh>
      ))}

      {/* BCM2835 with its RAM stacked on top, and the wireless module */}
      <mesh position={[-5, -3, 1.35]} material={M.chip}><boxGeometry args={[12.4, 12.4, 1.3]} /></mesh>
      <mesh position={[-5, -3, 2.1]} material={M.black}><boxGeometry args={[9.6, 9.6, .4]} /></mesh>
      <mesh position={[23, 1, 1.5]} material={M.chipLid}><boxGeometry args={[10.4, 8.4, 1.6]} /></mesh>
      <mesh position={[29.6, 11, 1.1]} material={M.chipLid}><boxGeometry args={[5.2, 4, .5]} /></mesh>
      {[[-16, -7], [-14, 2], [6, 4], [12, -6]].map(([x, y], i) => (
        <mesh key={i} position={[x, y, 1.1]} material={M.steel}><boxGeometry args={[3.4, 2.6, .8]} /></mesh>
      ))}
      {/* the two solder pads for RUN and TV */}
      {[[-23.5, 3.6], [-18, 3.6]].map(([x, y], i) => (
        <mesh key={i} position={[x, y, .8]} material={M.gold}><cylinderGeometry args={[.9, .9, .3, 12]} /></mesh>
      ))}
      <mesh position={[-26, -6, 1]} material={M.led}><boxGeometry args={[1.8, 1.2, .7]} /></mesh>

      {/* bottom edge: mini-HDMI, micro-USB data, micro-USB power */}
      <group position={[-20.1, -13.4, 2.2]}>
        <mesh material={M.metal}><boxGeometry args={[11.2, 6.8, 3]} /></mesh>
        <mesh position={[0, -3.3, 0]} material={M.black}><boxGeometry args={[9.6, .8, 1.9]} /></mesh>
      </group>
      {[8.9, 21.5].map((x) => (
        <group key={x} position={[x, -13.6, 2.1]}>
          <mesh material={M.metal}><boxGeometry args={[7.6, 6.4, 2.8]} /></mesh>
          <mesh position={[0, -3, 0]} material={M.black}><boxGeometry args={[6.2, .8, 1.7]} /></mesh>
        </group>
      ))}

      {/* microSD off the left edge, camera FPC on the right */}
      <mesh position={[-33.5, 0, -1.4]} material={M.steel}><boxGeometry args={[13, 12, 1.6]} /></mesh>
      <mesh position={[30, -3, 1.6]} material={M.black}><boxGeometry args={[3.4, 12, 1.8]} /></mesh>

      <Callout position={[-4, -20, 6]} show={[3]} title="Raspberry Pi Zero W" sub="BCM2835 · 512 MB · 65 × 30 mm" />
    </Part>
  );
}

/* ---------------- PANEL: the 3.5" IPS module, running the game ---------------- */
function Panel() {
  const back = useMemo(() => panelBack(), []);
  const gloss = useMemo(() => sheen(), []);
  const backMat = useMemo(() => new THREE.MeshStandardMaterial({ map: back, roughness: .7 }), [back]);
  const sheenMat = useMemo(() => new THREE.MeshBasicMaterial({ map: gloss, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: .26 }), [gloss]);
  const { tex, game, attract } = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 480; canvas.height = 320;
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    const game = new Game(canvas, null, { seed: 11 });
    const attract = new Attract(game);
    game.step(.06, performance.now() / 1000); game.draw(); tex.needsUpdate = true;
    return { tex, game, attract };
  }, []);
  const acc = useRef(0);
  useFrame((_, dt) => {
    const now = performance.now() / 1000;
    game.step(Math.min(.1, dt), now);
    attract.step(now);
    acc.current += dt;
    if (acc.current > 1 / 20) { game.draw(); tex.needsUpdate = true; acc.current = 0; }
  });
  return (
    <Part home={HOME.panel} explode={HOME.panelEx}>
      {/* carrier board, printed on the back */}
      <mesh material={M.pcbDark} castShadow><boxGeometry args={[92, 60, 1.6]} /></mesh>
      <mesh position={[0, 0, -.81]} rotation={[0, Math.PI, 0]} material={backMat}><planeGeometry args={[92, 60]} /></mesh>
      {/* the panel itself: black cover glass with the image behind it */}
      <mesh position={[0, 0, 1.1]} material={M.black}><boxGeometry args={[88, 56, .8]} /></mesh>
      <mesh position={[0, 0, 1.52]}>
        <planeGeometry args={[79, 49]} />
        <meshStandardMaterial color="#000" emissive="#ffffff" emissiveMap={tex} emissiveIntensity={1.2} roughness={.9} />
      </mesh>
      <mesh position={[0, 0, 1.62]} material={M.glass}><boxGeometry args={[88, 56, .12]} /></mesh>
      <mesh position={[0, 0, 1.7]} material={sheenMat}><planeGeometry args={[88, 56]} /></mesh>
      {/* ribbon to the touch controller, the driver board and the 2x13 socket */}
      <mesh position={[6, -32.6, -.2]} rotation={[.5, 0, 0]} material={M.kapton}><planeGeometry args={[26, 9]} /></mesh>
      <mesh position={[-20, -33.5, -.9]} material={M.pcbDark}><boxGeometry args={[16, 9, 1.2]} /></mesh>
      <mesh position={[-20, -33.5, -.1]} material={M.chip}><boxGeometry args={[5, 5, .8]} /></mesh>
      <mesh position={[19, -17.8, -5.6]} material={M.black}><boxGeometry args={[34, 5.1, 8.4]} /></mesh>
      {[[-42, -26], [42, -26], [-42, 26], [42, 26]].map(([x, y], i) => (
        <mesh key={i} position={[x, y, -2.4]} material={M.steel}><cylinderGeometry args={[2, 2, 3.2, 12]} /></mesh>
      ))}
      <Callout position={[-18, 32, 4]} show={[2, 3]} title="3.5″ IPS · 480 × 320" sub="on the first 26 header pins" />
    </Part>
  );
}

/* ---------------- BUTTONS: 12 mm switches behind the 13 mm square openings ---------------- */
function Button({ x, cap, callout }: { x: number; cap: THREE.Material; callout?: ReactNode }) {
  return (
    <Part home={[x, HOME.btnY, HOME.btnZ]} explode={[x * .5, HOME.btnEx[1], HOME.btnEx[2]]}>
      {/* the cap sits in the square opening and stands 2.5 mm proud */}
      <mesh position={[0, 0, .5]} material={cap} rotation={[Math.PI / 2, 0, 0]} castShadow><cylinderGeometry args={[5.75, 5.5, 4, 48]} /></mesh>
      <mesh position={[0, 0, 2.5]} material={cap} scale={[1, 1, .32]}><sphereGeometry args={[5.75, 32, 16]} /></mesh>
      <mesh position={[0, 0, -2]} material={M.black} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[6.4, 6.4, 1.4, 40]} /></mesh>
      {/* the switch body behind the wall, with its dome plate and two connection terminals */}
      <mesh position={[0, 0, -6.4]} material={M.black}><boxGeometry args={[12, 12, 7]} /></mesh>
      <mesh position={[0, 0, -2.9]} material={M.steel}><boxGeometry args={[10.6, 10.6, .4]} /></mesh>
      {[-1, 1].map((side) => (
        <mesh key={side} position={[side * 5.4, 0, -10.6]} material={M.gold}><boxGeometry args={[1.2, 2.6, 1.4]} /></mesh>
      ))}
      {callout}
    </Part>
  );
}
function Buttons() {
  return (
    <>
      <Button x={-13} cap={M.red} callout={<Callout position={[-6, -16, -2]} show={[3]} title="12 mm switches" sub="two leads each: signal + ground" />} />
      <Button x={13} cap={M.yellow} />
    </>
  );
}

/* ---------------- ROTARY ENCODER: inside the shell, knob through the wall ---------------- */
function Encoder() {
  const spin = useRef<THREE.Group>(null!);
  useFrame(() => {
    const f = rig.prog * 5;
    const on = f > .55 && f < 2.2 ? 1 : 0;
    if (!rig.reduced) spin.current.rotation.x = rig.t * 2.6 * on;
  });
  const knurl = useMemo(() => Array.from({ length: 22 }, (_, i) => (i / 22) * Math.PI * 2), []);
  return (
    <Part home={HOME.enc} explode={HOME.encEx}>
      {/* KY-040 board, standing against the inside of the right wall */}
      <mesh position={[-5, 0, -1]} material={M.pcb}><boxGeometry args={[1.6, 26, 19]} /></mesh>
      <mesh position={[-6, -8.5, -1]} material={M.black}><boxGeometry args={[2.6, 3, 13]} /></mesh>
      {[-2, -1, 0, 1, 2].map((i) => (
        <mesh key={i} position={[-9, -8.5, i * 2.54]} material={M.gold}><boxGeometry args={[6, .64, .64]} /></mesh>
      ))}
      <mesh position={[-4, 7, 4]} material={M.chip}><boxGeometry args={[.8, 3.2, 1.6]} /></mesh>
      {/* the encoder can: 12.4 mm square, just inside the 12 mm wall opening */}
      <mesh position={[0, 0, 0]} material={M.steel} castShadow><boxGeometry args={[6.6, 12.4, 12.4]} /></mesh>
      <mesh position={[3.6, 0, 0]} material={M.steel} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[3.5, 3.5, 5, 24]} /></mesh>
      <mesh position={[7.4, 0, 0]} material={M.steel} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[4.6, 4.6, 1.6, 6]} /></mesh>
      {/* only this comes out of the case */}
      <group ref={spin}>
        <mesh position={[11, 0, 0]} material={M.steel} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[3, 3, 9, 20]} /></mesh>
        <mesh position={[14.5, 0, 0]} material={M.knob} rotation={[0, 0, Math.PI / 2]} castShadow><cylinderGeometry args={[7.4, 7, 12, 40]} /></mesh>
        {knurl.map((a, i) => (
          <mesh key={i} position={[14.5, Math.cos(a) * 7.2, Math.sin(a) * 7.2]} rotation={[-a, 0, 0]} material={M.knobDark}><boxGeometry args={[11, .9, .9]} /></mesh>
        ))}
        <mesh position={[20.6, 0, 0]} material={M.knob} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[7, 7, .6, 40]} /></mesh>
        <mesh position={[21, 0, 4.2]} material={M.yellow}><boxGeometry args={[.8, 1.6, 5]} /></mesh>
      </group>
      <Callout position={[-2, 20, 0]} show={[1, 3]} title="KY-040 encoder" sub="CLK 21 · DT 20 · SW 16" />
    </Part>
  );
}

/* ---------------- JUMPER WIRES: header → buttons and encoder ----------------
   Silicone jumpers with Dupont shells, rebuilt only when the explode changes. */
const WIRES = [
  { pin: 33, to: 'red', terminal: -1, color: '#e04a3f' },
  { pin: 34, to: 'red', terminal: 1, color: '#23272b' },
  { pin: 37, to: 'yellow', terminal: -1, color: '#ffcc48' },
  { pin: 39, to: 'yellow', terminal: 1, color: '#23272b' },
  { pin: 40, to: 'enc', color: '#7fe4b8' },
  { pin: 38, to: 'enc', color: '#3d8fd0' },
  { pin: 36, to: 'enc', color: '#e8e2d3' },
];

function endOf(to: string, explode: number, terminal = 0) {
  if (to === 'enc') {
    return new THREE.Vector3(HOME.enc[0] - 9 + HOME.encEx[0] * explode, HOME.enc[1] - 8.5, HOME.enc[2] - 1);
  }
  const x = to === 'red' ? -13 : 13;
  return new THREE.Vector3(x + x * .5 * explode + terminal * 5.4, HOME.btnY + HOME.btnEx[1] * explode, HOME.btnZ - 10.6 + HOME.btnEx[2] * explode);
}

function Wires() {
  const group = useRef<THREE.Group>(null!);
  const last = useRef(-1);
  const meshes = useRef<THREE.Mesh[]>([]);
  const mats = useMemo(() => WIRES.map((w) => new THREE.MeshStandardMaterial({ color: w.color, roughness: .42 })), []);

  useFrame(() => {
    if (Math.abs(rig.explode - last.current) < .002) return;
    last.current = rig.explode;
    WIRES.forEach((w, i) => {
      const a = pinWorld(w.pin, rig.explode);
      const b = endOf(w.to, rig.explode, w.terminal);
      // out of the pin, down behind the board, then round to the switch
      const c1 = a.clone().add(new THREE.Vector3(0, -6, -10 - i * 1.5));
      const c2 = new THREE.Vector3(a.x * .35 + b.x * .65, b.y + 16 + i * 1.2, b.z - 16 - i * 1.5);
      const curve = new THREE.CubicBezierCurve3(a, c1, c2, b);
      const geo = new THREE.TubeGeometry(curve, 28, .62, 7, false);
      const mesh = meshes.current[i];
      if (mesh) { mesh.geometry.dispose(); mesh.geometry = geo; }
    });
  });

  return (
    <group ref={group}>
      {WIRES.map((w, i) => (
        <group key={i}>
          <mesh ref={(el) => { if (el) meshes.current[i] = el; }} material={mats[i]} />
        </group>
      ))}
    </group>
  );
}

/* ---------------- the whole device ---------------- */
export function Device() {
  const yaw = useRef<THREE.Group>(null!);
  useFrame(() => {
    const f = rig.prog * 5, i = Math.floor(f), u = f - i;
    const idle = rig.reduced ? 0 : rig.t;
    const y = (i === 0 && u < .5 ? Math.sin(idle * .35) * .16 : 0) + (i >= 4 ? Math.sin(idle * .25) * .2 : 0);
    yaw.current.rotation.y = y;
    yaw.current.position.y = rig.reduced ? 0 : Math.sin(idle * .8) * 2;
  });
  return (
    <group ref={yaw}>
      <Body />
      <Lid />
      <Speaker />
      <Pi />
      <Panel />
      <Buttons />
      <Encoder />
      <Wires />
    </group>
  );
}
