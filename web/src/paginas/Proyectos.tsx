// Vista grande de «Proyectos» (22/10; pedido de Franco: «un botón de agrandar que abra como una ventana grande, estilo Google
// Drive, donde cada conversación es un archivo y adentro tenés cada carpeta, podés arrastrarlas y borrarlas»).
// /proyectos = la raíz (mis carpetas + las compartidas conmigo); /proyectos/:id = adentro de una carpeta.
// Migas de pan, grilla o lista, buscador, ordenar, selección múltiple (clic, Ctrl/Shift+clic, casillas), arrastrar carpetas e
// ítems a otra carpeta o a una miga, menú contextual (clic derecho o ⋮), panel de detalles, vacíos con llamada a la acción.
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { apiChat } from "../apiChat";
import { apiProyectos } from "../apiProyectos";
import { useSesion } from "../App";
import type { ContenidoProyecto, ItemProyecto, Proyecto, TipoItem } from "../tiposProyectos";
import { Icono, type NombreIcono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import MoverA from "../componentes/proyectos/MoverA";
import CompartirModal from "../componentes/proyectos/CompartirModal";
import { ESTADO_TXT, IconoTipo, Miniatura, TIPO_TXT, rutaDe } from "../componentes/proyectos/IconoItem";
import { etiqueta, useProyectos } from "../componentes/proyectos/ProyectosContexto";
import { TIPO_ARRASTRE_CONV, TIPO_ARRASTRE_ITEM, TIPO_ARRASTRE_PROYECTO } from "../componentes/proyectos/ArbolProyectos";
import "../proyectos.css";

type Vista = "grilla" | "lista";
type Orden = "nombre" | "fecha";
type Sel = { clase: "carpeta"; id: string } | { clase: "item"; id: string };
const COLORES = ["#d99a1f", "#3a6b35", "#2f6fb3", "#b43c3c", "#8a4fb0", "#1f8a8a", "#666"];

function fechaCorta(iso: string | null | undefined) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "2-digit" }) + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

function claveSel(s: Sel) {
  return s.clase + ":" + s.id;
}

export default function Proyectos() {
  const { id } = useParams();
  const nav = useNavigate();
  const { yo } = useSesion();
  const { avisar } = useToast();
  const proyectos = useProyectos();

  const [contenido, setContenido] = useState<ContenidoProyecto | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [vista, setVista] = useState<Vista>(() => (localStorage.getItem("fva-proyectos-vista") as Vista) || "grilla");
  const [orden, setOrden] = useState<Orden>("nombre");
  const [asc, setAsc] = useState(true);
  const [buscar, setBuscar] = useState("");
  const [sel, setSel] = useState<Map<string, Sel>>(new Map());
  const [menu, setMenu] = useState<{ x: number; y: number; sobre: Sel } | null>(null);
  const [sobreCarpeta, setSobreCarpeta] = useState<string | null>(null);
  const [nuevaCarpeta, setNuevaCarpeta] = useState(false);
  const [renombrando, setRenombrando] = useState<Proyecto | null>(null);
  const [aBorrar, setABorrar] = useState<Proyecto | null>(null);
  const [aQuitar, setAQuitar] = useState<ItemProyecto[] | null>(null);
  const [moviendo, setMoviendo] = useState<Sel[] | null>(null);
  const [compartiendo, setCompartiendo] = useState<Proyecto | null>(null);
  const [agregando, setAgregando] = useState(false);
  const [detalles, setDetalles] = useState(() => window.innerWidth > 1000);
  const ultimoClic = useRef<string | null>(null);

  useEffect(() => localStorage.setItem("fva-proyectos-vista", vista), [vista]);

  // ---------- cargar ----------
  const cargar = useCallback(async () => {
    if (!id) {
      setContenido(null);
      setError(null);
      return;
    }
    setCargando(true);
    try {
      setContenido(await apiProyectos.ver(id));
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude abrir la carpeta.");
      setContenido(null);
    } finally {
      setCargando(false);
    }
  }, [id]);
  useEffect(() => {
    setSel(new Map());
    setMenu(null);
    cargar();
  }, [cargar]);

  async function refrescar() {
    await Promise.all([cargar(), proyectos.recargar()]);
  }

  // ---------- lo que se muestra ----------
  const permiso = id ? contenido?.permiso || null : "dueño";
  const puedeEditar = permiso === "dueño" || permiso === "editar";
  const carpetaActual = id ? contenido?.proyecto || proyectos.porId.get(id) || null : null;

  const carpetas: Proyecto[] = useMemo(() => {
    if (id) return contenido?.subcarpetas || [];
    return (proyectos.proyectos || []).filter((p) => !p.padre_id || !proyectos.porId.has(p.padre_id));
  }, [id, contenido, proyectos.proyectos, proyectos.porId]);
  const items: ItemProyecto[] = id ? contenido?.items || [] : [];

  const q = buscar.trim().toLowerCase();
  const cmp = (a: string, b: string) => (asc ? 1 : -1) * a.localeCompare(b, "es");
  const carpetasVis = useMemo(() => {
    const l = carpetas.filter((c) => !q || c.nombre.toLowerCase().includes(q));
    return l.sort((a, b) => (orden === "nombre" ? cmp(a.nombre, b.nombre) : cmp(a.actualizado || "", b.actualizado || "")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [carpetas, q, orden, asc]);
  const itemsVis = useMemo(() => {
    const l = items.filter((i) => !q || (i.titulo || "").toLowerCase().includes(q) || TIPO_TXT[i.tipo].toLowerCase().includes(q));
    return l.sort((a, b) => (orden === "nombre" ? cmp(a.titulo || "", b.titulo || "") : cmp(a.fecha || a.agregado || "", b.fecha || b.agregado || "")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, q, orden, asc]);
  const todos: Sel[] = useMemo(() => [...carpetasVis.map((c) => ({ clase: "carpeta", id: c.id }) as Sel), ...itemsVis.map((i) => ({ clase: "item", id: i.id }) as Sel)], [carpetasVis, itemsVis]);

  // ---------- selección ----------
  function clicSel(e: MouseEvent, s: Sel) {
    e.stopPropagation();
    const k = claveSel(s);
    setSel((prev) => {
      const n = new Map(e.ctrlKey || e.metaKey ? prev : []);
      if (e.shiftKey && ultimoClic.current) {
        const claves = todos.map(claveSel);
        const a = claves.indexOf(ultimoClic.current);
        const b = claves.indexOf(k);
        if (a >= 0 && b >= 0) {
          for (let i = Math.min(a, b); i <= Math.max(a, b); i++) n.set(claves[i], todos[i]);
          return n;
        }
      }
      if ((e.ctrlKey || e.metaKey) && prev.has(k)) n.delete(k);
      else n.set(k, s);
      return n;
    });
    ultimoClic.current = k;
  }
  function marcar(s: Sel, si: boolean) {
    setSel((prev) => {
      const n = new Map(prev);
      if (si) n.set(claveSel(s), s);
      else n.delete(claveSel(s));
      return n;
    });
  }
  const seleccion = [...sel.values()];
  const unico = seleccion.length === 1 ? seleccion[0] : null;
  const carpetaSel = unico?.clase === "carpeta" ? carpetas.find((c) => c.id === unico.id) || proyectos.porId.get(unico.id) || null : null;
  const itemSel = unico?.clase === "item" ? items.find((i) => i.id === unico.id) || null : null;

  // ---------- abrir ----------
  function abrir(s: Sel) {
    if (s.clase === "carpeta") nav(`/proyectos/${s.id}`);
    else {
      const it = items.find((i) => i.id === s.id);
      const r = it && rutaDe(it);
      if (r) nav(r);
      else if (it?.tipo === "imagen" && it.url) window.open(it.url, "_blank", "noopener");
      else avisar(it && !it.existe ? "Ese elemento ya no existe." : "Ese elemento todavía no tiene pantalla propia.", "info");
    }
  }

  // ---------- acciones ----------
  async function crearCarpeta(nombre: string) {
    try {
      const p = await apiProyectos.crear({ nombre, padre_id: id || null });
      await refrescar();
      avisar(`Carpeta «${p.nombre}» creada.`);
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude crear la carpeta.", "error");
      throw e;
    }
  }
  async function renombrar(p: Proyecto, nombre: string) {
    try {
      await apiProyectos.editar(p.id, { nombre });
      await refrescar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude renombrar.", "error");
      throw e;
    }
  }
  async function editarCarpeta(p: Proyecto, datos: { descripcion?: string | null; color?: string | null; emoji?: string | null }) {
    try {
      await apiProyectos.editar(p.id, datos);
      await refrescar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude guardar.", "error");
    }
  }
  async function borrarCarpeta(p: Proyecto) {
    try {
      await apiProyectos.borrar(p.id);
      avisar(`Carpeta «${p.nombre}» borrada. Las conversaciones, recortes y piezas siguen donde estaban.`);
      setABorrar(null);
      setSel(new Map());
      if (p.id === id) nav(p.padre_id ? `/proyectos/${p.padre_id}` : "/proyectos");
      else await refrescar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude borrar la carpeta.", "error");
    }
  }
  async function quitar(lista: ItemProyecto[]) {
    if (!id) return;
    let n = 0;
    for (const it of lista) {
      try {
        await apiProyectos.quitarItem(id, it.id);
        n++;
      } catch (e) {
        avisar(e instanceof ErrorApi ? e.message : "No pude quitarlo.", "error");
      }
    }
    if (n) avisar(n === 1 ? "Quitado del proyecto (el original sigue en su lugar)." : `${n} elementos quitados del proyecto.`);
    setAQuitar(null);
    setSel(new Map());
    await refrescar();
  }
  async function moverTodo(lista: Sel[], destino: string) {
    let n = 0;
    for (const s of lista) {
      try {
        if (s.clase === "carpeta") {
          if (s.id === destino) continue;
          await apiProyectos.editar(s.id, { padre_id: destino });
        } else if (id) await apiProyectos.moverItem(id, s.id, destino);
        n++;
      } catch (e) {
        avisar(e instanceof ErrorApi ? e.message : "No pude moverlo.", "error");
        throw e;
      }
    }
    const nombre = proyectos.porId.get(destino)?.nombre || "la carpeta";
    if (n) avisar(n === 1 ? `Movido a «${nombre}».` : `${n} elementos movidos a «${nombre}».`);
    setSel(new Map());
    await refrescar();
  }
  async function alRaiz(lista: Sel[]) {
    for (const s of lista) {
      if (s.clase !== "carpeta") continue;
      try {
        await apiProyectos.editar(s.id, { padre_id: "" });
      } catch (e) {
        avisar(e instanceof ErrorApi ? e.message : "No pude moverla.", "error");
      }
    }
    setSel(new Map());
    await refrescar();
  }

  // ---------- arrastrar ----------
  function iniciarArrastre(e: DragEvent, s: Sel) {
    const lista = sel.has(claveSel(s)) ? seleccion : [s];
    const carp = lista.filter((x) => x.clase === "carpeta").map((x) => x.id);
    const its = lista.filter((x) => x.clase === "item").map((x) => `${id}|${x.id}`);
    if (carp.length) e.dataTransfer.setData(TIPO_ARRASTRE_PROYECTO, carp.join(","));
    if (its.length) e.dataTransfer.setData(TIPO_ARRASTRE_ITEM, its.join(","));
    e.dataTransfer.setData("text/plain", String(lista.length));
    e.dataTransfer.effectAllowed = "move";
  }
  function aceptaSoltar(e: DragEvent, destino: Proyecto | null) {
    if (destino && destino.permiso === "ver") return false;
    const t = Array.from(e.dataTransfer.types);
    if (!destino) return t.includes(TIPO_ARRASTRE_PROYECTO); // la raíz solo recibe carpetas
    return t.includes(TIPO_ARRASTRE_PROYECTO) || t.includes(TIPO_ARRASTRE_ITEM) || t.includes(TIPO_ARRASTRE_CONV);
  }
  async function soltar(e: DragEvent, destino: Proyecto | null) {
    e.preventDefault();
    e.stopPropagation();
    setSobreCarpeta(null);
    const carp = (e.dataTransfer.getData(TIPO_ARRASTRE_PROYECTO) || "").split(",").filter(Boolean);
    const its = (e.dataTransfer.getData(TIPO_ARRASTRE_ITEM) || "").split(",").filter(Boolean);
    const conv = e.dataTransfer.getData(TIPO_ARRASTRE_CONV);
    try {
      if (!destino) {
        if (carp.length) await alRaiz(carp.map((c) => ({ clase: "carpeta", id: c })));
        return;
      }
      if (carp.includes(destino.id)) return;
      let n = 0;
      for (const c of carp) {
        await apiProyectos.editar(c, { padre_id: destino.id });
        n++;
      }
      for (const x of its) {
        const [de, iid] = x.split("|");
        if (de === destino.id) continue;
        await apiProyectos.moverItem(de, iid, destino.id);
        n++;
      }
      if (conv) {
        await apiProyectos.agregarItem(destino.id, "conversacion", conv);
        n++;
      }
      if (n) avisar(n === 1 ? `Movido a «${destino.nombre}».` : `${n} elementos movidos a «${destino.nombre}».`);
      setSel(new Map());
      await refrescar();
    } catch (err) {
      avisar(err instanceof ErrorApi ? err.message : "No pude moverlo.", "error");
    }
  }

  // ---------- menú contextual ----------
  function abrirMenu(e: MouseEvent, s: Sel) {
    e.preventDefault();
    e.stopPropagation();
    if (!sel.has(claveSel(s))) setSel(new Map([[claveSel(s), s]]));
    const x = Math.min(e.clientX, window.innerWidth - 230);
    const y = Math.min(e.clientY, window.innerHeight - 300);
    setMenu({ x, y, sobre: s });
  }
  useEffect(() => {
    if (!menu) return;
    const cerrar = () => setMenu(null);
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setMenu(null);
    document.addEventListener("click", cerrar);
    document.addEventListener("keydown", tecla);
    window.addEventListener("scroll", cerrar, true);
    return () => {
      document.removeEventListener("click", cerrar);
      document.removeEventListener("keydown", tecla);
      window.removeEventListener("scroll", cerrar, true);
    };
  }, [menu]);

  // atajos: Supr quita/borra, Enter abre, Escape deselecciona
  useEffect(() => {
    function tecla(e: KeyboardEvent) {
      const obj = e.target as HTMLElement | null;
      if (obj && (obj.tagName === "INPUT" || obj.tagName === "TEXTAREA" || obj.tagName === "SELECT")) return;
      if (document.querySelector(".fondo-modal")) return;
      if (e.key === "Escape") setSel(new Map());
      else if (e.key === "Enter" && unico) abrir(unico);
      else if (e.key === "Delete" && seleccion.length && puedeEditar) {
        const its = seleccion.filter((s) => s.clase === "item").map((s) => items.find((i) => i.id === s.id)!).filter(Boolean);
        if (its.length) setAQuitar(its);
        else if (carpetaSel && esDuenoDe(carpetaSel)) setABorrar(carpetaSel);
      }
    }
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  });

  const esDuenoDe = (p: Proyecto) => p.permiso === "dueño" || p.dueno === yo?.usuario;
  const migas = id ? [{ id: "", nombre: "Mis proyectos" }, ...(contenido?.migas || (carpetaActual ? [{ id: carpetaActual.id, nombre: carpetaActual.nombre }] : []))] : [{ id: "", nombre: "Mis proyectos" }];
  const nombreVentana = carpetaActual ? etiqueta(carpetaActual) : "Proyectos";
  const itemsSel = seleccion.filter((s) => s.clase === "item").map((s) => items.find((i) => i.id === s.id)!).filter(Boolean);

  function MenuOpciones({ s }: { s: Sel }) {
    const carpeta = s.clase === "carpeta" ? carpetas.find((c) => c.id === s.id) || proyectos.porId.get(s.id) : undefined;
    const it = s.clase === "item" ? items.find((i) => i.id === s.id) : undefined;
    const varios = seleccion.length > 1 && sel.has(claveSel(s));
    const op = (icono: NombreIcono, texto: string, hacer: () => void, peligro = false) => (
      <button type="button" role="menuitem" className={"menu-op" + (peligro ? " peligro" : "")} onClick={() => { setMenu(null); hacer(); }}>
        <Icono nombre={icono} tam={16} /> {texto}
      </button>
    );
    return (
      <div className="menu-contextual tarjeta" role="menu" style={{ left: menu?.x, top: menu?.y }} onClick={(e) => e.stopPropagation()}>
        {!varios && op("externo", "Abrir", () => abrir(s))}
        {puedeEditar && (carpeta ? esDuenoDe(carpeta) : true) && op("mover", varios ? `Mover ${seleccion.length} elementos a…` : "Mover a…", () => setMoviendo(varios ? seleccion : [s]))}
        {carpeta && esDuenoDe(carpeta) && !varios && op("compartir", "Compartir", () => setCompartiendo(carpeta))}
        {carpeta && (carpeta.permiso !== "ver") && !varios && op("lapiz", "Renombrar", () => setRenombrando(carpeta))}
        {it && puedeEditar && op("cruz", varios ? `Quitar ${itemsSel.length} del proyecto` : "Quitar del proyecto", () => setAQuitar(varios ? itemsSel : [it]))}
        {carpeta && esDuenoDe(carpeta) && !varios && op("tacho", "Borrar la carpeta…", () => setABorrar(carpeta), true)}
      </div>
    );
  }

  return (
    <div className="drive" onClick={() => setSel(new Map())}>
      <header className="drive-cabecera">
        <div className="drive-titulo">
          <Icono nombre="carpeta" tam={22} style={{ color: carpetaActual?.color || "var(--amarillo-oscuro)" }} />
          <h1>{nombreVentana}</h1>
          {carpetaActual && permiso && permiso !== "dueño" && <span className="chip suave">{permiso === "ver" ? "solo ver" : "podés editar"} · de {carpetaActual.dueno}</span>}
        </div>
        <div className="buscar drive-buscar">
          <Icono nombre="buscar" tam={16} />
          <input type="search" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder={id ? "Buscar en esta carpeta" : "Buscar carpeta"} aria-label="Buscar" />
        </div>
        <div className="drive-herramientas" onClick={(e) => e.stopPropagation()}>
          <label className="drive-orden">
            <Icono nombre="ordenar" tam={15} />
            <select value={orden} onChange={(e) => setOrden(e.target.value as Orden)} aria-label="Ordenar por">
              <option value="nombre">Nombre</option>
              <option value="fecha">Fecha</option>
            </select>
            <button type="button" className="boton sutil chico icono-solo" onClick={() => setAsc((a) => !a)} aria-label={asc ? "Ascendente" : "Descendente"} title={asc ? "Ascendente" : "Descendente"}>
              <Icono nombre="chevron" tam={14} style={{ transform: asc ? "rotate(-90deg)" : "rotate(90deg)" }} />
            </button>
          </label>
          <span className="drive-vistas" role="group" aria-label="Cómo ver">
            <button type="button" className={"boton sutil chico icono-solo" + (vista === "grilla" ? " activo" : "")} onClick={() => setVista("grilla")} aria-pressed={vista === "grilla"} title="Grilla">
              <Icono nombre="grilla" tam={16} />
            </button>
            <button type="button" className={"boton sutil chico icono-solo" + (vista === "lista" ? " activo" : "")} onClick={() => setVista("lista")} aria-pressed={vista === "lista"} title="Lista">
              <Icono nombre="lista" tam={16} />
            </button>
          </span>
          <button type="button" className={"boton sutil chico icono-solo" + (detalles ? " activo" : "")} onClick={() => setDetalles((d) => !d)} aria-pressed={detalles} title="Panel de detalles">
            <Icono nombre="info" tam={16} />
          </button>
          {puedeEditar && (
            <button type="button" className="boton chico" onClick={() => setNuevaCarpeta(true)}>
              <Icono nombre="carpetaMas" tam={16} /> <span>Nueva carpeta</span>
            </button>
          )}
          {id && puedeEditar && (
            <button type="button" className="boton primario chico" onClick={() => setAgregando(true)}>
              <Icono nombre="mas" tam={16} /> <span>Agregar</span>
            </button>
          )}
          {carpetaActual && esDuenoDe(carpetaActual) && (
            <button type="button" className="boton chico" onClick={() => setCompartiendo(carpetaActual)} title="Compartir esta carpeta">
              <Icono nombre="compartir" tam={16} /> <span>Compartir</span>
            </button>
          )}
          <button type="button" className="boton sutil chico icono-solo drive-cerrar" onClick={() => nav("/chat")} aria-label="Cerrar y volver al chat" title="Volver al chat">
            <Icono nombre="cruz" tam={18} />
          </button>
        </div>
      </header>

      <nav className="drive-migas" aria-label="Dónde estás">
        {migas.map((m, i) => {
          const ultima = i === migas.length - 1;
          const destino = m.id ? proyectos.porId.get(m.id) || (contenido?.proyecto.id === m.id ? contenido.proyecto : null) : null;
          return (
            <span key={m.id || "raiz"} className="miga">
              {i > 0 && <Icono nombre="chevron" tam={14} />}
              {ultima ? (
                <span aria-current="page">{m.nombre}</span>
              ) : (
                <Link
                  to={m.id ? `/proyectos/${m.id}` : "/proyectos"}
                  className={sobreCarpeta === (m.id || "raiz") ? "sobre" : ""}
                  onDragOver={(e) => {
                    if (!aceptaSoltar(e, m.id ? destino : null)) return;
                    e.preventDefault();
                    setSobreCarpeta(m.id || "raiz");
                  }}
                  onDragLeave={() => setSobreCarpeta(null)}
                  onDrop={(e) => soltar(e, m.id ? destino : null)}
                >
                  {m.id ? m.nombre : <><Icono nombre="casa" tam={14} /> {m.nombre}</>}
                </Link>
              )}
            </span>
          );
        })}
        {seleccion.length > 0 && (
          <span className="drive-seleccion" onClick={(e) => e.stopPropagation()}>
            <span className="chip">{seleccion.length} seleccionado{seleccion.length > 1 ? "s" : ""}</span>
            {puedeEditar && (
              <button type="button" className="boton chico" onClick={() => setMoviendo(seleccion)}>
                <Icono nombre="mover" tam={14} /> Mover
              </button>
            )}
            {puedeEditar && itemsSel.length > 0 && (
              <button type="button" className="boton chico" onClick={() => setAQuitar(itemsSel)}>
                <Icono nombre="cruz" tam={14} /> Quitar
              </button>
            )}
            <button type="button" className="boton sutil chico" onClick={() => setSel(new Map())}>
              Deseleccionar
            </button>
          </span>
        )}
      </nav>

      <div className={"drive-cuerpo" + (detalles ? " con-detalles" : "")}>
        <main className="drive-lienzo" aria-busy={cargando}>
          {error && (
            <div className="aviso error">
              <Icono nombre="alerta" tam={16} /> {error}{" "}
              <Link className="boton chico" to="/proyectos">
                Ir a mis proyectos
              </Link>
            </div>
          )}
          {proyectos.error && !id && <div className="aviso error chico">{proyectos.error}</div>}
          {(cargando || (!id && proyectos.proyectos === null)) && !error && (
            <div className={"drive-" + vista} aria-hidden="true">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="ficha esqueleto">
                  <Hueso ancho="100%" alto={vista === "grilla" ? 110 : 22} radio={8} />
                  {vista === "grilla" && <Hueso ancho="70%" alto={14} style={{ marginTop: 10 }} />}
                </div>
              ))}
            </div>
          )}
          {!cargando && !error && (id ? !!contenido : proyectos.proyectos !== null) && (
            <>
              {carpetasVis.length === 0 && itemsVis.length === 0 && (
                <div className="vacio drive-vacio" role="status">
                  <Icono nombre={q ? "buscar" : "carpeta"} tam={42} style={{ color: "var(--amarillo-oscuro)" }} />
                  {q ? (
                    <>
                      <h3>Nada coincide con «{buscar.trim()}»</h3>
                      <p className="suave">Probá con otra palabra.</p>
                    </>
                  ) : id ? (
                    <>
                      <h3>Esta carpeta está vacía</h3>
                      <p className="suave">{puedeEditar ? "Arrastrá conversaciones desde la lista del chat, o agregá recortes, piezas e imágenes desde acá." : "Quien la compartió todavía no puso nada."}</p>
                      {puedeEditar && (
                        <div className="acciones" style={{ justifyContent: "center" }}>
                          <button type="button" className="boton primario" onClick={() => setAgregando(true)}>
                            <Icono nombre="mas" /> Agregar
                          </button>
                          <button type="button" className="boton" onClick={() => setNuevaCarpeta(true)}>
                            <Icono nombre="carpetaMas" /> Nueva subcarpeta
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <h3>Todavía no tenés proyectos</h3>
                      <p className="suave">Un proyecto es una carpeta: adentro van conversaciones, recortes, piezas e imágenes, con subcarpetas si querés. Se comparte con el equipo.</p>
                      <div className="acciones" style={{ justifyContent: "center" }}>
                        <button type="button" className="boton primario" onClick={() => setNuevaCarpeta(true)}>
                          <Icono nombre="carpetaMas" /> Crear el primero
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}

              {carpetasVis.length > 0 && (
                <section aria-label="Carpetas">
                  <h2 className="drive-seccion">Carpetas</h2>
                  <div className={"drive-" + vista}>
                    {vista === "lista" && (
                      <div className="fila cabecera" aria-hidden="true">
                        <span />
                        <span>Nombre</span>
                        <span>Dueño</span>
                        <span>Actualizada</span>
                        <span />
                      </div>
                    )}
                    {carpetasVis.map((c) => {
                      const s: Sel = { clase: "carpeta", id: c.id };
                      const marcada = sel.has(claveSel(s));
                      const compartida = c.permiso !== "dueño" || (c.compartido_con_n || 0) > 0;
                      const comunes = {
                        draggable: c.permiso === "dueño",
                        onDragStart: (e: DragEvent) => iniciarArrastre(e, s),
                        onDragOver: (e: DragEvent) => {
                          if (!aceptaSoltar(e, c)) return;
                          e.preventDefault();
                          if (sobreCarpeta !== c.id) setSobreCarpeta(c.id);
                        },
                        onDragLeave: () => sobreCarpeta === c.id && setSobreCarpeta(null),
                        onDrop: (e: DragEvent) => soltar(e, c),
                        onClick: (e: MouseEvent) => clicSel(e, s),
                        onDoubleClick: () => abrir(s),
                        onContextMenu: (e: MouseEvent) => abrirMenu(e, s),
                        className: (vista === "grilla" ? "ficha carpeta" : "fila") + (marcada ? " marcada" : "") + (sobreCarpeta === c.id ? " sobre" : ""),
                        tabIndex: 0,
                        role: "option",
                        "aria-selected": marcada,
                        onKeyDown: (e: React.KeyboardEvent) => e.key === " " && (e.preventDefault(), marcar(s, !marcada)),
                      };
                      return vista === "grilla" ? (
                        <div key={c.id} {...comunes}>
                          <div className="ficha-mini carpeta-grande" style={{ color: c.color || "var(--amarillo-oscuro)" }}>
                            {c.emoji ? <span className="ficha-emoji">{c.emoji}</span> : <Icono nombre="carpeta" tam={54} />}
                          </div>
                          <div className="ficha-pie">
                            <span className="ficha-nombre" title={c.nombre}>
                              {c.nombre}
                            </span>
                            <span className="ficha-sub suave">
                              {c.n_items ?? 0} elem.{compartida && <Icono nombre="compartir" tam={12} />}
                              {c.permiso !== "dueño" && ` · de ${c.dueno}`}
                            </span>
                          </div>
                          <button type="button" className="boton sutil chico icono-solo ficha-menu" onClick={(e) => abrirMenu(e, s)} aria-label={`Opciones de ${c.nombre}`}>
                            <Icono nombre="puntos" tam={16} />
                          </button>
                          <input type="checkbox" className="ficha-check" checked={marcada} onChange={(e) => marcar(s, e.target.checked)} onClick={(e) => e.stopPropagation()} aria-label={`Seleccionar ${c.nombre}`} />
                        </div>
                      ) : (
                        <div key={c.id} {...comunes}>
                          <input type="checkbox" checked={marcada} onChange={(e) => marcar(s, e.target.checked)} onClick={(e) => e.stopPropagation()} aria-label={`Seleccionar ${c.nombre}`} />
                          <span className="fila-nombre">
                            <Icono nombre="carpeta" tam={18} style={{ color: c.color || "var(--amarillo-oscuro)" }} /> {etiqueta(c)}
                            {compartida && <Icono nombre="compartir" tam={12} style={{ color: "var(--suave)" }} />}
                          </span>
                          <span className="suave">{c.permiso === "dueño" ? "vos" : c.dueno}</span>
                          <span className="suave">{fechaCorta(c.actualizado)}</span>
                          <button type="button" className="boton sutil chico icono-solo" onClick={(e) => abrirMenu(e, s)} aria-label={`Opciones de ${c.nombre}`}>
                            <Icono nombre="puntos" tam={16} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {itemsVis.length > 0 && (
                <section aria-label="Archivos">
                  <h2 className="drive-seccion">Archivos</h2>
                  <div className={"drive-" + vista}>
                    {vista === "lista" && (
                      <div className="fila cabecera" aria-hidden="true">
                        <span />
                        <span>Nombre</span>
                        <span>Tipo</span>
                        <span>Fecha</span>
                        <span />
                      </div>
                    )}
                    {itemsVis.map((it) => {
                      const s: Sel = { clase: "item", id: it.id };
                      const marcada = sel.has(claveSel(s));
                      const comunes = {
                        draggable: puedeEditar,
                        onDragStart: (e: DragEvent) => iniciarArrastre(e, s),
                        onClick: (e: MouseEvent) => clicSel(e, s),
                        onDoubleClick: () => abrir(s),
                        onContextMenu: (e: MouseEvent) => abrirMenu(e, s),
                        className: (vista === "grilla" ? "ficha archivo tipo-" + it.tipo : "fila") + (marcada ? " marcada" : "") + (it.existe ? "" : " no-existe"),
                        tabIndex: 0,
                        role: "option",
                        "aria-selected": marcada,
                        onKeyDown: (e: React.KeyboardEvent) => e.key === " " && (e.preventDefault(), marcar(s, !marcada)),
                      };
                      const estado = it.estado ? ESTADO_TXT[it.estado] || it.estado : null;
                      return vista === "grilla" ? (
                        <div key={it.id} {...comunes}>
                          <div className="ficha-mini">
                            <Miniatura it={it} />
                          </div>
                          <div className="ficha-pie">
                            <span className="ficha-nombre" title={it.titulo}>
                              <IconoTipo tipo={it.tipo} tam={14} /> {it.titulo}
                            </span>
                            <span className="ficha-sub suave">
                              {TIPO_TXT[it.tipo]}
                              {estado && ` · ${estado}`}
                              {it.canal && ` · ${it.canal}`}
                            </span>
                          </div>
                          <button type="button" className="boton sutil chico icono-solo ficha-menu" onClick={(e) => abrirMenu(e, s)} aria-label={`Opciones de ${it.titulo}`}>
                            <Icono nombre="puntos" tam={16} />
                          </button>
                          <input type="checkbox" className="ficha-check" checked={marcada} onChange={(e) => marcar(s, e.target.checked)} onClick={(e) => e.stopPropagation()} aria-label={`Seleccionar ${it.titulo}`} />
                        </div>
                      ) : (
                        <div key={it.id} {...comunes}>
                          <input type="checkbox" checked={marcada} onChange={(e) => marcar(s, e.target.checked)} onClick={(e) => e.stopPropagation()} aria-label={`Seleccionar ${it.titulo}`} />
                          <span className="fila-nombre">
                            <Miniatura it={it} chica /> {it.titulo}
                          </span>
                          <span className="suave">
                            {TIPO_TXT[it.tipo]}
                            {estado && ` · ${estado}`}
                          </span>
                          <span className="suave">{fechaCorta(it.fecha || it.agregado)}</span>
                          <button type="button" className="boton sutil chico icono-solo" onClick={(e) => abrirMenu(e, s)} aria-label={`Opciones de ${it.titulo}`}>
                            <Icono nombre="puntos" tam={16} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}
            </>
          )}
        </main>

        {detalles && (
          <aside className="drive-detalles tarjeta" aria-label="Detalles" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="boton sutil chico icono-solo drive-detalles-cerrar" onClick={() => setDetalles(false)} aria-label="Cerrar detalles">
              <Icono nombre="cruz" tam={16} />
            </button>
            {carpetaSel ? (
              <DetalleCarpeta p={carpetaSel} puedeEditar={carpetaSel.permiso !== "ver"} esDueno={esDuenoDe(carpetaSel)} onAbrir={() => abrir({ clase: "carpeta", id: carpetaSel.id })} onCompartir={() => setCompartiendo(carpetaSel)} onRenombrar={() => setRenombrando(carpetaSel)} onBorrar={() => setABorrar(carpetaSel)} onEditar={(d) => editarCarpeta(carpetaSel, d)} />
            ) : itemSel ? (
              <DetalleItem it={itemSel} puedeEditar={puedeEditar} onAbrir={() => abrir({ clase: "item", id: itemSel.id })} onMover={() => setMoviendo([{ clase: "item", id: itemSel.id }])} onQuitar={() => setAQuitar([itemSel])} />
            ) : seleccion.length > 1 ? (
              <div className="detalle-vacio suave">
                <Icono nombre="lista" tam={30} />
                <p>{seleccion.length} elementos seleccionados.</p>
              </div>
            ) : carpetaActual ? (
              <DetalleCarpeta p={carpetaActual} puedeEditar={puedeEditar} esDueno={esDuenoDe(carpetaActual)} actual compartidoCon={contenido?.compartido_con} onCompartir={() => setCompartiendo(carpetaActual)} onRenombrar={() => setRenombrando(carpetaActual)} onBorrar={() => setABorrar(carpetaActual)} onEditar={(d) => editarCarpeta(carpetaActual, d)} nItems={items.length} nSub={carpetas.length} />
            ) : (
              <div className="detalle-vacio suave">
                <Icono nombre="info" tam={30} />
                <p>Elegí una carpeta o un archivo para ver sus detalles.</p>
                <p className="chico">Clic derecho (o ⋮) abre el menú. Ctrl+clic selecciona varios. Arrastrá para mover.</p>
              </div>
            )}
          </aside>
        )}
      </div>

      {menu && <MenuOpciones s={menu.sobre} />}

      {nuevaCarpeta && (
        <FormNombre titulo={id ? "Nueva subcarpeta" : "Nuevo proyecto"} texto="Nombre" boton="Crear" onCerrar={() => setNuevaCarpeta(false)} onGuardar={crearCarpeta} />
      )}
      {renombrando && <FormNombre titulo="Renombrar la carpeta" texto="Nombre nuevo" boton="Guardar" inicial={renombrando.nombre} onCerrar={() => setRenombrando(null)} onGuardar={(n) => renombrar(renombrando, n)} />}
      {aBorrar && (
        <Modal titulo="¿Borrar esta carpeta?" onCerrar={() => setABorrar(null)} peligro>
          <p>
            <strong>{etiqueta(aBorrar)}</strong>
          </p>
          <p className="suave">Se borra la carpeta, sus subcarpetas y lo que tenga adentro como referencias. Las conversaciones, recortes y piezas NO se borran: siguen en su lugar. Esto no se puede deshacer.</p>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="boton" onClick={() => setABorrar(null)}>
              Cancelar
            </button>
            <button type="button" className="boton peligro" onClick={() => borrarCarpeta(aBorrar)}>
              <Icono nombre="tacho" /> Sí, borrar
            </button>
          </div>
        </Modal>
      )}
      {aQuitar && (
        <Modal titulo={aQuitar.length === 1 ? "¿Quitar del proyecto?" : `¿Quitar ${aQuitar.length} elementos del proyecto?`} onCerrar={() => setAQuitar(null)}>
          <ul className="detalle-lista">
            {aQuitar.slice(0, 6).map((i) => (
              <li key={i.id}>
                <IconoTipo tipo={i.tipo} tam={14} /> {i.titulo}
              </li>
            ))}
            {aQuitar.length > 6 && <li className="suave">y {aQuitar.length - 6} más…</li>}
          </ul>
          <p className="suave">Solo se saca de esta carpeta: la conversación, el recorte o la pieza siguen existiendo.</p>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="boton" onClick={() => setAQuitar(null)}>
              Cancelar
            </button>
            <button type="button" className="boton primario" onClick={() => quitar(aQuitar)}>
              Quitar
            </button>
          </div>
        </Modal>
      )}
      {moviendo && (
        <MoverA
          que={moviendo.length === 1 ? (moviendo[0].clase === "carpeta" ? `Carpeta «${proyectos.porId.get(moviendo[0].id)?.nombre || ""}»` : `«${items.find((i) => i.id === moviendo[0].id)?.titulo || ""}»`) : `${moviendo.length} elementos`}
          actualId={id || null}
          excluir={moviendo.filter((s) => s.clase === "carpeta").map((s) => s.id)}
          onCerrar={() => setMoviendo(null)}
          onElegir={(pid) => moverTodo(moviendo, pid)}
        />
      )}
      {compartiendo && <CompartirModal tipo="proyecto" itemId={compartiendo.id} nombre={etiqueta(compartiendo)} onCerrar={() => setCompartiendo(null)} onCambio={refrescar} />}
      {agregando && id && <AgregarModal proyectoId={id} yaEstan={items} onCerrar={() => setAgregando(false)} onAgregado={refrescar} />}
    </div>
  );
}

// ---------------- Panel de detalles ----------------
function DetalleCarpeta({ p, puedeEditar, esDueno, actual = false, compartidoCon, nItems, nSub, onAbrir, onCompartir, onRenombrar, onBorrar, onEditar }: { p: Proyecto; puedeEditar: boolean; esDueno: boolean; actual?: boolean; compartidoCon?: ContenidoProyecto["compartido_con"]; nItems?: number; nSub?: number; onAbrir?: () => void; onCompartir: () => void; onRenombrar: () => void; onBorrar: () => void; onEditar: (d: { descripcion?: string | null; color?: string | null; emoji?: string | null }) => void }) {
  const [desc, setDesc] = useState(p.descripcion || "");
  const [emoji, setEmoji] = useState(p.emoji || "");
  useEffect(() => {
    setDesc(p.descripcion || "");
    setEmoji(p.emoji || "");
  }, [p.id, p.descripcion, p.emoji]);
  return (
    <div className="detalle">
      <div className="detalle-icono" style={{ color: p.color || "var(--amarillo-oscuro)" }}>
        {p.emoji ? <span className="ficha-emoji">{p.emoji}</span> : <Icono nombre="carpeta" tam={56} />}
      </div>
      <h3>{p.nombre}</h3>
      <p className="suave chico">
        {actual ? "Esta carpeta" : "Carpeta"} · {p.permiso === "dueño" ? "tuya" : `de ${p.dueno} (${p.permiso === "ver" ? "solo ver" : "podés editar"})`}
      </p>
      <dl className="detalle-datos">
        {typeof nItems === "number" && (
          <>
            <dt>Contenido</dt>
            <dd>
              {nSub || 0} subcarpeta{nSub === 1 ? "" : "s"}, {nItems} archivo{nItems === 1 ? "" : "s"}
            </dd>
          </>
        )}
        {typeof nItems !== "number" && (
          <>
            <dt>Archivos</dt>
            <dd>{p.n_items ?? 0}</dd>
          </>
        )}
        <dt>Creada</dt>
        <dd>{fechaCorta(p.creado)}</dd>
        <dt>Actualizada</dt>
        <dd>{fechaCorta(p.actualizado)}</dd>
        {compartidoCon && (
          <>
            <dt>Compartida con</dt>
            <dd>{compartidoCon.length ? compartidoCon.map((c) => `${c.usuario} (${c.permiso})`).join(", ") : "nadie todavía"}</dd>
          </>
        )}
      </dl>
      {puedeEditar ? (
        <label className="detalle-campo">
          <span className="chico suave">Descripción</span>
          <textarea value={desc} onChange={(e) => setDesc(e.target.value)} onBlur={() => desc !== (p.descripcion || "") && onEditar({ descripcion: desc })} rows={3} placeholder="Para qué es esta carpeta" maxLength={400} />
        </label>
      ) : (
        p.descripcion && <p className="chico">{p.descripcion}</p>
      )}
      {puedeEditar && (
        <div className="detalle-campo">
          <span className="chico suave">Color y emoji</span>
          <div className="detalle-colores">
            {COLORES.map((c) => (
              <button key={c} type="button" className={"color-punto" + (p.color === c ? " elegido" : "")} style={{ background: c }} onClick={() => onEditar({ color: c })} aria-label={`Color ${c}`} />
            ))}
            <button type="button" className={"color-punto sin" + (!p.color ? " elegido" : "")} onClick={() => onEditar({ color: "" })} aria-label="Sin color" title="Sin color">
              ×
            </button>
            <input className="detalle-emoji" value={emoji} onChange={(e) => setEmoji(e.target.value)} onBlur={() => emoji !== (p.emoji || "") && onEditar({ emoji })} placeholder="😀" aria-label="Emoji" maxLength={4} />
          </div>
        </div>
      )}
      <div className="detalle-acciones">
        {onAbrir && (
          <button type="button" className="boton primario chico" onClick={onAbrir}>
            <Icono nombre="externo" tam={14} /> Abrir
          </button>
        )}
        {esDueno && (
          <button type="button" className="boton chico" onClick={onCompartir}>
            <Icono nombre="compartir" tam={14} /> Compartir
          </button>
        )}
        {puedeEditar && (
          <button type="button" className="boton chico" onClick={onRenombrar}>
            <Icono nombre="lapiz" tam={14} /> Renombrar
          </button>
        )}
        {esDueno && (
          <button type="button" className="boton peligro sutil chico" onClick={onBorrar}>
            <Icono nombre="tacho" tam={14} /> Borrar
          </button>
        )}
      </div>
    </div>
  );
}

function DetalleItem({ it, puedeEditar, onAbrir, onMover, onQuitar }: { it: ItemProyecto; puedeEditar: boolean; onAbrir: () => void; onMover: () => void; onQuitar: () => void }) {
  const estado = it.estado ? ESTADO_TXT[it.estado] || it.estado : null;
  return (
    <div className="detalle">
      <div className="detalle-mini">
        <Miniatura it={it} />
      </div>
      <h3>{it.titulo}</h3>
      <p className="suave chico">
        <IconoTipo tipo={it.tipo} tam={13} /> {TIPO_TXT[it.tipo]}
        {it.canal && ` · ${it.canal}`}
        {it.formato && ` · ${it.formato}`}
      </p>
      <dl className="detalle-datos">
        {estado && (
          <>
            <dt>Estado</dt>
            <dd>{estado}</dd>
          </>
        )}
        {it.fecha && (
          <>
            <dt>{it.tipo === "conversacion" ? "Última actividad" : "Creado"}</dt>
            <dd>{fechaCorta(it.fecha)}</dd>
          </>
        )}
        {it.dueno && (
          <>
            <dt>De</dt>
            <dd>{it.propio ? "vos" : it.dueno}</dd>
          </>
        )}
        <dt>Agregado</dt>
        <dd>
          {fechaCorta(it.agregado)} por {it.agregado_por}
        </dd>
        {it.tipo === "imagen" && it.url && (
          <>
            <dt>URL</dt>
            <dd className="detalle-url">
              <a href={it.url} target="_blank" rel="noreferrer">
                {it.url}
              </a>
            </dd>
          </>
        )}
      </dl>
      <div className="detalle-acciones">
        <button type="button" className="boton primario chico" onClick={onAbrir} disabled={!it.existe}>
          <Icono nombre="externo" tam={14} /> Abrir
        </button>
        {puedeEditar && (
          <button type="button" className="boton chico" onClick={onMover}>
            <Icono nombre="mover" tam={14} /> Mover
          </button>
        )}
        {puedeEditar && (
          <button type="button" className="boton sutil chico" onClick={onQuitar}>
            <Icono nombre="cruz" tam={14} /> Quitar
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------- Formularios ----------------
function FormNombre({ titulo, texto, boton, inicial = "", onCerrar, onGuardar }: { titulo: string; texto: string; boton: string; inicial?: string; onCerrar: () => void; onGuardar: (nombre: string) => Promise<void> }) {
  const [valor, setValor] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const n = valor.trim();
    if (!n) return;
    setGuardando(true);
    try {
      await onGuardar(n);
      onCerrar();
    } catch {
      /* ya avisó */
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Modal titulo={titulo} onCerrar={onCerrar} ancho={420}>
      <form onSubmit={enviar} className="form-nombre">
        <label>
          <span className="chico suave">{texto}</span>
          <input autoFocus value={valor} onChange={(e) => setValor(e.target.value)} maxLength={80} required />
        </label>
        <div className="acciones" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="boton" onClick={onCerrar} disabled={guardando}>
            Cancelar
          </button>
          <button type="submit" className="boton primario" disabled={guardando || !valor.trim()}>
            {guardando ? "…" : boton}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ---------------- Agregar: conversaciones, recortes, piezas (de la persona) o una imagen por URL ----------------
type Solapa = TipoItem;
interface Candidato {
  id: string;
  titulo: string;
  sub: string;
  miniatura: string | null;
}

function AgregarModal({ proyectoId, yaEstan, onCerrar, onAgregado }: { proyectoId: string; yaEstan: ItemProyecto[]; onCerrar: () => void; onAgregado: () => Promise<void> }) {
  const { avisar } = useToast();
  const { carpetaDe } = useProyectos();
  const [solapa, setSolapa] = useState<Solapa>("conversacion");
  const [lista, setLista] = useState<Candidato[] | null>(null);
  const [buscar, setBuscar] = useState("");
  const [elegidos, setElegidos] = useState<Set<string>>(new Set());
  const [url, setUrl] = useState("");
  const [tituloImg, setTituloImg] = useState("");
  const [guardando, setGuardando] = useState(false);
  const ya = useMemo(() => new Set(yaEstan.map((i) => i.tipo + ":" + i.item_id)), [yaEstan]);

  useEffect(() => {
    setLista(null);
    setElegidos(new Set());
    let vivo = true;
    (async () => {
      try {
        let l: Candidato[] = [];
        if (solapa === "conversacion") l = (await apiChat.conversaciones()).map((c) => ({ id: c.id, titulo: c.titulo || "Conversación", sub: fechaCorta(c.actualizado), miniatura: null }));
        else if (solapa === "recorte") l = (await api.recortes("mios")).map((c) => ({ id: c.id, titulo: c.titulo || c.video_id, sub: `${c.formato} · ${c.estado_texto}`, miniatura: c.miniatura }));
        else if (solapa === "pieza") l = (await apiProyectos.misPiezas()).piezas.map((p) => ({ id: p.id, titulo: p.titulo || (p.texto || "").slice(0, 70) || "Pieza", sub: `${p.canal} · ${ESTADO_TXT[p.estado] || p.estado}`, miniatura: p.imagen_url }));
        if (vivo) setLista(l);
      } catch (e) {
        if (vivo) {
          setLista([]);
          avisar(e instanceof ErrorApi ? e.message : "No pude leer la lista.", "error");
        }
      }
    })();
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solapa]);

  const q = buscar.trim().toLowerCase();
  const vis = (lista || []).filter((c) => !q || c.titulo.toLowerCase().includes(q));

  async function agregar() {
    setGuardando(true);
    let n = 0;
    try {
      if (solapa === "imagen") {
        const u = url.trim();
        if (!/^https?:\/\//.test(u)) {
          avisar("Pegá la URL de la imagen (empieza con http).", "error");
          return;
        }
        await apiProyectos.agregarItem(proyectoId, "imagen", u, { url: u, titulo: tituloImg.trim() || undefined });
        n = 1;
      } else {
        for (const id of elegidos) {
          await apiProyectos.agregarItem(proyectoId, solapa, id);
          n++;
        }
      }
      avisar(n === 1 ? "Agregado al proyecto." : `${n} elementos agregados al proyecto.`);
      await onAgregado();
      onCerrar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude agregar.", "error");
    } finally {
      setGuardando(false);
    }
  }

  const solapas: { k: Solapa; t: string }[] = [
    { k: "conversacion", t: "Conversaciones" },
    { k: "recorte", t: "Recortes" },
    { k: "pieza", t: "Piezas" },
    { k: "imagen", t: "Imagen" },
  ];
  return (
    <Modal titulo="Agregar al proyecto" onCerrar={onCerrar} ancho={560}>
      <div className="solapas" role="tablist" aria-label="Qué agregar">
        {solapas.map((s) => (
          <button key={s.k} role="tab" type="button" aria-selected={solapa === s.k} className={"solapa" + (solapa === s.k ? " activa" : "")} onClick={() => setSolapa(s.k)}>
            <IconoTipo tipo={s.k} tam={14} /> {s.t}
          </button>
        ))}
      </div>
      {solapa === "imagen" ? (
        <div className="agregar-imagen">
          <p className="suave chico">Una foto compuesta (del banco, con frase y logo) u otra imagen por su URL, para reutilizarla desde acá.</p>
          <label>
            <span className="chico suave">URL de la imagen</span>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" autoFocus />
          </label>
          <label>
            <span className="chico suave">Título (opcional)</span>
            <input value={tituloImg} onChange={(e) => setTituloImg(e.target.value)} placeholder="Frase del día con logo" maxLength={120} />
          </label>
          {/^https?:\/\//.test(url.trim()) && <img className="agregar-vista" src={url.trim()} alt="" />}
        </div>
      ) : (
        <>
          <div className="buscar" style={{ maxWidth: "none" }}>
            <Icono nombre="buscar" tam={16} />
            <input type="search" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar" aria-label="Buscar" />
          </div>
          <ul className="agregar-lista">
            {lista === null && <li className="suave chico">Cargando…</li>}
            {lista && vis.length === 0 && <li className="suave chico">{q ? "Nada coincide." : "No tenés nada de este tipo todavía."}</li>}
            {vis.map((c) => {
              const esta = ya.has(solapa + ":" + c.id);
              const otra = !esta ? carpetaDe(solapa, c.id) : null;
              const marcado = elegidos.has(c.id);
              return (
                <li key={c.id}>
                  <label className={"agregar-op" + (esta ? " ya" : "")}>
                    <input
                      type="checkbox"
                      checked={esta || marcado}
                      disabled={esta}
                      onChange={(e) =>
                        setElegidos((s) => {
                          const n = new Set(s);
                          if (e.target.checked) n.add(c.id);
                          else n.delete(c.id);
                          return n;
                        })
                      }
                    />
                    {c.miniatura ? <img src={c.miniatura} alt="" /> : <IconoTipo tipo={solapa} tam={18} />}
                    <span className="agregar-txt">
                      <span className="agregar-titulo">{c.titulo}</span>
                      <span className="suave chico">
                        {c.sub}
                        {esta && " · ya está acá"}
                        {otra && ` · está en «${otra.nombre}» (se mueve)`}
                      </span>
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </>
      )}
      <div className="acciones" style={{ justifyContent: "flex-end", marginTop: 12 }}>
        <button type="button" className="boton" onClick={onCerrar} disabled={guardando}>
          Cancelar
        </button>
        <button type="button" className="boton primario" onClick={agregar} disabled={guardando || (solapa === "imagen" ? !url.trim() : elegidos.size === 0)}>
          <Icono nombre="mas" tam={16} /> {guardando ? "…" : solapa === "imagen" ? "Agregar imagen" : `Agregar${elegidos.size ? ` (${elegidos.size})` : ""}`}
        </button>
      </div>
    </Modal>
  );
}
