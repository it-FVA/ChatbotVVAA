// Una pieza sola (4/11, Franco: «cuando quiero abrir una pieza que me comparten no se abre, me manda a Mis publicaciones y muere
// ahí»). /publicaciones/:id muestra la pieza en grande: la imagen o el video, el texto entero, el canal, el estado y quién la hizo.
// Si es de otra persona (llegó por un proyecto compartido o por «Del equipo») es solo lectura: se puede copiar el texto, bajar la
// imagen o «Usar como base», que abre Diseñar con una copia (la original no cambia). Si es propia, además «Retomar».
// (4/11) Con permiso «editar» (carpeta compartida para editar, o aprobador) aparece «Editar»: retoma la misma pieza, que sigue
// siendo de su dueña.
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ErrorApi } from "../api";
import { apiPublicar } from "../apiPublicar";
import type { Publicacion } from "../tiposPublicar";
import { useSesion } from "../App";
import { fechaCreacion, fechaLegible } from "../util/fechas";
import { Icono, type NombreIcono } from "../componentes/Iconos";
import { Hueso, Migas } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import { etiqueta, useProyectos } from "../componentes/proyectos/ProyectosContexto";
import { descargarHtml } from "./Publicaciones";
import "../publicar.css";
import "../proyectos.css";

/** Corta en la última palabra entera y agrega «…». */
function recortar(t: string, n: number) {
  t = t.trim();
  if (t.length <= n) return t;
  const corte = t.slice(0, n);
  const espacio = corte.lastIndexOf(" ");
  return (espacio > n * 0.6 ? corte.slice(0, espacio) : corte).replace(/[\s,.;:]+$/, "") + "…";
}

/** Lo que manda la vista de Proyectos al abrir un ítem, para que las migas vuelvan a esa carpeta. */
export interface DesdeCarpeta {
  desde?: { id: string; nombre: string };
}

export default function PiezaVer() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const loc = useLocation();
  const { avisar } = useToast();
  const { yo } = useSesion();
  const canales = yo?.canales || [];
  const proyectos = useProyectos();
  const [p, setP] = useState<Publicacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sinImagen, setSinImagen] = useState(false); // la URL de la imagen no carga (sacada del banco, por ejemplo)

  useEffect(() => {
    let vivo = true;
    setP(null);
    setError(null);
    apiPublicar
      .una(id)
      .then((x) => vivo && setP(x))
      .catch((e) => vivo && setError(e instanceof ErrorApi ? e.message : "No pude abrir la pieza."));
    return () => {
      vivo = false;
    };
  }, [id]);

  // Migas: la carpeta desde la que se abrió (o la carpeta donde está), si no «Mis publicaciones»
  const desde = (loc.state as DesdeCarpeta | null)?.desde;
  const carpeta = desde ? { id: desde.id, nombre: desde.nombre } : (() => {
    const c = proyectos.carpetaDe("pieza", id);
    return c ? { id: c.id, nombre: etiqueta(c) } : null;
  })();
  const titulo = p ? p.titulo || recortar((p.texto || "").split("\n")[0], 70) || p.canal_texto || "Pieza" : "Pieza";
  // una carpeta de otra persona cuelga de «Compartidos conmigo», como en la vista de carpetas
  const raiz = carpeta && proyectos.porId.get(carpeta.id)?.permiso !== "dueño" && proyectos.porId.has(carpeta.id) ? { texto: "Compartidos conmigo", a: "/compartidos" } : { texto: "Proyectos", a: "/proyectos" };
  const migas = carpeta ? [raiz, { texto: carpeta.nombre, a: `/proyectos/${carpeta.id}` }, { texto: titulo }] : [{ texto: "Mis publicaciones", a: "/publicaciones" }, { texto: titulo }];
  const volver = carpeta ? `/proyectos/${carpeta.id}` : "/publicaciones";

  if (error)
    return (
      <div className="pagina">
        <Migas pasos={migas} />
        <div className="aviso error">{error}</div>
        <Link className="boton" to={volver}>
          <Icono nombre="flechaIzq" /> Volver
        </Link>
      </div>
    );
  if (!p)
    return (
      <div className="pagina pieza-ver" aria-busy="true">
        <Hueso ancho={220} alto={14} />
        <div className="pieza-ver-grilla" style={{ marginTop: 16 }}>
          <Hueso ancho="100%" alto={360} radio={12} />
          <div>
            <Hueso ancho="60%" alto={24} />
            <Hueso ancho="100%" alto={14} style={{ marginTop: 16 }} />
            <Hueso ancho="90%" alto={14} style={{ marginTop: 8 }} />
            <Hueso ancho="70%" alto={14} style={{ marginTop: 8 }} />
          </div>
        </div>
      </div>
    );

  const propia = p.propia !== false;
  // (4/11) con permiso «editar» (carpeta compartida para editar, o aprobador) se edita la misma pieza, como la dueña
  const edita = propia || p.permiso === "editar";
  const esNewsletter = p.canal === "newsletter";
  const autor = p.propuesta_por || p.usuario || "otra persona";
  const icono = (canales.find((c) => c.clave === p.canal)?.icono as NombreIcono) || "megafono";

  async function copiarTexto() {
    try {
      await navigator.clipboard.writeText(p!.texto || "");
      avisar("Texto copiado.");
    } catch {
      avisar("No pude copiar: seleccioná el texto y copialo a mano.", "error");
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
              <Icono nombre={icono} tam={14} /> {p.canal_texto}
              {p.formato && p.formato !== "cuadrado" ? ` · ${p.formato}` : ""}
            </span>
            <span className="estado neutro">{p.estado_texto}</span>
            <span className="suave">creada {fechaCreacion(p.creado)}</span>
            {!propia && !edita && (
              <span className="chip suave" title="Es de otra persona: la podés ver y usar como base, no cambiarla.">
                <Icono nombre="compartir" tam={12} /> de {autor} · solo lectura
              </span>
            )}
            {!propia && edita && (
              <span className="chip suave" title="Es de otra persona y la compartieron con vos para editar: los cambios quedan en la misma pieza, que sigue siendo suya.">
                <Icono nombre="compartir" tam={12} /> de {p.usuario || autor} · podés editarla
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="pieza-ver-grilla">
        <div className={"pieza-ver-medio" + (p.formato === "historia" || p.formato === "vertical" || p.formato === "reel" ? " vertical" : "")}>
          {p.video_url ? (
            <video src={p.video_url} controls playsInline preload="metadata" />
          ) : p.imagen_url && !sinImagen ? (
            <a href={p.imagen_url} target="_blank" rel="noreferrer" title="Abrir la imagen en tamaño real">
              <img src={p.imagen_url} alt={p.texto_imagen || ""} onError={() => setSinImagen(true)} />
            </a>
          ) : (
            <div className="pieza-ver-sin">
              <Icono nombre={icono} tam={42} />
              <span className="suave chico">{sinImagen ? "La imagen no carga (puede que la hayan sacado del banco)" : "Sin imagen"}</span>
            </div>
          )}
        </div>

        <div className="pieza-ver-cuerpo">
          {esNewsletter ? (
            <p className="suave">Newsletter · plantilla {p.plantilla || "mensual"}. El contenido se baja como HTML.</p>
          ) : (
            p.texto && <div className="pieza-ver-texto">{p.texto}</div>
          )}
          {p.texto_imagen && (
            <p className="suave chico">
              Sobre la imagen: <strong>{p.texto_imagen}</strong>
            </p>
          )}
          <dl className="detalle-datos">
            <dt>De</dt>
            <dd>{propia ? "vos" : autor}</dd>
            {p.editada_por && (
              <>
                <dt>Editó</dt>
                <dd>{p.editada_por === yo?.usuario ? "vos" : p.editada_por}</dd>
              </>
            )}
            {p.fecha_programada && (
              <>
                <dt>Sale</dt>
                <dd>{fechaLegible(p.fecha_programada)}</dd>
              </>
            )}
            {p.aprobada_por && (
              <>
                <dt>Aprobó</dt>
                <dd>
                  {p.aprobada_por} ({fechaCreacion(p.aprobada_en)})
                </dd>
              </>
            )}
            {p.rechazada_por && (
              <>
                <dt>Rechazó</dt>
                <dd>
                  {p.rechazada_por} ({fechaCreacion(p.rechazada_en)})
                </dd>
              </>
            )}
            {p.corregida_por && (
              <>
                <dt>Corrigió</dt>
                <dd>{p.corregida_por === yo?.usuario ? "vos" : p.corregida_por}</dd>
              </>
            )}
            {p.nota && (
              <>
                <dt>Nota</dt>
                <dd>{p.nota}</dd>
              </>
            )}
            {carpeta && (
              <>
                <dt>Carpeta</dt>
                <dd>
                  <Link to={`/proyectos/${carpeta.id}`}>{carpeta.nombre}</Link>
                </dd>
              </>
            )}
          </dl>

          <div className="acciones">
            {edita && p.retomable && (
              <Link
                className="boton primario"
                to={esNewsletter ? `/newsletter?borrador=${encodeURIComponent(p.id)}` : `/publicar?borrador=${encodeURIComponent(p.id)}`}
                title={p.estado === "rechazada" ? "Abre la pieza con la nota del rechazo arriba. Cuando termines de corregirla, la volvés a mandar a aprobación." : undefined}
              >
                <Icono nombre="lapiz" /> {p.estado === "rechazada" || !propia ? "Editar" : "Retomar"}
              </Link>
            )}
            {!esNewsletter && (
              <button type="button" className={"boton" + (edita && p.retomable ? "" : " primario")} onClick={() => nav(`/publicar?base=${encodeURIComponent(p.id)}`)} title="Abre Diseñar con una copia de esta pieza: la original no cambia">
                <Icono nombre="mas" /> Usar como base
              </button>
            )}
            {esNewsletter && p.texto && (
              <button type="button" className="boton" onClick={() => descargarHtml(p)}>
                <Icono nombre="descargar" /> Descargar HTML
              </button>
            )}
            {!esNewsletter && p.texto && (
              <button type="button" className="boton" onClick={copiarTexto}>
                <Icono nombre="check" /> Copiar el texto
              </button>
            )}
            {p.imagen_url && !p.video_url && !sinImagen && (
              <a className="boton" href={p.imagen_url} target="_blank" rel="noreferrer" download>
                <Icono nombre="descargar" /> Bajar la imagen
              </a>
            )}
            {p.ver_url && (
              <a className="boton sutil" href={p.ver_url} target="_blank" rel="noreferrer">
                <Icono nombre="externo" /> Ver {p.canal === "wordpress" ? "la entrada" : "el posteo"}
              </a>
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
