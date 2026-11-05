// Elegir una foto: buscar en el banco de WordPress o pegar una URL. Lo usan la solapa «Foto de fondo» y «Pedir un cambio».
import { useState } from "react";
import { apiChat } from "../../../apiChat";
import { AvisoBanco } from "../../../componentes/Comunes";
import { Icono } from "../../../componentes/Iconos";
import type { FotoBanco } from "../../../tiposChat";



/** (2/11 tarde) Elegir una foto: buscar en el banco de WordPress o pegar una URL. `actual` es la elegida hoy; onElegir(null) = sacarla.
 *  Lo usan los aprobadores (FotoFondo, guarda en la frase) y los creadores (SolicitarCambio, la proponen). */
export function ElegirFoto({ actual, ocupado, textoQuitar, onElegir }: { actual: string | null; ocupado: boolean; textoQuitar: string; onElegir: (url: string | null) => void }) {
  const [q, setQ] = useState("");
  const [fotos, setFotos] = useState<FotoBanco[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [url, setUrl] = useState("");
  async function buscar() {
    setBuscando(true);
    try {
      setFotos(await apiChat.banco(q.trim(), "cuadrado"));
    } catch {
      setFotos([]);
    } finally {
      setBuscando(false);
    }
  }
  return (
    <>
      {actual && (
        <div className="fd-foto-actual">
          <img src={actual} alt="Foto elegida" />
          <button type="button" className="boton chico" onClick={() => onElegir(null)} disabled={ocupado}>
            {textoQuitar}
          </button>
        </div>
      )}
      <div className="campo-con-boton">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en el banco: ej. amanecer montaña calma" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscar())} aria-label="Buscar en el banco" />
        <button type="button" className="boton" onClick={buscar} disabled={buscando}>
          <Icono nombre="buscar" tam={15} /> {buscando ? "Buscando…" : "Buscar"}
        </button>
      </div>
      <AvisoBanco fotos={fotos} />
      {fotos && fotos.length === 0 && !buscando && <p className="suave chico">El banco no devolvió nada para esa búsqueda.</p>}
      {fotos && fotos.length > 0 && (
        <div className="pieza-fotos">
          {fotos.map((x) => (
            <button key={x.id} type="button" className={"pieza-foto" + (actual === x.url ? " elegida" : "")} onClick={() => onElegir(x.url)} disabled={ocupado} title={x.titulo || `#${x.id}`}>
              <img src={x.miniatura} alt={x.titulo || ""} loading="lazy" />
              <span className="chico">{(x.titulo || `#${x.id}`).slice(0, 28)}</span>
            </button>
          ))}
        </div>
      )}
      <div className="campo-con-boton">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="…o pegá la URL de una imagen que ya está en internet" aria-label="URL de la foto" />
        <button type="button" className="boton" disabled={ocupado || !url.trim()} onClick={() => (onElegir(url.trim()), setUrl(""))}>
          Usar esa URL
        </button>
      </div>
    </>
  );
}
