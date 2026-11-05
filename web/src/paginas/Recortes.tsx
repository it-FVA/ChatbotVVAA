import Cabecera from "../componentes/Cabecera";
import ChipEstado from "../componentes/ChipEstado";
import { definirAyuda } from "../ayuda/registro";
import { fechaHora } from "../util/fechas";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useSesion } from "../App";
import type { Recorte, Uso } from "../tipos";
import { mmss } from "../util/tiempo";
import { Icono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { EstadoVacio, TarjetaEsqueleto } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import SubirVideo from "../componentes/SubirVideo";
import MoverA from "../componentes/proyectos/MoverA";
import { apiProyectos } from "../apiProyectos";
import { etiqueta, useProyectos } from "../componentes/proyectos/ProyectosContexto";
import "../recortes.css";

type Vista = "mios" | "equipo" | "todos";

/** vistaFija (22/10): embebida en Aprobación → Clips con la solapa «Todos» fija y sin cabecera. */
// (5/11, Franco) Ayuda de esta pantalla: de acá salen la página /ayuda y la guía interactiva. Cada id es un data-ayuda="recortes.<id>" en el JSX.
definirAyuda("recortes", {
  titulo: "Mis recortes",
  que: "Los pedazos de video que pediste desde el chat. Tardan unos 15 minutos en estar listos, y aparecen acá solos.",
  pasos: [
    { texto: "En el chat, debajo de un video, tocá «Pedir el recorte» o «Pedir en vertical». Después esperá a que aparezca el video acá.", titulo: "Cómo se pide" },
    { id: "diseniar", texto: "«Diseñar» arma una pieza con el recorte." },
    { id: "editar", texto: "«Editar» cambia los tramos, quita pausas largas y corrige los subtítulos. Después, «Regenerar el recorte»." },
    { id: "descargar", texto: "«Descargar» baja el video." },
    { id: "subir", texto: "«Subir un video» sirve para un video editado afuera: entra como un recorte más." },
  ],
});

export default function Recortes({ vistaFija }: { vistaFija?: Vista } = {}) {
  const { yo } = useSesion();
  const { avisar } = useToast();
  const [vistaElegida, setVista] = useState<Vista>("mios");
  const vista: Vista = vistaFija ?? vistaElegida;
  const [buscar, setBuscar] = useState("");
  const [filas, setFilas] = useState<Recorte[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aBorrar, setABorrar] = useState<Recorte | null>(null);
  const [subiendo, setSubiendo] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setFilas(await api.recortes(vista, buscar));
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer los recortes.");
    }
  }, [vista, buscar]);

  useEffect(() => {
    setFilas(null);
    cargar();
  }, [cargar]);

  // Los recortes tardan ~15 min: mientras haya alguno en proceso, la lista se refresca sola cada minuto.
  useEffect(() => {
    if (!filas?.some((c) => c.estado === "pedido")) return;
    const t = setInterval(cargar, 60000);
    return () => clearInterval(t);
  }, [filas, cargar]);

  const aprueba = !!yo?.rol.aprueba;

  return (
    <div className={vistaFija ? "recortes-embebidos" : "pagina"}>
      {!vistaFija && (
        <Cabecera
          titulo="Mis recortes"
          subtitulo="Tus pedazos de video, listos para diseñar una pieza. Tardan unos 15 minutos. Borrá los que no vayas a usar: ocupan lugar."
          ayuda="recortes"
          acciones={
            <button className="boton primario" data-ayuda="recortes.subir" onClick={() => setSubiendo(true)}>
              <Icono nombre="enviar" /> Subir un video
            </button>
          }
        />
      )}

      {subiendo && (
        <SubirVideo
          onCerrar={() => setSubiendo(false)}
          onSubido={() => {
            setSubiendo(false);
            avisar("Video subido: ya está en tus recortes.");
            cargar();
          }}
        />
      )}

      <div className="filtros">
        <div className="solapas" role="tablist" aria-label="Qué recortes ver" hidden={!!vistaFija}>
          <button role="tab" aria-selected={vista === "mios"} className={"solapa" + (vista === "mios" ? " activa" : "")} onClick={() => setVista("mios")}>
            Míos
          </button>
          <button role="tab" aria-selected={vista === "equipo"} className={"solapa" + (vista === "equipo" ? " activa" : "")} onClick={() => setVista("equipo")}>
            <Icono nombre="usuarios" tam={15} /> Del equipo
          </button>
          {aprueba && (
            <button role="tab" aria-selected={vista === "todos"} className={"solapa" + (vista === "todos" ? " activa" : "")} onClick={() => setVista("todos")}>
              Todos
            </button>
          )}
        </div>
        <div className="buscar">
          <Icono nombre="buscar" tam={16} />
          <input type="search" placeholder="Buscar por título, video o quién lo pidió" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar recortes" />
        </div>
      </div>

      {vista === "equipo" && <p className="suave chico">Recortes que otras personas del equipo compartieron con el botón «Compartir» de sus recortes. Se pueden abrir y publicar; para cambiarlos o borrarlos, pedíselo a quien lo pidió o a un aprobador.</p>}
      {error && (
        <div className="aviso error">
          {error}{" "}
          <button type="button" className="boton chico" onClick={cargar}>
            Reintentar
          </button>
        </div>
      )}
      {filas === null && !error && (
        <div className="lista" aria-busy="true" aria-label="Cargando los recortes">
          <TarjetaEsqueleto vertical />
          <TarjetaEsqueleto />
          <TarjetaEsqueleto vertical />
        </div>
      )}
      {filas && filas.length === 0 && (
        <>
          {buscar ? (
            <EstadoVacio
              titulo="Ningún recorte coincide"
              texto={
                <>
                  No hay recortes con «{buscar}». Probá con otra palabra del título o el nombre de quien lo pidió.
                </>
              }
              accion={
                <button type="button" className="boton" onClick={() => setBuscar("")}>
                  <Icono nombre="cruz" /> Limpiar la búsqueda
                </button>
              }
            />
          ) : vista === "equipo" ? (
            <EstadoVacio titulo="Todavía no hay recortes del equipo" texto="Cuando otra persona comparta uno de sus recortes listos, va a aparecer acá para abrirlo o publicarlo." />
          ) : (
            <EstadoVacio
              titulo="Todavía no pediste ningún recorte"
              texto="Se piden desde los botones «Pedir el recorte» / «Pedir en vertical» debajo de cada video en el chat, o diciéndole al bot «pedime ese tramo en vertical»."
              accion={
                <Link className="boton primario" to="/chat">
                  <Icono nombre="chat" /> Ir al chat a pedir uno
                </Link>
              }
            />
          )}
        </>
      )}
      <div className="lista">
        {filas?.map((c) => (
          <Tarjeta key={c.id} c={c} mostrarQuien={vista !== "mios"} aprueba={aprueba} onBorrar={() => setABorrar(c)} onCambio={cargar} />
        ))}
      </div>

      {aBorrar && (
        <ConfirmarBorrado
          c={aBorrar}
          onCerrar={() => setABorrar(null)}
          onBorrado={() => {
            setABorrar(null);
            avisar("Recorte borrado.");
            cargar();
          }}
        />
      )}
    </div>
  );
}

function Tarjeta({ c, mostrarQuien, aprueba, onBorrar, onCambio }: { c: Recorte; mostrarQuien: boolean; aprueba: boolean; onBorrar: () => void; onCambio: () => void }) {
  const listo = c.estado === "listo" && !!c.url;
  const { avisar } = useToast();
  const [reintentando, setReintentando] = useState(false);
  const [compartiendo, setCompartiendo] = useState(false);
  const [descargando, setDescargando] = useState(false);
  // (22/10, proyectos) «Guardar en un proyecto»: la carpeta donde está, y el modal para elegir otra
  const proyectos = useProyectos();
  const carpeta = proyectos.carpetaDe("recorte", c.id);
  const [aProyecto, setAProyecto] = useState(false);

  async function reintentar() {
    setReintentando(true);
    try {
      await api.reintentar(c.id);
      avisar("Se vuelve a cortar: tarda unos 15 minutos.");
      onCambio();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude reintentar.", "error");
    } finally {
      setReintentando(false);
    }
  }

  // (3/11, reunión con Julián) «Descargar»: el mp4 crudo para editarlo afuera (Premiere). Va por la API porque WordPress es otro
  // origen y el navegador lo abriría en vez de guardarlo.
  async function descargar() {
    setDescargando(true);
    try {
      const r = await api.descargarRecorte(c.id);
      const nombre = /filename="([^"]+)"/.exec(r.headers.get("content-disposition") || "")?.[1] || `recorte-${c.id}.mp4`;
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

  // (2/11, Franco) «los clips se comparten cuando el usuario lo permite»: solo el dueño prende o apaga la marca
  async function compartir() {
    setCompartiendo(true);
    try {
      const r = await api.compartir(c.id, !c.compartido);
      avisar(r.compartido ? "Compartido con el equipo: ahora lo ven en «Del equipo»." : "Ya no está compartido con el equipo.");
      onCambio();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude cambiar si está compartido.", "error");
    } finally {
      setCompartiendo(false);
    }
  }

  return (
    <article className={"tarjeta recorte " + c.formato} aria-label={c.titulo || c.video_id}>
      <div className="recorte-mini">{listo ? <video src={c.url!} poster={c.miniatura ?? undefined} preload="metadata" controls muted playsInline /> : c.miniatura ? <img src={c.miniatura} alt="" /> : <div className="mini-vacia">{c.subido ? "subido" : null}</div>}</div>
      <div className="recorte-cuerpo">
        <h3>{(c.titulo || c.video_id).slice(0, 90)}</h3>
        <div className="recorte-meta">
          <span>{fechaHora(c.creado)}</span>
          <span>
            <Icono nombre={c.formato === "vertical" ? "celular" : "pelicula"} tam={14} /> {c.formato}
          </span>
          <span>
            {c.subido ? `${(c.duracion_ms / 1000).toFixed(0)} s` : `${mmss(c.inicio_ms)}–${mmss(c.fin_ms)} · ${(c.duracion_ms / 1000).toFixed(0)} s`}
          </span>
          <ChipEstado estado={c.regenerando ? "regenerando" : c.estado} texto={c.estado_texto} />
          {(c.sin_pausas || c.segmentos_hechos) && (
            <span title={c.sin_pausas ? `${c.sin_pausas.pausas} pausas sacadas` : undefined}>
              <Icono nombre="tijera" tam={13} /> editado
            </span>
          )}
          {mostrarQuien && (
            <span>
              {c.subido ? "subió" : "pidió"} <strong>{c.pedido_por || "—"}</strong>
            </span>
          )}
          {c.compartido && (
            <span title="Su dueño lo compartió con el equipo">
              <Icono nombre="usuarios" tam={13} /> compartido
            </span>
          )}
        </div>
        {c.nota && <p className="suave chico">{c.nota.slice(0, 160)}</p>}
        {c.estado === "error" && c.error && <p className="aviso error chico">{c.error.slice(0, 200)}</p>}
        <div className="acciones">
          {listo && (
            <Link className="boton" data-ayuda="recortes.diseniar" to={`/publicar?recorte=${encodeURIComponent(c.id)}`} title="Diseñar una pieza con este recorte para Instagram, Facebook, YouTube o como blogpost">
              <Icono nombre="enviar" /> Diseñar
            </Link>
          )}
          {c.puede_editar && (
            <Link className="boton" data-ayuda="recortes.editar" to={`/recortes/${c.id}`}>
              <Icono nombre="lapiz" /> Editar
            </Link>
          )}
          {listo && (
            <a className="boton" href={c.url!} target="_blank" rel="noreferrer">
              <Icono nombre="externo" /> Abrir
            </a>
          )}
          {listo && (
            <button type="button" className="boton" data-ayuda="recortes.descargar" onClick={descargar} disabled={descargando} title="Bajar el mp4 tal cual está, para editarlo con otro programa">
              <Icono nombre="descargar" /> {descargando ? "Bajando…" : "Descargar"}
            </button>
          )}
          {listo && (
            <Link className="boton sutil" to={`/newsletter?recorte=${encodeURIComponent(c.id)}`} title="Ponerlo en el bloque «Un recorte para ver» del newsletter">
              <Icono nombre="sobre" /> Llevar al newsletter
            </Link>
          )}
          {c.estado === "error" && aprueba && (
            <button className="boton" onClick={reintentar} disabled={reintentando}>
              <Icono nombre="regenerar" /> {reintentando ? "Reintentando…" : "Reintentar"}
            </button>
          )}
          {c.puede_compartir && (
            <button className="boton sutil" onClick={compartir} disabled={compartiendo} title={c.compartido ? "Dejar de mostrarlo en «Del equipo»" : "Mostrarlo en «Del equipo» para que otras personas lo abran o publiquen"}>
              <Icono nombre="usuarios" /> {compartiendo ? "…" : c.compartido ? "Dejar de compartir" : "Compartir"}
            </button>
          )}
          <button className="boton sutil" onClick={() => setAProyecto(true)} title={carpeta ? `Está en «${etiqueta(carpeta)}»; mover a otra carpeta` : "Guardar este recorte en un proyecto"}>
            <Icono nombre="carpeta" /> {carpeta ? etiqueta(carpeta) : "Proyecto"}
          </button>
          {c.puede_borrar && (
            <button className="boton peligro sutil" onClick={onBorrar}>
              <Icono nombre="tacho" /> Borrar
            </button>
          )}
        </div>
      </div>
      {aProyecto && (
        <MoverA
          titulo="Guardar en un proyecto"
          que={`Recorte «${(c.titulo || c.video_id).slice(0, 80)}»`}
          actualId={carpeta?.id}
          textoBoton="Guardar acá"
          onCerrar={() => setAProyecto(false)}
          onElegir={async (pid) => {
            try {
              await apiProyectos.agregarItem(pid, "recorte", c.id);
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

function ConfirmarBorrado({ c, onCerrar, onBorrado }: { c: Recorte; onCerrar: () => void; onBorrado: () => void }) {
  const [usos, setUsos] = useState<Uso[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [borrando, setBorrando] = useState(false);
  const listo = c.estado === "listo" && !!c.url;

  useEffect(() => {
    if (!c.url) {
      setUsos([]);
      return;
    }
    api.usos(c.id).then(setUsos).catch(() => setUsos([]));
  }, [c]);

  async function borrar() {
    setBorrando(true);
    setError(null);
    try {
      await api.borrar(c.id);
      onBorrado();
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude borrar el recorte.");
      setBorrando(false);
    }
  }

  return (
    <Modal titulo="¿Borrar este recorte?" onCerrar={onCerrar} peligro>
      <p>
        <strong>{(c.titulo || c.video_id).slice(0, 90)}</strong>
        <br />
        <span className="suave">
          {mmss(c.inicio_ms)}–{mmss(c.fin_ms)} · {c.formato}
        </span>
      </p>
      {listo ? <p className="suave">Se borra el archivo de WordPress y el registro. No se puede deshacer.</p> : <p className="suave">Se saca este pedido de la lista.</p>}
      {usos === null && <p className="suave chico">Viendo si alguna publicación lo usa…</p>}
      {usos && usos.length > 0 && (
        <div className="aviso">
          <Icono nombre="alerta" tam={16} /> Este recorte está usado en: {usos.slice(0, 4).map((u) => `${u.canal} (${u.estado})`).join(", ")}. Si lo borrás, un blogpost que lo tenga embebido se queda sin video;
          Instagram, Facebook y YouTube ya tienen su copia.
        </div>
      )}
      {error && <div className="aviso error">{error}</div>}
      <div className="acciones" style={{ justifyContent: "flex-end" }}>
        <button className="boton" onClick={onCerrar} disabled={borrando}>
          Cancelar
        </button>
        <button className="boton peligro" onClick={borrar} disabled={borrando || usos === null}>
          <Icono nombre="tacho" /> {borrando ? "Borrando…" : "Sí, borrar"}
        </button>
      </div>
    </Modal>
  );
}

