// Un recorte que no se puede editar desde acá (4/11): de otra persona (llegó por un proyecto compartido o por «Del equipo») o todavía
// en proceso. Antes la pantalla decía solo «no se puede editar desde acá» y no dejaba hacer nada. Ahora muestra el video con los
// datos, y deja bajarlo o usarlo en una pieza. Editar: quien lo pidió, un aprobador o (4/11) quien lo tiene en una carpeta con
// permiso de edición (esos van directo al editor).
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, ErrorApi } from "../api";
import type { Detalle } from "../tipos";
import { mmss } from "../util/tiempo";
import { fechaCreacion } from "../util/fechas";
import { Icono } from "../componentes/Iconos";
import { Migas } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import { etiqueta, useProyectos } from "../componentes/proyectos/ProyectosContexto";
import type { DesdeCarpeta } from "./PiezaVer";
import "../proyectos.css";

export default function RecorteVer({ det }: { det: Detalle }) {
  const loc = useLocation();
  const { avisar } = useToast();
  const proyectos = useProyectos();
  const [descargando, setDescargando] = useState(false);
  const listo = det.estado === "listo" && !!det.url;
  const titulo = (det.titulo || det.video_id).slice(0, 80);

  const desde = (loc.state as DesdeCarpeta | null)?.desde;
  const enCarpeta = proyectos.carpetaDe("recorte", det.id);
  const carpeta = desde || (enCarpeta ? { id: enCarpeta.id, nombre: etiqueta(enCarpeta) } : null);
  // una carpeta de otra persona cuelga de «Compartidos conmigo», como en la vista de carpetas
  const raiz = carpeta && proyectos.porId.get(carpeta.id)?.permiso !== "dueño" && proyectos.porId.has(carpeta.id) ? { texto: "Compartidos conmigo", a: "/compartidos" } : { texto: "Proyectos", a: "/proyectos" };
  const migas = carpeta ? [raiz, { texto: carpeta.nombre, a: `/proyectos/${carpeta.id}` }, { texto: titulo }] : [{ texto: "Recortes", a: "/recortes" }, { texto: titulo }];
  const volver = carpeta ? `/proyectos/${carpeta.id}` : "/recortes";

  async function descargar() {
    setDescargando(true);
    try {
      const r = await api.descargarRecorte(det.id);
      const nombre = /filename="([^"]+)"/.exec(r.headers.get("content-disposition") || "")?.[1] || `recorte-${det.id}.mp4`;
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = nombre;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude bajar el video.", "error");
    } finally {
      setDescargando(false);
    }
  }

  return (
    <div className="pagina pieza-ver">
      <Migas pasos={migas} />
      <header className="pieza-ver-cabecera">
        <div>
          <h1>{titulo}</h1>
          <div className="publicacion-meta">
            <span>
              <Icono nombre={det.formato === "vertical" ? "celular" : "pelicula"} tam={14} /> Recorte {det.formato}
            </span>
            <span>
              {mmss(det.inicio_ms)}–{mmss(det.fin_ms)} · {(det.duracion_ms / 1000).toFixed(0)} s
            </span>
            <span className="suave">{det.estado_texto}</span>
            {!det.propio && (
              <span className="chip suave" title="Lo pidió otra persona: lo podés ver, bajar y usar en una pieza, no editarlo.">
                <Icono nombre="compartir" tam={12} /> de {det.pedido_por || "otra persona"} · solo lectura
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="pieza-ver-grilla">
        <div className={"pieza-ver-medio" + (det.formato === "vertical" ? " vertical" : "")}>
          {listo ? (
            <video src={det.url!} poster={det.miniatura ?? undefined} controls playsInline preload="metadata" />
          ) : det.miniatura ? (
            <img src={det.miniatura} alt="" />
          ) : (
            <div className="pieza-ver-sin">
              <Icono nombre="pelicula" tam={42} />
            </div>
          )}
        </div>
        <div className="pieza-ver-cuerpo">
          {!listo && <div className="aviso">Este recorte todavía no está listo: el video aparece cuando termine de procesarse (unos 15 minutos).</div>}
          {det.nota && <p className="suave chico">{det.nota}</p>}
          <dl className="detalle-datos">
            <dt>Pidió</dt>
            <dd>{det.propio ? "vos" : det.pedido_por || "—"}</dd>
            <dt>Creado</dt>
            <dd>{fechaCreacion(det.creado)}</dd>
            <dt>Video</dt>
            <dd>
              <a href={`https://www.youtube.com/watch?v=${det.video_id}&t=${Math.floor(det.inicio_ms / 1000)}s`} target="_blank" rel="noreferrer">
                el original en YouTube
              </a>
            </dd>
            {carpeta && (
              <>
                <dt>Carpeta</dt>
                <dd>
                  <Link to={`/proyectos/${carpeta.id}`}>{carpeta.nombre}</Link>
                </dd>
              </>
            )}
          </dl>
          {det.lineas?.length > 0 && (
            <details className="pieza-ver-subtitulos">
              <summary>Subtítulos ({det.lineas.length} líneas)</summary>
              <div className="pieza-ver-texto">{det.lineas.map((l) => l.texto).join("\n")}</div>
            </details>
          )}
          <div className="acciones">
            {listo && (
              <Link className="boton primario" to={`/publicar?recorte=${encodeURIComponent(det.id)}`} title="Diseñar una pieza con este recorte">
                <Icono nombre="mas" /> Usar en una pieza
              </Link>
            )}
            {listo && (
              <button type="button" className="boton" onClick={descargar} disabled={descargando} title="Bajar el mp4 tal cual está">
                <Icono nombre="descargar" /> {descargando ? "Bajando…" : "Descargar"}
              </button>
            )}
            <Link className="boton sutil" to={volver}>
              <Icono nombre="flechaIzq" /> Volver
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
