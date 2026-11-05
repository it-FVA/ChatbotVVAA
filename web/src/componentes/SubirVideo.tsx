// (5/11, Julián) «Subir un video»: un video editado afuera (Premiere) entra como un recorte más. Lo usan Mis recortes y Diseñar.
import { useState } from "react";
import { api, ErrorApi } from "../api";
import Modal from "./Modal";

const MAX_MB = 200;

// (5/11, Franco) `archivoInicial`: Diseñar ya recibió el archivo en su zona de arrastrar, y acá solo se completan el título y el formato
export default function SubirVideo({ onCerrar, onSubido, archivoInicial = null }: { onCerrar: () => void; onSubido: (id: string | null) => void; archivoInicial?: File | null }) {
  const [archivo, setArchivo] = useState<File | null>(archivoInicial);
  const [titulo, setTitulo] = useState(archivoInicial ? archivoInicial.name.replace(/\.[^.]+$/, "").slice(0, 100) : "");
  const [formato, setFormato] = useState<"horizontal" | "vertical">("horizontal");
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState<string | null>(archivoInicial && archivoInicial.size > MAX_MB * 1024 * 1024 ? `El video pesa ${Math.round(archivoInicial.size / 1024 / 1024)} MB; el máximo es ${MAX_MB} MB.` : null);

  function elegir(f: File | null) {
    setError(null);
    setArchivo(f);
    if (f && f.size > MAX_MB * 1024 * 1024) setError(`El video pesa ${Math.round(f.size / 1024 / 1024)} MB; el máximo es ${MAX_MB} MB.`);
    if (f && !titulo) setTitulo(f.name.replace(/\.[^.]+$/, "").slice(0, 100));
  }

  async function subir() {
    if (!archivo) return;
    setSubiendo(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("archivo", archivo);
      form.append("titulo", titulo.trim());
      form.append("formato", formato);
      const r = await api.subirRecorte(form);
      onSubido(r.id);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude subir el video.");
      setSubiendo(false);
    }
  }

  const pasado = !!archivo && archivo.size > MAX_MB * 1024 * 1024;
  return (
    <Modal titulo="Subir un video" onCerrar={subiendo ? () => undefined : onCerrar}>
      <p className="suave chico">Un video propio (mp4 o mov, hasta {MAX_MB} MB), por ejemplo uno editado en Premiere. Queda como un recorte más: se puede diseñar, publicar, compartir y guardar en carpetas.</p>
      <label>
        Archivo
        <input type="file" accept="video/mp4,video/quicktime,.mp4,.mov" onChange={(e) => elegir(e.target.files?.[0] ?? null)} disabled={subiendo} />
      </label>
      <label>
        Título
        <input value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={200} disabled={subiendo} />
      </label>
      <fieldset className="opciones" disabled={subiendo}>
        <legend>Formato</legend>
        <label className="radio">
          <input type="radio" name="subir-formato" checked={formato === "horizontal"} onChange={() => setFormato("horizontal")} /> <span>Horizontal</span>
        </label>
        <label className="radio">
          <input type="radio" name="subir-formato" checked={formato === "vertical"} onChange={() => setFormato("vertical")} /> <span>Vertical</span>
        </label>
      </fieldset>
      {subiendo && <p className="suave chico" role="status">Subiendo… puede tardar unos minutos, no cierres esta ventana.</p>}
      {error && <div className="aviso error">{error}</div>}
      <div className="acciones" style={{ justifyContent: "flex-end" }}>
        <button className="boton" onClick={onCerrar} disabled={subiendo}>
          Cancelar
        </button>
        <button className="boton primario" onClick={subir} disabled={subiendo || !archivo || !titulo.trim() || pasado}>
          {subiendo ? "Subiendo…" : "Subir"}
        </button>
      </div>
    </Modal>
  );
}
