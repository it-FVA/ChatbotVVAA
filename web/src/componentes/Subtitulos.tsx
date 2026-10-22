// Subtítulos por línea, sincronizados con el reproductor: la que suena se resalta y la lista la sigue; clic en el tiempo salta a
// ese momento; se edita el texto, no el tiempo. Contador de caracteres por línea con aviso cuando puede ocupar tres renglones.
import { useEffect, useRef } from "react";
import type { Linea } from "../tipos";
import { srtASegundos } from "../util/tiempo";
import { Icono } from "./Iconos";

interface Props {
  lineas: Linea[];
  actual: number; // índice de la línea que suena ahora (-1 si ninguna)
  onTexto: (i: number, texto: string) => void;
  onIr: (segundos: number) => void;
}

// SUPUESTO (no medido con libass): en vertical, con el tamaño «normal», entran unos 26 caracteres por renglón; a partir de
// dos renglones (52) la línea suele pasar a tres y tapa demasiado. Ajustar mirando recortes reales.
export const MAX_POR_RENGLON = 26;
export const MAX_DOS_RENGLONES = MAX_POR_RENGLON * 2;

export default function Subtitulos({ lineas, actual, onTexto, onIr }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // desplaza solo la lista (scrollIntoView movería la página entera)
    const lista = ref.current;
    const el = lista?.querySelector<HTMLElement>(".sub-linea.actual");
    if (!lista || !el) return;
    const arriba = el.offsetTop - lista.offsetTop;
    const abajo = arriba + el.offsetHeight;
    if (arriba < lista.scrollTop) lista.scrollTo({ top: arriba - 4, behavior: "smooth" });
    else if (abajo > lista.scrollTop + lista.clientHeight) lista.scrollTo({ top: abajo - lista.clientHeight + 4, behavior: "smooth" });
  }, [actual]);

  if (!lineas.length) {
    return (
      <p className="suave chico">
        Este recorte se hizo antes de que guardáramos los subtítulos, así que no se pueden corregir todavía. Si lo regenerás (por el tramo, los pedazos o
        el estilo), se arman de nuevo y quedan editables.
      </p>
    );
  }
  return (
    <div className="sub-lista" ref={ref} role="list">
      {lineas.map((l, i) => {
        const n = l.texto.length;
        const largo = n > MAX_DOS_RENGLONES;
        return (
          <div key={i} role="listitem" className={"sub-linea" + (i === actual ? " actual" : "") + (l.texto.trim() ? "" : " vacia") + (largo ? " larga" : "")}>
            <button type="button" className="sub-tiempo" onClick={() => onIr(srtASegundos(l.inicio))} title="Ir a este momento">
              {i === actual && <Icono nombre="reproducir" tam={10} relleno />}
              {l.inicio.slice(3, 8)}
            </button>
            <div className="sub-campo">
              <input
                value={l.texto}
                maxLength={80}
                onChange={(e) => onTexto(i, e.target.value)}
                onFocus={() => onIr(srtASegundos(l.inicio))}
                placeholder="(vacía: se saca)"
                aria-label={`Línea ${i + 1}, de ${l.inicio.slice(3, 8)} a ${l.fin.slice(3, 8)}`}
                aria-describedby={largo ? `sub-aviso-${i}` : undefined}
              />
              <span className={"sub-contador" + (largo ? " alerta" : "")} title={largo ? "Puede ocupar tres renglones en el video" : "Caracteres (dos renglones ≈ 52)"}>
                {n}
              </span>
            </div>
            {largo && (
              <span id={`sub-aviso-${i}`} className="sub-aviso">
                <Icono nombre="alerta" tam={12} /> Larga: puede ocupar 3 renglones
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Índice de la línea que corresponde al segundo t (-1 si ninguna). */
export function lineaEn(lineas: Linea[], t: number): number {
  for (let i = 0; i < lineas.length; i++) {
    if (t >= srtASegundos(lineas[i].inicio) && t < srtASegundos(lineas[i].fin)) return i;
  }
  return -1;
}
