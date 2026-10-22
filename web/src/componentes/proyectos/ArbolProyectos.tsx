// Árbol de proyectos de la barra lateral del chat (22/10): carpetas plegables con subcarpetas, encima de «Conversaciones».
// Se arrastra una conversación de la lista a una carpeta (HTML5 drag and drop; el tipo de dato es "application/x-fva-conversacion")
// y también se mueven carpetas entre sí. «Nueva carpeta» acá mismo, «Agrandar» abre la vista grande (/proyectos) y el
// icono de compartido marca las carpetas compartidas (mías con otros, o de otros conmigo).
import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiProyectos } from "../../apiProyectos";
import { ErrorApi } from "../../api";
import { Icono } from "../Iconos";
import { useToast } from "../Toasts";
import { etiqueta, useProyectos, type NodoProyecto } from "./ProyectosContexto";

export const TIPO_ARRASTRE_CONV = "application/x-fva-conversacion";
export const TIPO_ARRASTRE_PROYECTO = "application/x-fva-proyecto";
export const TIPO_ARRASTRE_ITEM = "application/x-fva-item";

const CLAVE_PLEGADO = "fva-proyectos-plegados";

function leerPlegados(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(CLAVE_PLEGADO) || "[]"));
  } catch {
    return new Set();
  }
}

interface Props {
  /** Después de mover una conversación a una carpeta (para refrescar la lista del chat). */
  onCambio?: () => void;
}

export default function ArbolProyectos({ onCambio }: Props) {
  const { proyectos, arbol, error, recargar } = useProyectos();
  const { avisar } = useToast();
  const nav = useNavigate();
  const [abierto, setAbierto] = useState(() => localStorage.getItem("fva-proyectos-seccion") !== "cerrada");
  const [plegados, setPlegados] = useState<Set<string>>(leerPlegados);
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [sobre, setSobre] = useState<string | null>(null);
  const creandoYa = useRef(false); // Enter y el blur que sigue al desmontar el input llegan los dos: se crea una sola vez

  useEffect(() => {
    localStorage.setItem("fva-proyectos-seccion", abierto ? "abierta" : "cerrada");
  }, [abierto]);

  function plegar(id: string) {
    setPlegados((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      localStorage.setItem(CLAVE_PLEGADO, JSON.stringify([...n]));
      return n;
    });
  }

  async function crear() {
    const n = nombre.trim();
    if (!n) {
      setCreando(false);
      return;
    }
    if (creandoYa.current) return;
    creandoYa.current = true;
    setGuardando(true);
    try {
      const p = await apiProyectos.crear({ nombre: n });
      await recargar();
      setNombre("");
      setCreando(false);
      avisar(`Carpeta «${p.nombre}» creada.`);
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude crear la carpeta.", "error");
    } finally {
      setGuardando(false);
      creandoYa.current = false;
    }
  }

  function teclaNueva(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      crear();
    } else if (e.key === "Escape") {
      e.stopPropagation();
      setCreando(false);
      setNombre("");
    }
  }

  // ---------- soltar sobre una carpeta ----------
  function puedeSoltar(e: DragEvent, n: NodoProyecto) {
    if (n.permiso === "ver") return false;
    const tipos = Array.from(e.dataTransfer.types);
    return tipos.includes(TIPO_ARRASTRE_CONV) || tipos.includes(TIPO_ARRASTRE_PROYECTO) || tipos.includes(TIPO_ARRASTRE_ITEM);
  }

  async function soltar(e: DragEvent, n: NodoProyecto) {
    e.preventDefault();
    e.stopPropagation();
    setSobre(null);
    const conv = e.dataTransfer.getData(TIPO_ARRASTRE_CONV);
    const proy = e.dataTransfer.getData(TIPO_ARRASTRE_PROYECTO);
    const item = e.dataTransfer.getData(TIPO_ARRASTRE_ITEM); // "proyecto_id|item_fila_id"
    try {
      if (conv) {
        await apiProyectos.agregarItem(n.id, "conversacion", conv);
        avisar(`Conversación guardada en «${n.nombre}».`);
      } else if (proy) {
        if (proy === n.id) return;
        await apiProyectos.editar(proy, { padre_id: n.id });
        avisar(`Carpeta movida adentro de «${n.nombre}».`);
      } else if (item) {
        const [de, iid] = item.split("|");
        if (de === n.id) return;
        await apiProyectos.moverItem(de, iid, n.id);
        avisar(`Movido a «${n.nombre}».`);
      } else return;
      await recargar();
      onCambio?.();
    } catch (err) {
      avisar(err instanceof ErrorApi ? err.message : "No pude moverlo.", "error");
    }
  }

  const n = proyectos?.length || 0;
  return (
    <section className={"arbol" + (abierto ? "" : " cerrado")} aria-label="Proyectos">
      <div className="arbol-cabecera">
        <button type="button" className="arbol-plegar" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto} aria-controls="arbol-lista">
          <Icono nombre="chevron" tam={14} style={{ transform: abierto ? "rotate(90deg)" : undefined }} />
          <span>Proyectos</span>
          {n > 0 && <span className="chip suave">{n}</span>}
        </button>
        <span className="arbol-botones">
          <button type="button" className="boton sutil chico icono-solo" onClick={() => setCreando(true)} aria-label="Nueva carpeta" title="Nueva carpeta">
            <Icono nombre="carpetaMas" tam={16} />
          </button>
          <button type="button" className="boton sutil chico icono-solo" onClick={() => nav("/proyectos")} aria-label="Agrandar: ver los proyectos en grande" title="Agrandar">
            <Icono nombre="agrandar" tam={15} />
          </button>
        </span>
      </div>
      {abierto && (
        <div id="arbol-lista" className="arbol-lista">
          {creando && (
            <div className="arbol-nueva">
              <Icono nombre="carpeta" tam={16} style={{ color: "var(--amarillo-oscuro)" }} />
              <input autoFocus value={nombre} onChange={(e) => setNombre(e.target.value)} onKeyDown={teclaNueva} onBlur={crear} placeholder="Nombre de la carpeta" aria-label="Nombre de la carpeta nueva" maxLength={80} disabled={guardando} />
            </div>
          )}
          {error && <p className="aviso error chico" style={{ margin: "4px 0" }}>{error}</p>}
          {proyectos === null && !error && <p className="suave chico" style={{ margin: "4px 10px" }}>Cargando…</p>}
          {proyectos && proyectos.length === 0 && !creando && (
            <p className="suave chico arbol-vacio">
              Sin carpetas todavía. Creá una y arrastrá conversaciones adentro.
            </p>
          )}
          <ul className="arbol-nivel" role="tree">
            {arbol.map((nodo) => (
              <Nodo key={nodo.id} n={nodo} plegados={plegados} plegar={plegar} sobre={sobre} setSobre={setSobre} puedeSoltar={puedeSoltar} soltar={soltar} />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Nodo({ n, plegados, plegar, sobre, setSobre, puedeSoltar, soltar }: { n: NodoProyecto; plegados: Set<string>; plegar: (id: string) => void; sobre: string | null; setSobre: (id: string | null) => void; puedeSoltar: (e: DragEvent, n: NodoProyecto) => boolean; soltar: (e: DragEvent, n: NodoProyecto) => void }) {
  const nav = useNavigate();
  const { id: rutaId } = useParams();
  const tieneHijos = n.hijos.length > 0;
  const plegado = plegados.has(n.id);
  const compartida = n.permiso !== "dueño" || (n.compartido_con_n || 0) > 0;
  const activa = rutaId === n.id && window.location.pathname.startsWith("/proyectos");
  return (
    <li role="treeitem" aria-expanded={tieneHijos ? !plegado : undefined} aria-selected={activa}>
      <div
        className={"arbol-nodo" + (sobre === n.id ? " sobre" : "") + (activa ? " activa" : "") + (n.permiso === "ver" ? " solo-ver" : "")}
        style={{ paddingLeft: 6 + n.nivel * 14 }}
        draggable={n.permiso === "dueño"}
        onDragStart={(e) => {
          e.dataTransfer.setData(TIPO_ARRASTRE_PROYECTO, n.id);
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(e) => {
          if (!puedeSoltar(e, n)) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          if (sobre !== n.id) setSobre(n.id);
        }}
        onDragLeave={() => sobre === n.id && setSobre(null)}
        onDrop={(e) => soltar(e, n)}
      >
        <button type="button" className={"arbol-flecha" + (tieneHijos ? "" : " vacia")} onClick={() => tieneHijos && plegar(n.id)} aria-label={tieneHijos ? (plegado ? "Desplegar" : "Plegar") : undefined} tabIndex={tieneHijos ? 0 : -1}>
          {tieneHijos && <Icono nombre="chevron" tam={12} style={{ transform: plegado ? undefined : "rotate(90deg)" }} />}
        </button>
        <button type="button" className="arbol-abrir" onClick={() => nav(`/proyectos/${n.id}`)} title={(n.descripcion ? n.descripcion + " · " : "") + `${n.n_items || 0} elementos`}>
          <Icono nombre="carpeta" tam={16} style={{ color: n.color || "var(--amarillo-oscuro)" }} />
          <span className="arbol-nombre">{etiqueta(n)}</span>
          {compartida && (
            <span className="arbol-compartida" title={n.permiso !== "dueño" ? `Compartida por ${n.compartido_por || "otra persona"} (${n.permiso === "ver" ? "solo ver" : "puede editar"})` : `Compartida con ${n.compartido_con_n} persona${n.compartido_con_n === 1 ? "" : "s"}`}>
              <Icono nombre="compartir" tam={12} />
            </span>
          )}
          {(n.n_items || 0) > 0 && <span className="arbol-n suave">{n.n_items}</span>}
        </button>
      </div>
      {tieneHijos && !plegado && (
        <ul className="arbol-nivel" role="group">
          {n.hijos.map((h) => (
            <Nodo key={h.id} n={h} plegados={plegados} plegar={plegar} sobre={sobre} setSobre={setSobre} puedeSoltar={puedeSoltar} soltar={soltar} />
          ))}
        </ul>
      )}
    </li>
  );
}
