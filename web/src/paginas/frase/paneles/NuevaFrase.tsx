// Ventana «Agregar una frase».
import { useState } from "react";
import { apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import Modal from "../../../componentes/Modal";
import { useToast } from "../../../componentes/Toasts";
import { mensajeDe } from "../comun";

export function NuevaFrase({ onCerrar, onHecha }: { onCerrar: () => void; onHecha: () => void }) {
  const { avisar } = useToast();
  const [texto, setTexto] = useState("");
  const [autor, setAutor] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function agregar() {
    setOcupado(true);
    try {
      await apiFrases.crear(texto.trim(), autor.trim());
      onHecha();
    } catch (e) {
      avisar(mensajeDe(e), "error");
      setOcupado(false);
    }
  }
  return (
    <Modal titulo="Agregar una frase" onCerrar={onCerrar} ancho={520}>
      <p className="suave chico">Queda validada y sin día; después la asignás desde «Frases sin día» o soltándola en un día libre.</p>
      <div className="fd-form">
        <label>
          Frase
          <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={4} />
        </label>
        <label>
          Autor
          <input value={autor} onChange={(e) => setAutor(e.target.value)} placeholder="Brother David" />
        </label>
      </div>
      <div className="acciones" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="boton" onClick={onCerrar} disabled={ocupado}>
          Cancelar
        </button>
        <button type="button" className="boton primario" onClick={agregar} disabled={ocupado || !texto.trim()}>
          <Icono nombre="mas" tam={15} /> Agregar
        </button>
      </div>
    </Modal>
  );
}
