// «Mover a…» / «Guardar en un proyecto» (22/10): modal con el árbol de carpetas donde la persona puede agregar cosas
// (las propias y las compartidas con permiso «editar»), buscador y «Nueva carpeta» ahí mismo. Es la alternativa táctil al arrastre.
import { useMemo, useState } from "react";
import { apiProyectos } from "../../apiProyectos";
import { ErrorApi } from "../../api";
import { Icono } from "../Iconos";
import Modal from "../Modal";
import { useToast } from "../Toasts";
import { aplanar, etiqueta, useProyectos, type NodoProyecto } from "./ProyectosContexto";

interface Props {
  titulo?: string;
  /** Lo que se está moviendo (para el texto). */
  que: string;
  /** Carpeta donde está ahora (se marca y no se ofrece). */
  actualId?: string | null;
  /** Carpetas que no se pueden elegir (p. ej. una carpeta no puede ir adentro de sí misma). */
  excluir?: string[];
  textoBoton?: string;
  onElegir: (proyectoId: string) => Promise<void>;
  onCerrar: () => void;
}

export default function MoverA({ titulo = "Mover a…", que, actualId, excluir = [], textoBoton = "Mover acá", onElegir, onCerrar }: Props) {
  const { arbol, recargar } = useProyectos();
  const { avisar } = useToast();
  const [buscar, setBuscar] = useState("");
  const [elegido, setElegido] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const [nueva, setNueva] = useState<string | null>(null); // null = cerrado; "" = escribiendo
  const [creando, setCreando] = useState(false);

  const filas = useMemo(() => {
    const todas = aplanar(arbol).filter((n) => n.permiso !== "ver");
    const q = buscar.trim().toLowerCase();
    return q ? todas.filter((n) => n.nombre.toLowerCase().includes(q)) : todas;
  }, [arbol, buscar]);

  async function confirmar() {
    if (!elegido) return;
    setTrabajando(true);
    try {
      await onElegir(elegido);
      onCerrar();
    } catch {
      /* quien llama ya avisó */
    } finally {
      setTrabajando(false);
    }
  }

  async function crearCarpeta() {
    const nombre = (nueva || "").trim();
    if (!nombre) return;
    setCreando(true);
    try {
      const p = await apiProyectos.crear({ nombre, padre_id: elegido || null });
      await recargar();
      setElegido(p.id);
      setNueva(null);
      avisar(`Carpeta «${p.nombre}» creada.`);
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude crear la carpeta.", "error");
    } finally {
      setCreando(false);
    }
  }

  const deshabilitada = (n: NodoProyecto) => n.id === actualId || excluir.includes(n.id);

  return (
    <Modal titulo={titulo} onCerrar={() => (trabajando ? null : onCerrar())} ancho={480}>
      <p className="suave chico" style={{ marginTop: 0 }}>
        {que}
      </p>
      <div className="buscar" style={{ maxWidth: "none" }}>
        <Icono nombre="buscar" tam={16} />
        <input type="search" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar carpeta" aria-label="Buscar carpeta" />
      </div>
      <ul className="mover-lista" role="listbox" aria-label="Carpetas">
        {filas.length === 0 && <li className="suave chico" style={{ padding: 10 }}>{buscar ? "Ninguna carpeta coincide." : "Todavía no tenés carpetas: creá la primera acá abajo."}</li>}
        {filas.map((n) => (
          <li key={n.id} role="option" aria-selected={elegido === n.id}>
            <button type="button" className={"mover-opcion" + (elegido === n.id ? " elegida" : "")} style={{ paddingLeft: 10 + (buscar ? 0 : n.nivel) * 18 }} disabled={deshabilitada(n)} onClick={() => setElegido(n.id)} title={n.id === actualId ? "Ya está acá" : undefined}>
              <Icono nombre="carpeta" tam={16} style={{ color: n.color || "var(--amarillo-oscuro)" }} />
              <span className="mover-nombre">{etiqueta(n)}</span>
              {n.permiso !== "dueño" && <span className="chip suave">{n.compartido_por ? `de ${n.compartido_por}` : "compartida"}</span>}
              {n.id === actualId && <span className="chip">acá</span>}
            </button>
          </li>
        ))}
      </ul>
      {nueva === null ? (
        <button type="button" className="boton sutil chico" onClick={() => setNueva("")}>
          <Icono nombre="carpetaMas" tam={16} /> Nueva carpeta{elegido ? " adentro de la elegida" : ""}
        </button>
      ) : (
        <form
          className="mover-nueva"
          onSubmit={(e) => {
            e.preventDefault();
            crearCarpeta();
          }}
        >
          <input autoFocus value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Nombre de la carpeta" aria-label="Nombre de la carpeta nueva" maxLength={80} />
          <button type="submit" className="boton chico" disabled={creando || !nueva.trim()}>
            {creando ? "…" : "Crear"}
          </button>
          <button type="button" className="boton sutil chico" onClick={() => setNueva(null)}>
            Cancelar
          </button>
        </form>
      )}
      <div className="acciones" style={{ justifyContent: "flex-end", marginTop: 12 }}>
        <button type="button" className="boton" onClick={onCerrar} disabled={trabajando}>
          Cancelar
        </button>
        <button type="button" className="boton primario" onClick={confirmar} disabled={!elegido || trabajando}>
          <Icono nombre="carpeta" tam={16} /> {trabajando ? "…" : textoBoton}
        </button>
      </div>
    </Modal>
  );
}
