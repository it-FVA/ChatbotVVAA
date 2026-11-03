// Mis publicaciones (22/10, fase 3) : solapas por estado con conteos, tarjetas con canal, estado,
// fechas, miniatura, quién aprobó/rechazó y la nota, y las acciones Retomar (borradores), Eliminar (lo eliminable), Ver resultado
// (el posteo, la entrada o el borrador de WordPress) y Descargar HTML (newsletter).
import { fechaCreacion, fechaLegible } from "../util/fechas";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi } from "../api";
import { apiPublicar } from "../apiPublicar";
import type { MisPublicaciones, Publicacion } from "../tiposPublicar";
import type { CanalInfo } from "../tipos";
import { useSesion } from "../App";
import { nombreCanal } from "../util/publicar";
import { Icono, type NombreIcono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { EstadoVacio, Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import MoverA from "../componentes/proyectos/MoverA";
import { apiProyectos } from "../apiProyectos";
import { etiqueta, useProyectos } from "../componentes/proyectos/ProyectosContexto";

const ORDEN = ["Todas", "Pendientes", "Aprobadas", "Publicadas", "Borradores", "Rechazadas", "Pruebas", "Del equipo"];
// (2/11, Franco) filtro por tipo de pieza: canal + formato (historia / posteo de Instagram, Facebook, blogpost, YouTube, newsletter…).
// (3/11) Los nombres salen del registro de la API (yo.canales); el formato de Instagram se agrega acá.
function tipoDe(p: Publicacion): string {
  if (p.canal === "instagram" && (p.formato === "historia" || p.formato === "reel")) return `instagram:${p.formato}`;
  return p.canal;
}
function nombreTipo(canales: CanalInfo[], t: string): string {
  const [canal, formato] = t.split(":");
  const nombre = nombreCanal(canales, canal);
  if (canal === "instagram") return `${nombre} · ${formato || "posteo"}`;
  return nombre;
}

export default function Publicaciones() {
  const { avisar } = useToast();
  const canales = useSesion().yo?.canales || [];
  const [datos, setDatos] = useState<MisPublicaciones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [solapa, setSolapa] = useState("Todas");
  const [tipo, setTipo] = useState("");
  const [equipo, setEquipo] = useState<MisPublicaciones | null>(null);
  const [aEliminar, setAEliminar] = useState<Publicacion | null>(null);

  const cargar = useCallback(async () => {
    try {
      setDatos(await apiPublicar.mias());
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer tus piezas.");
      setDatos({ piezas: [], grupos: {}, solapas: {}, eliminables: [] });
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  useEffect(() => {
    if (solapa === "Del equipo" && equipo === null) apiPublicar.delEquipo().then(setEquipo).catch(() => setEquipo({ piezas: [], grupos: {}, solapas: {}, eliminables: [] }));
  }, [solapa, equipo]);
  const ids = datos?.solapas[solapa] ?? [];
  const base = solapa === "Del equipo" ? equipo?.piezas ?? null : datos ? datos.piezas.filter((p) => solapa === "Todas" || ids.includes(p.id)) : null;
  const piezas = base ? base.filter((p) => !tipo || tipoDe(p) === tipo) : null;
  const tipos = Array.from(new Set((solapa === "Del equipo" ? equipo?.piezas ?? [] : datos?.piezas ?? []).map(tipoDe)));

  async function eliminar(p: Publicacion) {
    try {
      await apiPublicar.eliminar(p.id);
      avisar("Pieza eliminada.");
      setAEliminar(null);
      cargar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude eliminar la pieza.", "error");
    }
  }

  return (
    <div className="pagina publicaciones">
      <header className="pagina-cabecera">
        <div>
          <h1>Mis publicaciones</h1>
          <p className="suave">Todas las piezas que mandaste: pendientes, aprobadas, rechazadas, publicadas, borradores y pruebas.</p>
        </div>
        <Link to="/publicar" className="boton primario">
          <Icono nombre="mas" tam={16} /> Diseñar una pieza
        </Link>
      </header>
      <div className="solapas pub-solapas" role="tablist" aria-label="Estado de las piezas">
        {ORDEN.map((n) => {
          const cant = n === "Del equipo" ? (equipo ? equipo.piezas.length : null) : datos ? (n === "Todas" ? datos.piezas.length : (datos.solapas[n] || []).length) : null;
          return (
            <button key={n} role="tab" aria-selected={solapa === n} className={"solapa" + (solapa === n ? " activa" : "")} onClick={() => setSolapa(n)}>
              {n} {cant !== null && <span className="solapa-conteo">{cant}</span>}
            </button>
          );
        })}
      </div>
      <div className="pub-filtro-tipo chico">
        <label>
          Tipo{" "}
          <select value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Filtrar por tipo de pieza">
            <option value="">todos</option>
            {tipos.map((t) => (
              <option key={t} value={t}>
                {nombreTipo(canales, t)}
              </option>
            ))}
          </select>
        </label>
        {solapa === "Del equipo" && <span className="suave">Piezas que otras personas compartieron con el botón «Compartir». Se ven y se guardan en un proyecto; no se retoman ni se borran.</span>}
      </div>
      {error && (
        <div className="aviso error">
          {error}{" "}
          <button type="button" className="boton chico" onClick={cargar}>
            Reintentar
          </button>
        </div>
      )}
      {piezas === null && (
        <div className="lista" aria-busy="true">
          {[1, 2, 3].map((i) => (
            <div key={i} className="tarjeta publicacion esqueleto">
              <Hueso ancho={120} alto={120} radio={10} />
              <div style={{ flex: 1 }}>
                <Hueso ancho="40%" alto={16} />
                <Hueso ancho="70%" style={{ marginTop: 10 }} />
                <Hueso ancho="55%" style={{ marginTop: 8 }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {piezas && piezas.length === 0 && !error && (
        <EstadoVacio
          titulo={solapa === "Todas" ? "Todavía no mandaste ninguna pieza" : "Nada acá por ahora"}
          texto={solapa === "Todas" ? "Las piezas nacen en el chat (el bot propone una y la mandás) o desde «Nueva pieza»." : "Cuando una pieza pase a este estado, va a aparecer acá."}
          accion={
            solapa === "Todas" ? (
              <Link className="boton primario" to="/chat">
                <Icono nombre="chat" /> Ir al chat
              </Link>
            ) : undefined
          }
        />
      )}
      <div className="lista">{piezas?.map((p) => <TarjetaPublicacion key={p.id} p={p} mostrarUsuario={solapa === "Del equipo"} onEliminar={() => setAEliminar(p)} onCambio={cargar} />)}</div>
      {aEliminar && (
        <Modal titulo="¿Eliminar esta pieza?" onCerrar={() => setAEliminar(null)} peligro>
          <p>
            <strong>{aEliminar.titulo || (aEliminar.texto || "").slice(0, 80) || aEliminar.canal_texto}</strong>
            <br />
            <span className="suave">
              {aEliminar.canal_texto} · {aEliminar.estado_texto}
            </span>
          </p>
          <p className="suave">Se borra del registro. No se puede deshacer.</p>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button className="boton" onClick={() => setAEliminar(null)}>
              Cancelar
            </button>
            <button className="boton peligro" onClick={() => eliminar(aEliminar)}>
              <Icono nombre="tacho" /> Sí, eliminar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

const ICONO_ESTADO: Record<string, NombreIcono> = { a_aprobar: "reloj", pendiente: "calendario", programada: "calendario", publicada: "check", PUBLICADO: "check", draft: "lapiz", lista: "check", borrador: "lapiz", rechazada: "cruz", cancelada: "cruz", error: "alerta", prueba: "ojo", simulada: "ojo", simulado: "ojo" };
const CLASE_ESTADO: Record<string, string> = { a_aprobar: "proceso", pendiente: "ok", programada: "ok", publicada: "listo", PUBLICADO: "listo", draft: "ok", lista: "listo", borrador: "neutro", rechazada: "error", cancelada: "neutro", error: "error", prueba: "neutro", simulada: "neutro", simulado: "neutro" };

export function descargarHtml(p: Publicacion) {
  const blob = new Blob([p.texto || ""], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `newsletter-${String(p.creado || "").slice(0, 10)}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10000);
}

/** Una pieza del registro, con o sin quién la hizo y con las acciones que se le pasen. */
export function TarjetaPublicacion({ p, mostrarUsuario = false, onEliminar, onCambio, acciones }: { p: Publicacion; mostrarUsuario?: boolean; onEliminar?: () => void; onCambio?: () => void; acciones?: React.ReactNode }) {
  const esNewsletter = p.canal === "newsletter";
  // (2/11, Franco) «Compartir» como en Mis recortes: la dueña la muestra en «Del equipo» de las demás
  const [compartiendo, setCompartiendo] = useState(false);
  async function compartir() {
    setCompartiendo(true);
    try {
      const r = await apiPublicar.compartir(p.id, !p.compartido);
      avisar(r.compartido ? "Compartida con el equipo: aparece en «Del equipo» de las demás personas." : "Ya no está compartida.");
      onCambio?.();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude cambiar el compartido.", "error");
    } finally {
      setCompartiendo(false);
    }
  }
  // (22/10, Franco: "la misma lógica para todo") «Guardar en un proyecto», igual que en Mis recortes: la carpeta donde está y el modal para elegir otra.
  const { avisar } = useToast();
  const proyectos = useProyectos();
  const canales = useSesion().yo?.canales || [];
  const carpeta = proyectos.carpetaDe("pieza", p.id);
  const [aProyecto, setAProyecto] = useState(false);
  return (
    <article className="tarjeta publicacion" aria-label={p.titulo || p.canal_texto}>
      <div className="publicacion-mini">
        {p.video_url ? <video src={p.video_url} preload="metadata" muted playsInline controls /> : p.imagen_url ? <img src={p.imagen_url} alt="" loading="lazy" /> : <div className="mini-vacia" />}
      </div>
      <div className="publicacion-cuerpo">
        <div className="publicacion-meta">
          <span className={"estado " + (CLASE_ESTADO[p.estado] || "neutro")}>
            <Icono nombre={ICONO_ESTADO[p.estado] || "info"} tam={14} /> {p.estado_texto}
          </span>
          <span>
            <Icono nombre={(canales.find((c) => c.clave === p.canal)?.icono as NombreIcono) || "megafono"} tam={14} /> {p.canal_texto}
            {p.formato && p.formato !== "cuadrado" ? ` · ${p.formato}` : ""}
          </span>
          <span className="suave">creada {fechaCreacion(p.creado)}</span>
          {mostrarUsuario && (
            <span>
              por <strong>{p.propuesta_por || p.usuario}</strong>
            </span>
          )}
        </div>
        {p.titulo && <h3>{p.titulo}</h3>}
        {esNewsletter ? <p className="suave chico">Newsletter · plantilla {p.plantilla || "mensual"}</p> : p.texto && <p className="publicacion-texto">{p.texto.slice(0, 220) + (p.texto.length > 220 ? "…" : "")}</p>}
        {p.texto_imagen && <p className="suave chico">Sobre la imagen: «{p.texto_imagen}»</p>}
        <div className="publicacion-detalle suave chico">
          {p.fecha_programada && (
            <span>
              <Icono nombre="calendario" tam={13} /> sale el {fechaLegible(p.fecha_programada)}
            </span>
          )}
          {p.aprobada_por && (
            <span>
              aprobó <strong>{p.aprobada_por}</strong> ({fechaCreacion(p.aprobada_en)})
            </span>
          )}
          {p.rechazada_por && (
            <span>
              rechazó <strong>{p.rechazada_por}</strong> ({fechaCreacion(p.rechazada_en)})
            </span>
          )}
          {p.nota && <span>nota: «{p.nota}»</span>}
          {p.cancelada_por && (
            <span>
              canceló <strong>{p.cancelada_por}</strong>
            </span>
          )}
          {p.error_texto && <span className="rojo">error: {p.error_texto}</span>}
        </div>
        <div className="acciones">
          {p.retomable &&
            (esNewsletter ? (
              <Link className="boton primario" to={`/newsletter?borrador=${encodeURIComponent(p.id)}`}>
                <Icono nombre="lapiz" /> Retomar
              </Link>
            ) : (
              <Link className="boton primario" to={`/publicar?borrador=${encodeURIComponent(p.id)}`}>
                <Icono nombre="lapiz" /> Retomar
              </Link>
            ))}
          {p.ver_url && (
            <a className="boton" href={p.ver_url} target="_blank" rel="noreferrer">
              <Icono nombre="externo" /> Ver {p.canal === "wordpress" ? "la entrada" : "el posteo"}
            </a>
          )}
          {p.link_editar && (
            <a className="boton" href={p.link_editar} target="_blank" rel="noreferrer">
              <Icono nombre="externo" /> Abrir en WordPress
            </a>
          )}
          {esNewsletter && p.texto && (
            <button type="button" className="boton" onClick={() => descargarHtml(p)}>
              <Icono nombre="descargar" /> Descargar HTML
            </button>
          )}
          {acciones}
          {p.puede_compartir && (
            <button type="button" className="boton sutil" onClick={compartir} disabled={compartiendo} title={p.compartido ? "Dejar de mostrarla en «Del equipo»" : "Mostrarla en «Del equipo» para que otras personas la vean"}>
              <Icono nombre="usuarios" /> {compartiendo ? "…" : p.compartido ? "Dejar de compartir" : "Compartir"}
            </button>
          )}
          <button type="button" className="boton sutil" onClick={() => setAProyecto(true)} title={carpeta ? `Está en «${etiqueta(carpeta)}»; mover a otra carpeta` : "Guardar esta pieza en un proyecto"}>
            <Icono nombre="carpeta" /> {carpeta ? etiqueta(carpeta) : "Proyecto"}
          </button>
          {p.eliminable && onEliminar && (
            <button type="button" className="boton peligro sutil" onClick={onEliminar}>
              <Icono nombre="tacho" /> Eliminar
            </button>
          )}
        </div>
      </div>
      {aProyecto && (
        <MoverA
          titulo="Guardar en un proyecto"
          que={`Pieza «${(p.titulo || p.texto || p.canal_texto || "").slice(0, 80)}»`}
          actualId={carpeta?.id}
          textoBoton="Guardar acá"
          onCerrar={() => setAProyecto(false)}
          onElegir={async (pid) => {
            try {
              await apiProyectos.agregarItem(pid, "pieza", p.id);
              await proyectos.recargar();
              avisar(`Guardado en «${proyectos.porId.get(pid)?.nombre || "la carpeta"}».`);
            } catch (e) {
              avisar(e instanceof ErrorApi ? e.message : "No pude guardarlo.", "error");
              throw e;
            }
          }}
        />
      )}
    </article>
  );
}
