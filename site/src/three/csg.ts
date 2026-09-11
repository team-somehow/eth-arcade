import * as THREE from 'three';
import { Brush, Evaluator, SUBTRACTION } from 'three-bvh-csg';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

const evaluator = new Evaluator();
evaluator.useGroups = false;

/**
 * Subtract a set of cutter geometries (already positioned in the base's local
 * space) from a base geometry. The cutters are merged into one brush first, so
 * a lid with sixty-three grille slots costs one boolean, not sixty-three.
 */
export function cut(base: THREE.BufferGeometry, cutters: THREE.BufferGeometry[]): THREE.BufferGeometry {
  if (!cutters.length) return base;
  const merged = mergeGeometries(cutters, false);
  if (!merged) return base;
  const a = new Brush(base);
  const b = new Brush(merged);
  a.updateMatrixWorld();
  b.updateMatrixWorld();
  const out = evaluator.evaluate(a, b, SUBTRACTION);
  const g = out.geometry;
  g.computeVertexNormals();
  return g;
}

/** A box already translated (and optionally rotated) into place, ready to be a cutter. */
export function box(w: number, h: number, d: number, x: number, y: number, z: number, rotY = 0): THREE.BufferGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  if (rotY) g.rotateY(rotY);
  g.translate(x, y, z);
  return g;
}
