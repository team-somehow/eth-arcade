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
      shadows
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance', toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.08 }}
      camera={{ fov: 30, near: 1, far: 3000, position: [-34, 30, 300] }}
      style={{ position: 'absolute', inset: 0 }}
    >
      <color attach="background" args={['#070F17']} />
      <fog attach="fog" args={['#070F17', 460, 1100]} />
      {/* a dim room, one warm key, a cool rim down the right edge and a low fill */}
      <hemisphereLight args={['#31505f', '#05090d', .45]} />
      <directionalLight
        color="#fff1cf"
        intensity={2.1}
        position={[-150, 250, 240]}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-near={80}
        shadow-camera-far={700}
        shadow-camera-left={-160}
        shadow-camera-right={160}
        shadow-camera-top={160}
        shadow-camera-bottom={-160}
        shadow-bias={-0.0009}
      />
      <directionalLight color="#cfe6ff" intensity={.55} position={[260, 60, -180]} />
      <directionalLight color="#3d6a86" intensity={.5} position={[0, -180, 120]} />
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={5} color="#fff0cc" position={[-7, 5, 6]} scale={[10, 7, 1]} rotation-y={.5} />
        <Lightformer form="rect" intensity={1.5} color="#dcefff" position={[9, 2, -3]} scale={[3, 12, 1]} rotation-y={-.8} />
        <Lightformer form="rect" intensity={2.2} color="#ffffff" position={[0, 8, -4]} scale={[12, 2, 1]} rotation-x={.7} />
        <Lightformer form="rect" intensity={.9} color="#3d8fd0" position={[0, -7, 5]} scale={[12, 3, 1]} />
      </Environment>
      <Device />
      <ContactShadows position={[0, -62, 6]} opacity={.55} scale={300} blur={2.8} far={120} resolution={768} color="#000000" />
      <CameraRig />
      {!light && (
        <EffectComposer multisampling={4}>
          <Bloom mipmapBlur luminanceThreshold={.8} luminanceSmoothing={.22} intensity={.5} />
          <Noise premultiply opacity={.045} />
          <Vignette offset={.2} darkness={.8} />
        </EffectComposer>
      )}
    </Canvas>
  );
}
