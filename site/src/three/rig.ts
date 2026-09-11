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

/** Camera keyframes per chapter. Copy alternates left/right, so the device parks on the other side. */
export const KEYS: { pos: [number, number, number]; look: [number, number, number]; ex: number }[] = [
  { pos: [-24, 26, 318], look: [-66, 4, 0], ex: 0 },      // hero: copy left, device right
  { pos: [280, -30, 170], look: [90, -30, -6], ex: 0 },   // the dial: right face
  { pos: [-16, 34, 178], look: [-48, 22, 20], ex: 0 },    // the game: close on the screen
  { pos: [225, 105, 265], look: [70, -2, -20], ex: 1 },   // exploded
  { pos: [-160, 44, 285], look: [-76, 0, 0], ex: 0 },     // sound: reassembled, from the left
  { pos: [44, 12, 340], look: [70, 0, 0], ex: 0 },        // specs: slow orbit
];
