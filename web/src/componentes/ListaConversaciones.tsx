// La lista de conversaciones de la persona (la barra lateral del chat de Streamlit): buscador, «Nueva conversación», ítems con
// título y fecha relativa, renombrar en el lugar y borrar con confirmación + «Deshacer» (papelera de db.py).
// Es un componente aparte y cada ítem es <ItemConversacion data-id> para que, en la próxima etapa (carpetas / proyectos), alcance
// con envolver la lista en grupos y hacer los ítems arrastrables sin rehacer el chat.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { ConversacionResumen } from "../tiposChat";
import { grupo, relativa, type Idioma } from "../util/fechas";
import { textos } from "../textos";
import { Icono } from "./Iconos";
import Modal from "./Modal";
import { Hueso } from "./Comunes";

interface Props {
  items: ConversacionResumen[] | null; // null = cargando
  error?: string | null;
  actualId: string | null;
  idioma: Idioma;
  onNueva: () => void;
  onAbrir: (id: string) => void;
  onRenombrar: (id: string, titulo: string) => Promise<void>;
  onBorrar: (id: string) => Promise<void>;
  onRestaurar: (id: string) => Promise<void>;
  onReintentar?: () => void;
  /** En celular la lista es un cajón: este botón lo cierra. */
  onCerrar?: () => void;
  /** (22/10, proyectos) «Mover a…» por menú (alternativa táctil al arrastre) y la carpeta donde está cada conversación. */
  onMoverA?: (c: ConversacionResumen) => void;
  carpetaDe?: (id: string) => string | null;
  /** Encima de la lista (el árbol de proyectos). */
  arriba?: React.ReactNode;
}

const ORDEN_GRUPOS = ["hoy", "ayer", "semana", "antes"] as const;

export default function ListaConversaciones({ items, error, actualId, idioma, onNueva, onAbrir, onRenombrar, onBorrar, onRestaurar, onReintentar, onCerrar, onMoverA, carpetaDe, arriba }: Props) {
  const t = textos(idioma);
  const [buscar, setBuscar] = useState("");
  const [aBorrar, setABorrar] = useState<ConversacionResumen | null>(null);
  const [borrando, setBorrando] = useState(false);
  const [borrada, setBorrada] = useState<ConversacionResumen | null>(null); // para «Deshacer»
  const [restaurando, setRestaurando] = useState(false);
  const temporizador = useRef<number | null>(null);

  // El aviso «Deshacer» se va solo a los 12 s.
  useEffect(() => {
    if (!borrada) return;
    temporizador.current = window.setTimeout(() => setBorrada(null), 12000);
    return () => {
      if (temporizador.current) window.clearTimeout(temporizador.current);
    };
  }, [borrada]);

  const filtrados = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    const lista = items || [];
    return q ? lista.filter((c) => (c.titulo || "").toLowerCase().includes(q)) : lista;
  }, [items, buscar]);

  const grupos = useMemo(() => {
    const ahora = new Date();
    const m = new Map<string, ConversacionResumen[]>();
    for (const c of filtrados) {
      const g = grupo(c.actualizado, ahora);
      if (!m.has(g)) m.set(g, []);
      m.get(g)!.push(c);
    }
    return ORDEN_GRUPOS.filter((g) => m.has(g)).map((g) => ({ clave: g, items: m.get(g)! }));
  }, [filtrados]);

  async function confirmarBorrado() {
    if (!aBorrar) return;
    setBorrando(true);
    try {
      await onBorrar(aBorrar.id);
      setBorrada(aBorrar);
      setABorrar(null);
    } finally {
      setBorrando(false);
    }
  }

  async function deshacer() {
    if (!borrada) return;
    setRestaurando(true);
    try {
      await onRestaurar(borrada.id);
      setBorrada(null);
    } finally {
      setRestaurando(false);
    }
  }

  return (
    <nav className="conv-lista" aria-label={t("tus")}>
      <div className="conv-cabecera">
        <button type="button" className="boton primario conv-nueva" onClick={onNueva}>
          <Icono nombre="mas" /> {t("nueva")}
        </button>
        {onCerrar && (
          <button type="button" className="boton sutil icono-solo conv-cerrar" onClick={onCerrar} aria-label={t("cerrar")}>
            <Icono nombre="cruz" />
          </button>
        )}
      </div>
      <div className="buscar conv-buscar">
        <Icono nombre="buscar" tam={16} />
        <input type="search" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder={t("buscar")} aria-label={t("buscar")} />
      </div>

      {borrada && (
        <div className="aviso conv-deshacer" role="status">
          <span>{t("borrada")}</span>
          <button type="button" className="boton chico" onClick={deshacer} disabled={restaurando}>
            <Icono nombre="deshacer" tam={14} /> {t("deshacer")}
          </button>
        </div>
      )}

      {error && (
        <div className="aviso error chico">
          {error}{" "}
          {onReintentar && (
            <button type="button" className="boton chico" onClick={onReintentar}>
              <Icono nombre="regenerar" tam={14} /> {t("reintentar")}
            </button>
          )}
        </div>
      )}

      <div className="conv-scroll">
        {arriba}
        {items === null && !error && (
          <div aria-busy="true" aria-label={t("tus")} className="conv-esqueleto">
            {[80, 60, 72, 50, 66].map((w, i) => (
              <div key={i} className="conv-item esqueleto">
                <Hueso ancho={`${w}%`} alto={14} />
                <Hueso ancho={40} alto={10} style={{ marginTop: 6 }} />
              </div>
            ))}
          </div>
        )}
        {items && items.length === 0 && <p className="suave chico conv-vacia">{t("sinConversaciones")}</p>}
        {items && items.length > 0 && filtrados.length === 0 && <p className="suave chico conv-vacia">{t("sinResultados")}</p>}
        {grupos.map((g) => (
          <section key={g.clave} className="conv-grupo" aria-label={t(g.clave)}>
            <h4 className="conv-grupo-titulo">{t(g.clave)}</h4>
            <ul className="conv-items">
              {g.items.map((c) => (
                <ItemConversacion key={c.id} c={c} activa={c.id === actualId} idioma={idioma} onAbrir={() => onAbrir(c.id)} onRenombrar={(tit) => onRenombrar(c.id, tit)} onBorrar={() => setABorrar(c)} onMoverA={onMoverA ? () => onMoverA(c) : undefined} carpeta={carpetaDe?.(c.id) ?? null} />
              ))}
            </ul>
          </section>
        ))}
      </div>

      {aBorrar && (
        <Modal titulo={t("borrarTitulo")} onCerrar={() => (borrando ? null : setABorrar(null))} peligro>
          <p>
            <strong>{aBorrar.titulo || t("conversacion")}</strong>
          </p>
          <p className="suave">{t("borrarTexto")}</p>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="boton" onClick={() => setABorrar(null)} disabled={borrando}>
              {t("cancelar")}
            </button>
            <button type="button" className="boton peligro" onClick={confirmarBorrado} disabled={borrando}>
              <Icono nombre="tacho" /> {borrando ? "…" : t("siBorrar")}
            </button>
          </div>
        </Modal>
      )}
    </nav>
  );
}

/** Un ítem: botón con el título y la fecha; al pasar el mouse (o siempre, en táctil) los iconos de renombrar y borrar.
 *  data-id queda para el arrastre a carpetas de la próxima etapa. */
function ItemConversacion({ c, activa, idioma, onAbrir, onRenombrar, onBorrar, onMoverA, carpeta }: { c: ConversacionResumen; activa: boolean; idioma: Idioma; onAbrir: () => void; onRenombrar: (t: string) => Promise<void>; onBorrar: () => void; onMoverA?: () => void; carpeta?: string | null }) {
  const t = textos(idioma);
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState(c.titulo || "");
  const [guardando, setGuardando] = useState(false);
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editando) {
      campo.current?.focus();
      campo.current?.select();
    }
  }, [editando]);

  async function guardar() {
    const nuevo = valor.trim();
    if (!nuevo || nuevo === (c.titulo || "")) {
      setEditando(false);
      setValor(c.titulo || "");
      return;
    }
    setGuardando(true);
    try {
      await onRenombrar(nuevo);
      setEditando(false);
    } finally {
      setGuardando(false);
    }
  }

  function tecla(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      guardar();
    } else if (e.key === "Escape") {
      e.stopPropagation();
      setEditando(false);
      setValor(c.titulo || "");
    }
  }

  const titulo = c.titulo || t("conversacion");
  return (
    <li
      className={"conv-item" + (activa ? " activa" : "")}
      data-id={c.id}
      draggable={!!onMoverA && !editando}
      onDragStart={(e) => {
        // (22/10) se suelta sobre una carpeta del árbol de proyectos (ArbolProyectos) o de la vista grande
        e.dataTransfer.setData("application/x-fva-conversacion", c.id);
        e.dataTransfer.setData("text/plain", titulo);
        e.dataTransfer.effectAllowed = "move";
      }}
    >
      {editando ? (
        <input ref={campo} className="conv-renombrar" value={valor} onChange={(e) => setValor(e.target.value)} onKeyDown={tecla} onBlur={guardar} disabled={guardando} aria-label={t("renombrar")} maxLength={120} />
      ) : (
        <>
          <button type="button" className="conv-abrir" onClick={onAbrir} aria-current={activa ? "page" : undefined} title={titulo}>
            <span className="conv-titulo">{titulo}</span>
            <span className="conv-fecha suave">
              {relativa(c.actualizado, idioma)}
              {carpeta && (
                <span className="conv-carpeta" title={`En la carpeta ${carpeta}`}>
                  <Icono nombre="carpeta" tam={11} /> {carpeta}
                </span>
              )}
            </span>
          </button>
          <span className="conv-acciones">
            {onMoverA && (
              <button type="button" className="boton sutil chico icono-solo" onClick={onMoverA} aria-label={`Mover a una carpeta: ${titulo}`} title="Mover a una carpeta…">
                <Icono nombre="carpeta" tam={15} />
              </button>
            )}
            <button type="button" className="boton sutil chico icono-solo" onClick={() => setEditando(true)} aria-label={`${t("renombrar")}: ${titulo}`} title={t("renombrar")}>
              <Icono nombre="lapiz" tam={15} />
            </button>
            <button type="button" className="boton sutil peligro chico icono-solo" onClick={onBorrar} aria-label={`${t("borrar")}: ${titulo}`} title={t("borrar")}>
              <Icono nombre="tacho" tam={15} />
            </button>
          </span>
        </>
      )}
    </li>
  );
}
