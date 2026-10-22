// Subtítulos por línea, sincronizados con el reproductor: clic en una línea salta a ese momento; se edita el texto, no el tiempo.
import { useEffect, useRef } from "react";
import type { Linea } from "../tipos";
import { srtASegundos } from "../util/tiempo";

interface Props {
  lineas: Linea[];
  actual: number; // índice de la línea que suena ahora (-1 si ninguna)
  onTexto: (i: number, texto: string) => void;
  onIr: (segundos: number) => void;
}

export default function Subtitulos({ lineas, actual, onTexto, onIr }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current?.querySelector<HTMLElement>(".sub-linea.actual");
    el?.scrollIntoView({ block: "nearest" });
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
    <div className="sub-lista" ref={ref}>
      {lineas.map((l, i) => (
        <div key={i} className={"sub-linea" + (i === actual ? " actual" : "") + (l.texto.trim() ? "" : " vacia")}>
          <button type="button" className="sub-tiempo" onClick={() => onIr(srtASegundos(l.inicio))} title="Ir a este momento">
            {l.inicio.slice(3, 8)} → {l.fin.slice(3, 8)}
          </button>
          <input value={l.texto} maxLength={80} onChange={(e) => onTexto(i, e.target.value)} onFocus={() => onIr(srtASegundos(l.inicio))} placeholder="(vacía: se saca)" />
        </div>
      ))}
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
