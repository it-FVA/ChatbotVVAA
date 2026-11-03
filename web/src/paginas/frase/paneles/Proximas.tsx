// Panel «Próximas 14 días».
import type { Proxima } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { fechaCorta, recortar } from "../comun";

// ---------------- Próximas 14 días ----------------
export function Proximas({ lista, onElegir }: { lista: Proxima[] | null; onElegir: (f: string) => void }) {
  return (
    <details className="tarjeta fd-panel" open>
      <summary>
        <Icono nombre="chevron" tam={16} /> <Icono nombre="reloj" tam={16} /> Próximas 14 días
      </summary>
      <ul className="fd-proximas">
        {lista === null && <li className="suave chico">Cargando…</li>}
        {lista?.map((p) => (
          <li key={p.fecha} className={p.frase ? p.frase.estado : "libre"}>
            <button type="button" onClick={() => onElegir(p.fecha)} title="Ver el día">
              <span className="fd-prox-fecha">
                {p.dia.slice(0, 2)} {fechaCorta(p.fecha)}
              </span>
              {p.frase ? (
                <span className="fd-prox-texto">
                  {recortar(p.frase.texto, 80)} <em className="suave">— {p.frase.autor}</em>
                  <span className="fd-prox-estado chico suave">
                    {" "}
                    · {p.frase.estado === "saltada" ? "⏭ salteada" : p.frase.estado}
                    {p.frase.repetida ? " ↻" : ""}
                  </span>
                </span>
              ) : (
                <span className="fd-prox-texto suave">
                  <em>sin frase (la cola asigna la siguiente de la rotación)</em>
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
