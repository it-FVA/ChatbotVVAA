// Solapa «Texto» del detalle del día.
import { useEffect, useState } from "react";
import { type Frase, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import type { PropsSolapa } from "./index";

export function EditarTexto({ f, ocupado, onGuardar }: { f: Frase; ocupado: boolean; onGuardar: (texto: string, autor: string) => void }) {
  const [texto, setTexto] = useState(f.texto);
  const [autor, setAutor] = useState(f.autor || "");
  useEffect(() => {
    setTexto(f.texto);
    setAutor(f.autor || "");
  }, [f]);
  const sinCambios = texto.trim() === f.texto && autor.trim() === (f.autor || "");
  return (
    <div className="fd-form">
      <label>
        Frase
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={4} />
      </label>
      <label>
        Autor
        <input value={autor} onChange={(e) => setAutor(e.target.value)} />
      </label>
      <div className="acciones">
        <button type="button" className="boton primario" onClick={() => onGuardar(texto, autor)} disabled={ocupado || sinCambios || !texto.trim()}>
          <Icono nombre="check" tam={15} /> Guardar el texto
        </button>
      </div>
    </div>
  );
}

export default function Texto({ f, ocupado, correr }: PropsSolapa) {
  return <EditarTexto f={f} ocupado={ocupado} onGuardar={(texto, autor) => correr(async () => ((await apiFrases.editar(f.id, { texto, autor })), "Guardado."))} />;
}
