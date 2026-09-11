import { useEffect, useState } from 'react';

/** Six viewport-tall chapters drive the 3D stage. */
export const CHAPTERS = 6;

/** Continuous scroll progress through the film, 0..1. Read every frame by the stage. */
export const scroll = { target: 0 };

let film: HTMLElement | null = null;
let chapter = 0;
const listeners = new Set<(c: number) => void>();

function read() {
  if (!film) return;
  const r = film.getBoundingClientRect();
  const total = Math.max(1, film.offsetHeight - window.innerHeight);
  scroll.target = Math.max(0, Math.min(1, -r.top / total));
  const c = Math.round(scroll.target * (CHAPTERS - 1));
  if (c !== chapter) {
    chapter = c;
    listeners.forEach((l) => l(c));
  }
}

export function bindFilm(el: HTMLElement | null) {
  film = el;
  read();
}

export function onChapter(fn: (c: number) => void) {
  listeners.add(fn);
  fn(chapter);
  return () => {
    listeners.delete(fn);
  };
}

/** The chapter currently centred in the viewport (0..5). Changes rarely, so it is React state. */
export function useChapter() {
  const [c, set] = useState(chapter);
  useEffect(() => onChapter(set), []);
  return c;
}

if (typeof window !== 'undefined') {
  addEventListener('scroll', read, { passive: true });
  addEventListener('resize', read);
}
