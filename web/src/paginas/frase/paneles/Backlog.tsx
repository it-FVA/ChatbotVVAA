// Panel «Backlog»: validadas sin día (arrastrables) y pendientes de validación.
import { useEffect, useState } from "react";
import { type Backlog, type Frase, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { type Arrastre, empezarArrastre, recortar } from "../comun";

// ---------------- Backlog ----------------
export function BacklogPanel({ version, arrastrando, soloLectura, onArrastrar, onSoltarArrastre, onElegir }: { version: number; arrastrando: boolean; soloLectura?: boolean; onArrastrar: (a: Arrastre) => void; onSoltarArrastre: () => void; onElegir: (f: Frase) => void }) {
  const [q, setQ] = useState("");
  const [datos, setDatos] = useState<Backlog | null>(null);
  const [solapa, setSolapa] = useState<"sin_dia" | "pendientes">("sin_dia");
  useEffect(() => {
    const t = window.setTimeout(() => apiFrases.backlog(q).then(setDatos).catch(() => setDatos({ sin_dia: [], sin_dia_total: 0, pendientes: [], pendientes_total: 0 })), 250);
    return () => window.clearTimeout(t);
  }, [q, version]);
  const lista = datos ? (solapa === "sin_dia" ? datos.sin_dia : datos.pendientes) : null;
  return (
    <details className={"tarjeta fd-panel fd-backlog" + (arrastrando ? " arrastrando" : "")} open>
      <summary>
        <Icono nombre="chevron" tam={16} /> <Icono nombre="pelicula" tam={16} /> Frases sin día
        {datos && (
          <span className="suave chico">
            {" "}
            · {datos.sin_dia_total} sin día · {datos.pendientes_total} pendientes
          </span>
        )}
      </summary>
      <div className="fd-panel-cuerpo">
        <label className="buscar">
          <Icono nombre="buscar" tam={16} />
          <input type="search" placeholder="Buscar por texto o autor" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar en el backlog" />
        </label>
        <div className="solapas chico" role="tablist">
          <button role="tab" aria-selected={solapa === "sin_dia"} className={"solapa" + (solapa === "sin_dia" ? " activa" : "")} onClick={() => setSolapa("sin_dia")}>
            Validadas sin día {datos ? `(${datos.sin_dia_total})` : ""}
          </button>
          <button role="tab" aria-selected={solapa === "pendientes"} className={"solapa" + (solapa === "pendientes" ? " activa" : "")} onClick={() => setSolapa("pendientes")}>
            Pendientes {datos ? `(${datos.pendientes_total})` : ""}
          </button>
        </div>
        {solapa === "pendientes" && <p className="suave chico">Las nuevas del Sheet esperan el OK de Pato: no se pueden asignar hasta que estén validadas (se marcan en el Sheet y se vuelve a correr importar_frases.py).</p>}
        {solapa === "sin_dia" && <p className="suave chico">{soloLectura ? "Las validadas que todavía no tienen día. Para pedir que una salga un día, abrí ese día en el calendario." : "Arrastrá una frase a un día del calendario para asignarla (si el día está ocupado, la reemplaza y esa vuelve acá)."}</p>}
        <ul className="fd-lista">
          {lista === null && <li className="suave chico">Cargando…</li>}
          {lista && lista.length === 0 && <li className="suave chico">{q ? "Nada que coincida." : solapa === "sin_dia" ? "No hay validadas sin día: están todas en el calendario." : "No hay pendientes."}</li>}
          {lista?.map((f) => (
            <li
              key={f.id}
              className={"fd-item" + (solapa === "sin_dia" && !soloLectura ? " arrastrable" : "")}
              draggable={solapa === "sin_dia" && !soloLectura}
              onDragStart={(e) => solapa === "sin_dia" && !soloLectura && empezarArrastre(e, { id: f.id, desde: null, texto: f.texto }, onArrastrar)}
              onDragEnd={onSoltarArrastre}
              onClick={() => onElegir(f)}
              title={soloLectura ? (solapa === "sin_dia" ? "Validada, sin día todavía" : "Pendiente de validación") : solapa === "sin_dia" ? "Arrastrá a un día del calendario" : "Pendiente de validación"}
            >
              <span className="fd-texto">{recortar(f.texto, 140)}</span>
              <span className="suave chico">
                {f.autor}
                {f.veces_publicada ? ` · ↻ salió ${f.veces_publicada} ${f.veces_publicada === 1 ? "vez" : "veces"}` : ""}
                {solapa === "pendientes" ? " · 🕓 pendiente" : ""}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
