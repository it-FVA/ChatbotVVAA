// Tiempos: ms ↔ texto, SRT ↔ segundos, y el mapa entre la timeline del video actual y el original.

export function mmss(ms: number, decimales = 0): string {
  const t = Math.max(0, ms) / 1000;
  const m = Math.floor(t / 60);
  const s = t - m * 60;
  const sTxt = decimales ? s.toFixed(decimales).padStart(3 + decimales, "0") : String(Math.floor(s)).padStart(2, "0");
  return `${String(m).padStart(2, "0")}:${sTxt}`;
}

export function segundos(s: number): string {
  return s < 60 ? `${s.toFixed(1)} s` : `${(s / 60).toFixed(1)} min`;
}

/** 'HH:MM:SS,mmm' → segundos */
export function srtASegundos(t: string): number {
  const [h, m, resto] = t.trim().replace(".", ",").split(":");
  const [s, ms = "0"] = resto.split(",");
  return Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms.padEnd(3, "0").slice(0, 3)) / 1000;
}

/** Timeline del video actual: tramos [a, b] (segundos del tramo plano) que quedaron en el video, en orden.
 *  null = el video es el tramo plano entero (identidad). */
export type Timeline = number[][] | null;

/** segundo del video actual → segundo del tramo plano (relativo a inicio_ms del recorte) */
export function videoATramo(t: number, tl: Timeline): number {
  if (!tl || !tl.length) return t;
  let acum = 0;
  for (const [a, b] of tl) {
    const largo = b - a;
    if (t <= acum + largo) return a + (t - acum);
    acum += largo;
  }
  return tl[tl.length - 1][1];
}

/** segundo del tramo plano → segundo del video actual (si cae en un pedazo sacado, va al principio del pedazo que le sigue en el
 *  original). null si está fuera del video. (22/10) La timeline puede estar en otro orden que el original (pedazos reordenados). */
export function tramoAVideo(t: number, tl: Timeline, duracionVideo: number): number | null {
  if (!tl || !tl.length) return t >= 0 && t <= duracionVideo + 0.05 ? Math.min(t, duracionVideo) : null;
  let acum = 0;
  let siguiente: { a: number; acum: number } | null = null;
  for (const [a, b] of tl) {
    if (t >= a && t <= b) return acum + (t - a);
    if (t < a && (!siguiente || a < siguiente.a)) siguiente = { a, acum };
    acum += b - a;
  }
  return siguiente ? siguiente.acum : null;
}
