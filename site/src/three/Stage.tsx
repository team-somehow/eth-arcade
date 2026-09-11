import { useMemo } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Environment, Lightformer, ContactShadows } from '@react-three/drei';
import { EffectComposer, Bloom, Noise, Vignette } from '@react-three/postprocessing';
import { Device } from './Device';
import { rig, KEYS } from './rig';
import { scroll } from '../scroll';

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const smooth = (t: number) => t * t * (3 - 2 * t);
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

/** Damps scroll into progress, blends the chapter keyframes, drives camera and explode. */
function CameraRig() {
  const camera = useThree((s) => s.camera);
  const look = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, delta) => {
    const dt = Math.min(.1, delta);
    rig.t += dt;
    rig.prog = rig.reduced ? scroll.target : lerp(rig.prog, scroll.target, 1 - Math.pow(.001, dt * 3.2));
    const f = rig.prog * (KEYS.length - 1);
    const i = Math.min(KEYS.length - 2, Math.floor(f));
    const u = smooth(clamp(f - i, 0, 1));
    const a = KEYS[i], b = KEYS[i + 1];
    rig.explode = lerp(a.ex, b.ex, u);
    camera.position.set(lerp(a.pos[0], b.pos[0], u), lerp(a.pos[1], b.pos[1], u), lerp(a.pos[2], b.pos[2], u));
    look.set(lerp(a.look[0], b.look[0], u), lerp(a.look[1], b.look[1], u), lerp(a.look[2], b.look[2], u));
    camera.lookAt(look);
  });
  return null;
}

export function Stage() {
  const light = useMemo(() => typeof matchMedia !== 'undefined' && matchMedia('(max-width: 900px)').matches, []);
  return (
    <Canvas
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.0 }}
      camera={{ fov: 30, near: 1, far: 3000, position: [-24, 26, 318] }}
      style={{ position: 'absolute', inset: 0 }}
    >
      <color attach="background" args={['#0C1924']} />
      <fog attach="fog" args={['#0C1924', 480, 1000]} />
      <hemisphereLight args={['#3d5c6c', '#0c1924', .6]} />
      <directionalLight color="#ffe0a3" intensity={1.6} position={[200, 240, 260]} />
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={4} color="#ffe6b0" position={[6, 4, 5]} scale={[9, 6, 1]} rotation-y={-.6} />
        <Lightformer form="rect" intensity={1.6} color="#8fe9c4" position={[-8, 1, 3]} scale={[3, 10, 1]} rotation-y={.7} />
        <Lightformer form="rect" intensity={2.5} color="#ffffff" position={[0, 7, -5]} scale={[10, 2, 1]} rotation-x={.6} />
        <Lightformer form="rect" intensity={1} color="#3d8fd0" position={[0, -6, 5]} scale={[10, 3, 1]} />
      </Environment>
      <Device />
      <ContactShadows position={[0, -86, 0]} opacity={.65} scale={360} blur={2.4} far={150} resolution={512} color="#000000" />
      <CameraRig />
      {!light && (
        <EffectComposer multisampling={4}>
          <Bloom mipmapBlur luminanceThreshold={.82} luminanceSmoothing={.25} intensity={.55} />
          <Noise premultiply opacity={.055} />
          <Vignette offset={.22} darkness={.85} />
        </EffectComposer>
      )}
    </Canvas>
  );
}
