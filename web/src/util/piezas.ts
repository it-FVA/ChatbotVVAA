// Los pedazos del editor (22/10): funciones puras sobre dos cosas que van juntas.
//  · `piezas`: la partición del tramo [ini, fin] en el ORDEN DEL ORIGINAL (cada una conservada o sacada; entre todas cubren el tramo
//    sin huecos ni solapes). Es lo que se dibuja sobre el original.
//  · `orden`: los ids de las piezas conservadas en el ORDEN DE SALIDA (lo que se dibuja en la secuencia y lo que se manda como
//    `segmentos`: el orden de la lista es el orden en que salen en el video final).
import type { Pieza } from "../componentes/LineaTiempo";

export const MIN_PEDAZO_MS = 500;

let ultimoId = 0;
export function nuevoId(): number {
  ultimoId += 1;
  return ultimoId;
}

export interface Estado {
  piezas: Pieza[];
  orden: number[];
}

/** Los pedazos que se guardaron en clips.edicion (en orden de salida) → piezas sobre el original (con los huecos como sacadas) + orden. */
export function piezasIniciales(ini0: number, fin0: number, segmentos: number[][] | undefined | null): Estado {
  if (!segmentos || !segmentos.length) {
    const p = { id: nuevoId(), a: ini0, b: fin0, conservada: true };
    return { piezas: [p], orden: [p.id] };
  }
  const conservadas = segmentos.map(([a, b]) => ({ id: nuevoId(), a: Math.max(ini0, a), b: Math.min(fin0, b), conservada: true })).filter((p) => p.b > p.a);
  const orden = conservadas.map((p) => p.id);
  const piezas: Pieza[] = [];
  let t = ini0;
  for (const p of [...conservadas].sort((x, y) => x.a - y.a)) {
    if (p.a > t) piezas.push({ id: nuevoId(), a: t, b: p.a, conservada: false });
    piezas.push(p);
    t = p.b;
  }
  if (t < fin0) piezas.push({ id: nuevoId(), a: t, b: fin0, conservada: false });
  return { piezas, orden };
}

/** Deja `orden` consistente con `piezas`: saca los ids que ya no están o no se conservan y agrega los conservados que faltan,
 *  cada uno después del conservado que lo precede en el original (o al principio). */
export function sincronizarOrden(piezas: Pieza[], orden: number[]): number[] {
  const vivas = new Map(piezas.map((p) => [p.id, p]));
  let out = orden.filter((id) => vivas.get(id)?.conservada);
  for (const p of piezas) {
    if (!p.conservada || out.includes(p.id)) continue;
    const previa = [...piezas].filter((q) => q.conservada && q.b <= p.a && out.includes(q.id)).pop();
    const i = previa ? out.indexOf(previa.id) + 1 : 0;
    out = [...out.slice(0, i), p.id, ...out.slice(i)];
  }
  return out;
}

/** Parte la pieza que contiene `t` (a más de 300 ms de sus bordes) en dos; la segunda queda justo después en el orden. */
export function partirEn(e: Estado, t: number): Estado {
  const i = e.piezas.findIndex((p) => t > p.a + 300 && t < p.b - 300);
  if (i < 0) return e;
  const p = e.piezas[i];
  const nueva = { ...p, id: nuevoId(), a: t };
  const piezas = [...e.piezas.slice(0, i), { ...p, b: t }, nueva, ...e.piezas.slice(i + 1)];
  const j = e.orden.indexOf(p.id);
  const orden = p.conservada && j >= 0 ? [...e.orden.slice(0, j + 1), nueva.id, ...e.orden.slice(j + 1)] : e.orden;
  return { piezas, orden };
}

/** Conservar ↔ sacar. Una pieza restaurada vuelve a la secuencia cerca de donde está en el original. */
export function alternar(e: Estado, id: number): Estado {
  const piezas = e.piezas.map((p) => (p.id === id ? { ...p, conservada: !p.conservada } : p));
  return { piezas, orden: sincronizarOrden(piezas, e.orden) };
}

/** Un lugar antes (-1) o después (+1) en la secuencia. */
export function mover(e: Estado, id: number, dir: -1 | 1): Estado {
  const i = e.orden.indexOf(id);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= e.orden.length) return e;
  const orden = [...e.orden];
  [orden[i], orden[j]] = [orden[j], orden[i]];
  return { ...e, orden };
}

/** Nuevo inicio/fin para la pieza `id` sobre el original. No puede pisar a otra pieza conservada ni salir del tramo; sí puede
 *  comerse (o devolver) lo sacado que tiene al lado. Dura al menos MIN_PEDAZO_MS. La partición se rearma. */
export function recortar(e: Estado, id: number, a: number, b: number, ini: number, fin: number): Estado {
  const i = e.piezas.findIndex((p) => p.id === id);
  if (i < 0) return e;
  const p = e.piezas[i];
  // límites: la conservada más cercana a cada lado (o el tramo)
  let lo = ini, hi = fin;
  for (let k = i - 1; k >= 0; k--) if (e.piezas[k].conservada) { lo = e.piezas[k].b; break; }
  for (let k = i + 1; k < e.piezas.length; k++) if (e.piezas[k].conservada) { hi = e.piezas[k].a; break; }
  a = Math.round(Math.max(lo, Math.min(a, b - MIN_PEDAZO_MS)));
  b = Math.round(Math.min(hi, Math.max(b, a + MIN_PEDAZO_MS)));
  if (b - a < MIN_PEDAZO_MS || (a === p.a && b === p.b)) return e;
  // las sacadas de alrededor se achican (o se agrandan) para que la partición siga cubriendo el tramo
  const antes: Pieza[] = [], despues: Pieza[] = [];
  for (let k = 0; k < i; k++) {
    const q = e.piezas[k];
    if (q.b <= a) antes.push(q);
    else if (q.a < a) antes.push({ ...q, b: a });
  }
  if (p.a < a && (!antes.length || antes[antes.length - 1].b < a)) {
    const u = antes[antes.length - 1];
    if (u && !u.conservada) antes[antes.length - 1] = { ...u, b: a };
    else antes.push({ id: nuevoId(), a: u ? u.b : ini, b: a, conservada: false });
  }
  for (let k = i + 1; k < e.piezas.length; k++) {
    const q = e.piezas[k];
    if (q.a >= b) despues.push(q);
    else if (q.b > b) despues.push({ ...q, a: b });
  }
  if (p.b > b && (!despues.length || despues[0].a > b)) {
    const u = despues[0];
    if (u && !u.conservada) despues[0] = { ...u, a: b };
    else despues.unshift({ id: nuevoId(), a: b, b: u ? u.a : fin, conservada: false });
  }
  const piezas = [...antes, { ...p, a, b }, ...despues].filter((q) => q.b > q.a);
  return { piezas, orden: sincronizarOrden(piezas, e.orden) };
}

/** El tramo cambió a [a, b]: las piezas se recortan a él y, si creció, lo nuevo se suma a la pieza del borde. */
export function ajustarAlTramo(e: Estado, a: number, b: number): Estado {
  let out = e.piezas.map((p) => ({ ...p, a: Math.max(p.a, a), b: Math.min(p.b, b) })).filter((p) => p.b - p.a > 0);
  if (!out.length) {
    const p = { id: nuevoId(), a, b, conservada: true };
    return { piezas: [p], orden: [p.id] };
  }
  out[0] = { ...out[0], a };
  out[out.length - 1] = { ...out[out.length - 1], b };
  return { piezas: out, orden: sincronizarOrden(out, e.orden) };
}

/** Lo que se manda como `segmentos`: [[a, b], …] en orden de salida. Los consecutivos contiguos en el original se unen; si queda
 *  un solo pedazo que cubre el tramo entero, [] (= sin pedazos sacados ni movidos). */
export function segmentosDe(e: Estado, ini: number, fin: number): number[][] {
  const porId = new Map(e.piezas.map((p) => [p.id, p]));
  const out: number[][] = [];
  for (const id of e.orden) {
    const p = porId.get(id);
    if (!p) continue;
    const u = out[out.length - 1];
    if (u && u[1] === p.a) u[1] = p.b;
    else out.push([p.a, p.b]);
  }
  if (out.length === 1 && out[0][0] === ini && out[0][1] === fin) return [];
  return out;
}

/** ¿la secuencia está en otro orden que el original? */
export function reordenada(segmentos: number[][]): boolean {
  return segmentos.some((s, i) => i > 0 && s[0] < segmentos[i - 1][1]);
}
