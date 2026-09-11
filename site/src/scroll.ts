import { useSyncExternalStore } from 'react';

/** Six viewport-tall chapters drive the 3D stage. */
export const CHAPTERS = 6;

/** Continuous scroll progress through the film, 0..1. Read every frame by the stage. */
export const scroll = { target: 0 };

let film: HTMLElement | null = null;
let chapter = 0;
const listeners = new Set<() => void>();

function read() {
  if (!film) return;
  const r = film.getBoundingClientRect();
  const total = Math.max(1, film.offsetHeight - window.innerHeight);
  scroll.target = Math.max(0, Math.min(1, -r.top / total));
  const c = Math.round(scroll.target * (CHAPTERS - 1));
  if (c !== chapter) {
    chapter = c;
    listeners.forEach((l) => l());
  }
}

export function bindFilm(el: HTMLElement | null) {
  if (el) film = el;     // a ref detach must not unbind the film that is still on screen
  read();
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

/**
 * The chapter currently centred in the viewport (0..5). An external store
 * rather than an effect-and-setState pair: the value is written by a scroll
 * listener that runs before React mounts and between its strict-mode
 * remounts, and a subscription that is torn down at the wrong moment leaves
 * the whole page frozen on chapter 0.
 */
export function useChapter() {
  return useSyncExternalStore(subscribe, () => chapter, () => 0);
}

if (typeof window !== 'undefined') {
  (window as any).__scrollmod = ((window as any).__scrollmod || 0) + 1;
  (window as any).__readinfo = () => ({ target: scroll.target, chapter, film: !!film, listeners: listeners.size });
  addEventListener('scroll', read, { passive: true });
  addEventListener('resize', read);
}
