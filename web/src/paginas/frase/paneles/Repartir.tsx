// Ventana «Repartir en el año».
import { diaIso } from "../../../util/fechas";
import { useState } from "react";
import { apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import Modal from "../../../componentes/Modal";
import { useToast } from "../../../componentes/Toasts";
import { mensajeDe } from "../comun";

// ---------------- Repartir y agregar ----------------
export function Repartir({ hoy, sinDia, onCerrar, onHecho }: { hoy: string; sinDia: number; onCerrar: () => void; onHecho: (msg: string) => void }) {
  const { avisar } = useToast();
  const [modo, setModo] = useState<"orden" | "azar">("orden");
  const [desde, setDesde] = useState(() => diaIso(new Date(new Date(hoy + "T12:00:00").getTime() + 86400000)));
  const [ocupado, setOcupado] = useState(false);
  async function ir() {
    setOcupado(true);
    try {
      onHecho((await apiFrases.repartir(modo, desde)).mensaje);
    } catch (e) {
      avisar(mensajeDe(e), "error");
      setOcupado(false);
    }
  }
  return (
    <Modal titulo="Repartir en el año" onCerrar={onCerrar} ancho={520}>
      <p className="suave chico">
        Asigna un día a cada frase candidata a partir de la fecha elegida: primero las nunca publicadas ({sinDia} validadas sin día); cuando se acaban, siguen las ya publicadas de la más antigua a la más reciente. Las fechas que ya tienen frase no se tocan.
      </p>
      <div className="fd-form">
        <label>
          Orden
          <select value={modo} onChange={(e) => setModo(e.target.value as "orden" | "azar")}>
            <option value="orden">En el orden del Sheet</option>
            <option value="azar">Al azar (sin repetir autor dos días seguidos)</option>
          </select>
        </label>
        <label>
          A partir del
          <input type="date" value={desde} min={hoy} onChange={(e) => setDesde(e.target.value)} />
        </label>
      </div>
      <div className="acciones" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="boton" onClick={onCerrar} disabled={ocupado}>
          Cancelar
        </button>
        <button type="button" className="boton primario" onClick={ir} disabled={ocupado || !desde}>
          <Icono nombre="calendario" tam={15} /> {ocupado ? "Repartiendo…" : "Repartir"}
        </button>
      </div>
    </Modal>
  );
}
