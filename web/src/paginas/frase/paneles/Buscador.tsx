// Buscador entre las validadas sin día (lo usan «Cambiar por otra», asignar a un día libre y «Pedir un cambio»).
import { useEffect, useState } from "react";
import { type Frase, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { recortar } from "../comun";

/** Buscador entre las validadas sin día (frases_ui._buscador). */
export function Buscador({ excluir, textoBoton, ocupado, onElegir }: { excluir?: string; textoBoton: string; ocupado: boolean; onElegir: (f: Frase) => void }) {
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<Frase[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => {
    const t = window.setTimeout(() => apiFrases.backlog(q).then((b) => setLista(b.sin_dia.filter((x) => x.id !== excluir).slice(0, 30))).catch(() => setLista([])), 200);
    return () => window.clearTimeout(t);
  }, [q, excluir]);
  const elegida = lista?.find((x) => x.id === sel) ?? null;
  return (
    <div className="fd-form">
      <label className="buscar">
        <Icono nombre="buscar" tam={16} />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar entre las validadas sin día (texto o autor)" aria-label="Buscar frase" />
      </label>
      {lista && lista.length === 0 && <p className="suave chico">No hay frases sin día que coincidan.</p>}
      {lista && lista.length > 0 && (
        <ul className="fd-lista fd-elegir" role="listbox" aria-label="Frases">
          {lista.map((x) => (
            <li key={x.id} role="option" aria-selected={sel === x.id} className={"fd-item" + (sel === x.id ? " elegida" : "")} onClick={() => setSel(x.id)}>
              <span className="fd-texto">{recortar(x.texto, 120)}</span>
              <span className="suave chico">{x.autor}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="acciones">
        <button type="button" className="boton primario" disabled={ocupado || !elegida} onClick={() => elegida && onElegir(elegida)}>
          <Icono nombre="check" tam={15} /> {textoBoton}
        </button>
      </div>
    </div>
  );
}
