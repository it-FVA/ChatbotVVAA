// Mis publicaciones (22/10, fase 3) = publicar_ui.mis_publicaciones: solapas por estado con conteos, tarjetas con canal, estado,
// fechas, miniatura, quién aprobó/rechazó y la nota, y las acciones Retomar (borradores), Eliminar (lo eliminable), Ver resultado
// (el posteo, la entrada o el borrador de WordPress) y Descargar HTML (newsletter).
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi, STREAMLIT_URL } from "../api";
import { apiPublicar } from "../apiPublicar";
import type { MisPublicaciones, Publicacion } from "../tiposPublicar";
import { fechaCorta, fechaLegible } from "../util/publicar";
import { Icono, type NombreIcono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { EstadoVacio, Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";

const ORDEN = ["Todas", "Pendientes", "Aprobadas", "Publicadas", "Borradores", "Rechazadas", "Pruebas"];

export default function Publicaciones() {
  const { avisar } = useToast();
  const [datos, setDatos] = useState<MisPublicaciones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [solapa, setSolapa] = useState("Todas");
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

  const ids = datos?.solapas[solapa] ?? [];
  const piezas = datos ? datos.piezas.filter((p) => solapa === "Todas" || ids.includes(p.id)) : null;

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
          <Icono nombre="mas" tam={16} /> Nueva pieza
        </Link>
      </header>
      <div className="solapas pub-solapas" role="tablist" aria-label="Estado de las piezas">
        {ORDEN.map((n) => {
          const cant = datos ? (n === "Todas" ? datos.piezas.length : (datos.solapas[n] || []).length) : null;
          return (
            <button key={n} role="tab" aria-selected={solapa === n} className={"solapa" + (solapa === n ? " activa" : "")} onClick={() => setSolapa(n)}>
              {n} {cant !== null && <span className="solapa-conteo">{cant}</span>}
            </button>
          );
        })}
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
      <div className="lista">{piezas?.map((p) => <TarjetaPublicacion key={p.id} p={p} onEliminar={() => setAEliminar(p)} />)}</div>
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
const ICONO_CANAL: Record<string, NombreIcono> = { instagram: "celular", facebook: "usuarios", wordpress: "externo", youtube: "pelicula", newsletter: "enviar" };

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

/** Una pieza del registro (publicar_ui._fila_publicacion), con o sin quién la hizo y con las acciones que se le pasen. */
export function TarjetaPublicacion({ p, mostrarUsuario = false, onEliminar, acciones }: { p: Publicacion; mostrarUsuario?: boolean; onEliminar?: () => void; acciones?: React.ReactNode }) {
  const esNewsletter = p.canal === "newsletter";
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
            <Icono nombre={ICONO_CANAL[p.canal] || "megafono"} tam={14} /> {p.canal_texto}
            {p.formato && p.formato !== "cuadrado" ? ` · ${p.formato}` : ""}
          </span>
          <span className="suave">creada {fechaCorta(p.creado)}</span>
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
              aprobó <strong>{p.aprobada_por}</strong> ({fechaCorta(p.aprobada_en)})
            </span>
          )}
          {p.rechazada_por && (
            <span>
              rechazó <strong>{p.rechazada_por}</strong> ({fechaCorta(p.rechazada_en)})
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
              <a className="boton primario" href={STREAMLIT_URL + "/?vista=mis"} target="_blank" rel="noreferrer" title="Los borradores de newsletter se retoman en el editor de Streamlit">
                <Icono nombre="externo" /> Retomar en Streamlit
              </a>
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
          {p.eliminable && onEliminar && (
            <button type="button" className="boton peligro sutil" onClick={onEliminar}>
              <Icono nombre="tacho" /> Eliminar
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
