/**
 * Shared, mutable per-frame state for the 3D stage. Written by the camera rig,
 * read by every part that explodes. Kept out of React state on purpose: it
 * changes every frame.
 */
export const rig = {
  /** damped scroll progress, 0..1 */
  prog: 0,
  /** 0 = assembled, 1 = fully exploded */
  explode: 0,
  /** seconds since the stage mounted */
  t: 0,
  /** reduced-motion preference */
  reduced: typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches,
};

/** Camera keyframes per chapter. The stage is its own framed field, so the
 * device stays centred in it and only the angle, the distance and the
 * explode change. */
export const KEYS: { pos: [number, number, number]; look: [number, number, number]; ex: number }[] = [
  { pos: [-105, 65, 320], look: [4, 0, 0], ex: 0 },       // hero: three-quarter, front lit
  { pos: [236, -4, 202], look: [24, -26, 4], ex: 0 },   // the dial: down the right face at the knob
  { pos: [-14, 34, 246], look: [2, 19, 6], ex: 0 },      // the game: close on the screen
  { pos: [372, 158, 452], look: [0, -8, -16], ex: 1 },     // exploded
  { pos: [-196, 26, -250], look: [0, 0, -10], ex: 0 },     // sound: back together, from the left
  { pos: [68, 20, 344], look: [16, 0, 0], ex: 0 },        // specs: a slow orbit back to front
];
