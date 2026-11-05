// (5/11, Franco) Registro único de la ayuda. Cada pantalla declara su ayuda arriba de su componente con `definirAyuda` y marca en el
// JSX cada elemento que explica con data-ayuda="<pantalla>.<id>". De acá sale la guía interactiva («¿Cómo se usa?»); la página /ayuda se fue el 5/11.
// El orden de los pasos es el orden del recorrido. Un paso sin `id` no apunta a un elemento (p. ej. «tardan 15 minutos»): en la
// página es un texto más y en la guía es un cartelito general.
// Lo vigilan src/ayuda/registro.test.tsx (contra el DOM de cada pantalla) y scripts/verificar-ayuda.mjs (contra el código).
//
//   definirAyuda("recortes", {
//     titulo: "Mis recortes",
//     que: "…",
//     pasos: [{ id: "subir", texto: "…" }, { texto: "Un paso sin elemento." }],
//   });
//   <button data-ayuda="recortes.subir">…</button>

export interface PasoAyuda {
  /** Identifica el elemento: data-ayuda="<pantalla>.<id>". Sin id, el paso no apunta a nada. */
  id?: string;
  texto: string;
  /** Título del cartelito en la guía. Si falta, se usa el texto del botón o «Paso n». */
  titulo?: string;
}

export interface DefAyuda {
  titulo: string;
  que: string;
  /** Una línea por canal u opción, entre «qué es» y el paso a paso. */
  lista?: string[];
  pasos: PasoAyuda[];
}

const REGISTRO = new Map<string, DefAyuda>();

export function definirAyuda(pantalla: string, def: DefAyuda) {
  REGISTRO.set(pantalla, def);
}

export function ayudaDe(pantalla: string): DefAyuda | undefined {
  return REGISTRO.get(pantalla);
}

/** Todas las pantallas registradas, en el orden en que se importaron (ver ayuda/index.ts). */
export function todasLasAyudas(): [string, DefAyuda][] {
  return [...REGISTRO.entries()];
}

export const valorAyuda = (pantalla: string, id: string) => `${pantalla}.${id}`;
export const selectorAyuda = (pantalla: string, id: string) => `[data-ayuda="${pantalla}.${id}"]`;
