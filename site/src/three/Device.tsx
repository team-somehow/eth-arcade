/**
 * The TICK handheld, built from the CAD numbers in design/cad/tick-case-3d.scad.
 * Device space: x right, y up, z toward the viewer (front face at z = 20).
 * Every part is a <Part> with a home position and an explode vector; the
 * camera rig sets rig.explode and each part slides along its vector.
 */
import { useMemo, useRef, type ReactNode } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Html, Instances, Instance, QuadraticBezierLine } from '@react-three/drei';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { rig } from './rig';
import { cut, box } from './csg';
import { Game, Attract } from '../game/engine';
import { useChapter } from '../scroll';

type V3 = [number, number, number];

/* ---------------- materials, shared ---------------- */
const M = {
  shell: new THREE.MeshPhysicalMaterial({ color: '#e8e2d3', roughness: .48, clearcoat: .35, clearcoatRoughness: .45 }),
  lid: new THREE.MeshPhysicalMaterial({ color: '#d8d2c4', roughness: .55, clearcoat: .25, clearcoatRoughness: .5 }),
  dark: new THREE.MeshStandardMaterial({ color: '#14171b', roughness: .55 }),
  pcb: new THREE.MeshStandardMaterial({ color: '#1e7a3f', roughness: .62 }),
  pcbDark: new THREE.MeshStandardMaterial({ color: '#1b5e3a', roughness: .65 }),
  metal: new THREE.MeshStandardMaterial({ color: '#b7c0c6', roughness: .3, metalness: .95 }),
  gold: new THREE.MeshStandardMaterial({ color: '#d9b64a', roughness: .35, metalness: .9 }),
  chip: new THREE.MeshStandardMaterial({ color: '#24272c', roughness: .45 }),
  chipLid: new THREE.MeshStandardMaterial({ color: '#9aa3a9', roughness: .28, metalness: .85 }),
  white: new THREE.MeshStandardMaterial({ color: '#e9e9e4', roughness: .6 }),
  kapton: new THREE.MeshStandardMaterial({ color: '#c9973a', roughness: .5, transparent: true, opacity: .92 }),
  glass: new THREE.MeshPhysicalMaterial({ color: '#dbe6ee', transparent: true, opacity: .2, roughness: .04, clearcoat: 1, clearcoatRoughness: .05, depthWrite: false }),
  red: new THREE.MeshPhysicalMaterial({ color: '#d8382c', roughness: .35, clearcoat: .6 }),
  yellow: new THREE.MeshPhysicalMaterial({ color: '#e8b219', roughness: .35, clearcoat: .6 }),
  usb3: new THREE.MeshStandardMaterial({ color: '#1f5fbf', roughness: .5 }),
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
  return (
    <Html position={position} center distanceFactor={300} zIndexRange={[30, 0]} style={{ pointerEvents: 'none' }}>
      <div className={'callout' + (on ? ' on' : '')}>
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
      <mesh geometry={geo} material={M.shell} />
      <Callout position={[-52, 40, 20]} show={[3]} title="Printed body" sub="104 × 110 × 40 mm · every opening is in this part" />
      <Callout position={[25, 56, -5]} show={[3, 5]} title="USB-C cable exit" sub="28 × 14 mm, top-right corner" />
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
    <Part home={[0, 0, -16]} explode={[0, 0, -86]}>
      <mesh geometry={geo} material={M.lid} />
      {[-1, 1].map((s) => (
        <group key={s} position={[s * 46, -9, 0]}>
          <mesh position={[0, 0, -.5]} material={M.shell}><boxGeometry args={[10, 25, 2]} /></mesh>
          <mesh position={[s * 4, 0, 4.5]} material={M.shell}><boxGeometry args={[2, 25, 10]} /></mesh>
        </group>
      ))}
      <Callout position={[0, 48, -4]} show={[3]} title="Back lid" sub="presses on — a 5 mm lip, no screws" />
      <Callout position={[0, 4, -8]} show={[3]} title="Speaker grille" sub="63 slots" />
      <Callout position={[-46, -9, 12]} show={[3]} title="L-brackets" sub="glued where the board should stop" />
    </Part>
  );
}

/* ---------------- RASPBERRY PI 5 ---------------- */
const HEADER_X = -3.5, HEADER_Y = 24.5;
/** Header pin n (1..40) in Pi-local coordinates. Odd pins are the inner row. */
function pinPos(n: number): V3 {
  const col = Math.floor((n - 1) / 2), row = (n - 1) % 2;
  return [HEADER_X + (col - 9.5) * 2.54, HEADER_Y + (row ? 1.27 : -1.27), 4];
}
const WIRE_PINS = [33, 34, 37, 40, 38, 36];

function Pi5() {
  const pins = useMemo(() => Array.from({ length: 40 }, (_, i) => pinPos(i + 1)), []);
  return (
    // Rotated half a turn so the USB-C edge faces the top of the case and the
    // GPIO header faces the buttons, which is where the wires have to go.
    <Part home={[0, 24, -16.7]} explode={[0, 0, -48]} rotation={[0, 0, Math.PI]}>
      <mesh material={M.pcb}><boxGeometry args={[85, 56, 1.6]} /></mesh>
      {[[-29, -24.5], [29, -24.5], [-29, 24.5], [29, 24.5]].map(([x, y], i) => (
        <mesh key={i} position={[x, y, 0]} material={M.dark} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[1.35, 1.35, 1.9, 16]} /></mesh>
      ))}
      {/* 40-pin GPIO header */}
      <mesh position={[HEADER_X, HEADER_Y, 2.05]} material={M.dark}><boxGeometry args={[50.8, 5.1, 2.5]} /></mesh>
      <Instances limit={40} range={40} material={M.gold}>
        <boxGeometry args={[.64, .64, 6.4]} />
        {pins.map((p, i) => <Instance key={i} position={p} />)}
      </Instances>
      {WIRE_PINS.map((n) => <object3D key={n} name={'pin-' + n} position={[pinPos(n)[0], pinPos(n)[1], 7.4]} />)}
      {/* silicon */}
      <mesh position={[-7, 3, 1.3]} material={M.chip}><boxGeometry args={[15, 15, 1]} /></mesh>
      <mesh position={[-7, 3, 2.4]} material={M.chipLid}><boxGeometry args={[12, 12, 1.2]} /></mesh>
      <mesh position={[-26, 3, 1.3]} material={M.chip}><boxGeometry args={[12, 10, 1]} /></mesh>
      <mesh position={[23, -3, 1.3]} material={M.chip}><boxGeometry args={[11, 11, 1]} /></mesh>
      <mesh position={[-32, -12, 1.3]} material={M.chip}><boxGeometry args={[6, 6, 1]} /></mesh>
      <mesh position={[-27, 17, 1.7]} material={M.chipLid}><boxGeometry args={[12, 10, 1.8]} /></mesh>
      {/* bottom edge: USB-C power, two micro-HDMI, camera/display FPCs, fan header */}
      <mesh position={[-31.3, -26.2, 2.4]} material={M.metal}><boxGeometry args={[9, 7.6, 3.2]} /></mesh>
      <mesh position={[-31.3, -29.9, 2.4]} material={M.dark}><boxGeometry args={[7.2, .6, 2.2]} /></mesh>
      {[-16.5, -3].map((x) => (
        <group key={x}>
          <mesh position={[x, -26.6, 2.3]} material={M.metal}><boxGeometry args={[7, 6.4, 3]} /></mesh>
          <mesh position={[x, -29.7, 2.3]} material={M.dark}><boxGeometry args={[5.6, .6, 1.8]} /></mesh>
        </group>
      ))}
      {[9, 19.5].map((x) => (
        <group key={x}>
          <mesh position={[x, -25.5, 2.4]} material={M.dark}><boxGeometry args={[15, 3, 3.4]} /></mesh>
          <mesh position={[x, -25.5, 4.4]} material={M.white}><boxGeometry args={[15, 2.2, .8]} /></mesh>
        </group>
      ))}
      <mesh position={[28, -22, 2.5]} material={M.white}><boxGeometry args={[3.4, 4, 3.6]} /></mesh>
      {/* right edge: Ethernet, USB 3 pair, USB 2 pair */}
      <mesh position={[36.5, 18.5, 7.5]} material={M.metal}><boxGeometry args={[16, 21.5, 13.5]} /></mesh>
      <mesh position={[44.6, 18.5, 8.5]} material={M.dark}><boxGeometry args={[.6, 16, 11]} /></mesh>
      <mesh position={[36.5, -1, 8.6]} material={M.metal}><boxGeometry args={[13.3, 17.6, 15.6]} /></mesh>
      {[4, 12.5].map((z) => <mesh key={z} position={[43.3, -1, z]} material={M.usb3}><boxGeometry args={[.6, 12.5, 5]} /></mesh>)}
      <mesh position={[36.5, -19.5, 8.6]} material={M.metal}><boxGeometry args={[13.3, 17.6, 15.6]} /></mesh>
      {[4, 12.5].map((z) => <mesh key={z} position={[43.3, -19.5, z]} material={M.dark}><boxGeometry args={[.6, 12.5, 5]} /></mesh>)}
      {/* odds and ends */}
      <mesh position={[-40.6, 21, 1.6]} material={M.dark} rotation={[0, Math.PI / 2, 0]}><cylinderGeometry args={[1.2, 1.2, 1.6, 12]} /></mesh>
      <mesh position={[-38, -20, 2.3]} material={M.white}><boxGeometry args={[4, 4, 3]} /></mesh>
      <mesh position={[-36, 0, -1.8]} material={M.dark}><boxGeometry args={[12, 15, 2]} /></mesh>
      <mesh position={[-12, 19, 1.5]} material={M.dark}><boxGeometry args={[7.6, 2.6, 2]} /></mesh>

      <Callout position={[0, -6, 14]} show={[3]} title="Raspberry Pi 5" sub="BCM2712 · 4 GB · 85 × 56 mm" />
      <Callout position={[-3.5, 32, 10]} show={[3]} title="40-pin GPIO header" sub="buttons on 13 / 26 · encoder on 21 / 20 / 16" />
      <Callout position={[-31, -36, 5]} show={[3]} title="USB-C power" sub="5 V ⎓ 5 A · exits the top of the case" />
      <Callout position={[-10, -36, 4]} show={[3]} title="2 × micro-HDMI" />
      <Callout position={[47, 0, 10]} show={[3]} title="USB 3.0 · USB 2.0 · Gigabit Ethernet" />
    </Part>
  );
}

/* ---------------- PANEL: 3.5" IPS with capacitive touch, running the game ---------------- */
function Panel() {
  const { canvas, tex, game, attract } = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 480; canvas.height = 320;
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    const game = new Game(canvas, null, { seed: 11 });
    const attract = new Attract(game);
    game.step(.06, performance.now() / 1000); game.draw(); tex.needsUpdate = true;
    return { canvas, tex, game, attract };
  }, []);
  void canvas;
  const acc = useRef(0);
  useFrame((_, dt) => {
    const now = performance.now() / 1000;
    game.step(Math.min(.1, dt), now);
    attract.step(now);
    acc.current += dt;
    if (acc.current > 1 / 20) { game.draw(); tex.needsUpdate = true; acc.current = 0; }
  });
  return (
    <Part home={[0, 19, 16]} explode={[0, 0, 56]}>
      <mesh material={M.dark}><boxGeometry args={[92, 60, 3]} /></mesh>
      <mesh position={[0, 0, 1.55]}>
        <planeGeometry args={[79, 49]} />
        <meshStandardMaterial color="#000" emissive="#ffffff" emissiveMap={tex} emissiveIntensity={1.15} roughness={.9} />
      </mesh>
      <mesh position={[0, 0, 1.64]} material={M.glass}><planeGeometry args={[92, 60]} /></mesh>
      {/* ribbon to the touch controller, and the 2x20 socket that mates with the Pi header */}
      <mesh position={[6, -33.5, -.6]} material={M.kapton}><boxGeometry args={[24, 9, .3]} /></mesh>
      <mesh position={[-18, -33.5, -.7]} material={M.pcbDark}><boxGeometry args={[14, 9, 1.2]} /></mesh>
      <mesh position={[-18, -33.5, .1]} material={M.chip}><boxGeometry args={[5, 5, .8]} /></mesh>
      <mesh position={[0, -18, -5.7]} material={M.dark}><boxGeometry args={[50.8, 5.1, 8.5]} /></mesh>
      <Callout position={[0, 36, 6]} show={[2, 3]} title="3.5″ IPS · 480 × 320" sub="capacitive touch (Goodix) · SPI at 48 MHz" />
      <Callout position={[-14, -42, 0]} show={[3]} title="Touch controller + ribbon" />
      <Callout position={[0, -18, -14]} show={[3]} title="2 × 20 socket" sub="mates with the Pi's GPIO header" />
    </Part>
  );
}

/* ---------------- ARCADE BUTTONS ---------------- */
function Button({ x, material, name, callout }: { x: number; material: THREE.Material; name: string; callout?: ReactNode }) {
  return (
    <Part home={[x, -33, 20]} explode={[x * .55, 0, 36]}>
      <mesh position={[0, 0, 1.6]} material={material} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[7.6, 7.6, 6.5, 40]} /></mesh>
      <mesh position={[0, 0, -.4]} material={M.dark} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[9.4, 9.4, 1.6, 40]} /></mesh>
      <mesh position={[0, 0, -6.5]} material={M.dark}><boxGeometry args={[13, 13, 9]} /></mesh>
      <mesh position={[0, 0, -14]} material={M.dark}><boxGeometry args={[6, 10, 6]} /></mesh>
      {[-3, 3].map((dy) => <mesh key={dy} position={[0, dy, -18.2]} material={M.gold}><boxGeometry args={[1, 2.4, 2.4]} /></mesh>)}
      <object3D name={name} position={[0, 0, -18]} />
      {callout}
    </Part>
  );
}
function Buttons() {
  return (
    <>
      <Button x={-13} material={M.red} name="anchor-red" callout={<Callout position={[0, -14, 6]} show={[3]} title="Arcade buttons" sub="red → GPIO13, back · yellow → GPIO26, buy" />} />
      <Button x={13} material={M.yellow} name="anchor-yellow" />
    </>
  );
}

/* ---------------- ROTARY ENCODER (KY-040 module) ---------------- */
function Encoder() {
  const spin = useRef<THREE.Group>(null!);
  useFrame(() => {
    const f = rig.prog * 5;
    const on = f > .55 && f < 2.2 ? 1 : 0;
    if (!rig.reduced) spin.current.rotation.x = rig.t * 2.6 * on;
  });
  return (
    <Part home={[48, -33, 0]} explode={[58, 0, 0]}>
      <mesh position={[-1, 0, 0]} material={M.pcbDark}><boxGeometry args={[1.6, 26, 19]} /></mesh>
      <mesh position={[-2.6, 0, -6.5]} material={M.dark}><boxGeometry args={[3, 13, 2.5]} /></mesh>
      {[-2, -1, 0, 1, 2].map((i) => <mesh key={i} position={[-4.8, i * 2.54, -6.5]} material={M.gold}><boxGeometry args={[6, .64, .64]} /></mesh>)}
      <mesh position={[2.6, 0, 0]} material={M.metal}><boxGeometry args={[6, 12, 12]} /></mesh>
      <mesh position={[8.6, 0, 0]} material={M.metal} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[3.5, 3.5, 6, 24]} /></mesh>
      <group ref={spin}>
        <mesh position={[17, 0, 0]} material={M.metal} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[3, 3, 12, 24]} /></mesh>
        <mesh position={[25, 0, 0]} material={M.dark} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[7, 7, 10, 18]} /></mesh>
        <mesh position={[25, 0, 6.7]} material={M.yellow}><boxGeometry args={[1.4, 1.6, 8]} /></mesh>
      </group>
      <object3D name="anchor-enc" position={[-7, 0, -6.5]} />
      <Callout position={[32, 14, 0]} show={[1, 3]} title="KY-040 rotary encoder" sub="CLK 21 · DT 20 · SW 16 — read raw, every click counts" />
    </Part>
  );
}

/* ---------------- JUMPER WIRES: header → buttons and encoder ---------------- */
const WIRES = [
  { pin: 33, to: 'anchor-red', color: '#e9645b' },
  { pin: 34, to: 'anchor-red', color: '#2b2f33' },
  { pin: 37, to: 'anchor-yellow', color: '#ffcc48' },
  { pin: 40, to: 'anchor-enc', color: '#7fe4b8' },
  { pin: 38, to: 'anchor-enc', color: '#3d8fd0' },
  { pin: 36, to: 'anchor-enc', color: '#f4ecd2' },
];
function Wires() {
  const scene = useThree((s) => s.scene);
  const lines = useRef<any[]>([]);
  const found = useRef(new Map<string, THREE.Object3D>());
  const [a, b, m] = useMemo(() => [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()], []);
  const get = (name: string) => {
    let o = found.current.get(name);
    if (!o) { o = scene.getObjectByName(name) ?? undefined; if (o) found.current.set(name, o); }
    return o;
  };
  useFrame(() => {
    WIRES.forEach((w, i) => {
      const line = lines.current[i], from = get('pin-' + w.pin), to = get(w.to);
      if (!line || !from || !to) return;
      from.getWorldPosition(a); to.getWorldPosition(b);
      m.lerpVectors(a, b, .5); m.z -= 12 + i * 1.5; m.y -= 5 + rig.explode * 10;
      line.setPoints(a, b, m);
    });
  });
  return (
    <>
      {WIRES.map((w, i) => (
        <QuadraticBezierLine key={i} ref={(el: any) => { lines.current[i] = el; }} start={[0, 0, 0]} end={[0, 0, 0]} color={w.color} lineWidth={2.4} />
      ))}
    </>
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
    <>
      <group ref={yaw}>
        <Body />
        <Lid />
        <Pi5 />
        <Panel />
        <Buttons />
        <Encoder />
      </group>
      <Wires />
    </>
  );
}
