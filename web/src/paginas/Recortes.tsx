import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ErrorApi, STREAMLIT_URL } from "../api";
import { useSesion } from "../App";
import type { Recorte, Uso } from "../tipos";
import { mmss } from "../util/tiempo";
import { Icono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { EstadoVacio, TarjetaEsqueleto } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";

type Vista = "mios" | "equipo" | "todos";

export default function Recortes() {
  const { yo } = useSesion();
  const { avisar } = useToast();
  const [vista, setVista] = useState<Vista>("mios");
  const [buscar, setBuscar] = useState("");
  const [filas, setFilas] = useState<Recorte[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aBorrar, setABorrar] = useState<Recorte | null>(null);

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
    <div className="pagina">
      <header className="pagina-cabecera">
        <h1>Recortes</h1>
        <p className="suave">Los recortes tardan unos 15 minutos. Cuando están listos aparece el video y los botones. Borrá los que no vayas a usar: cada uno ocupa entre 5 y 50 MB en WordPress.</p>
      </header>

      <div className="filtros">
        <div className="solapas" role="tablist" aria-label="Qué recortes ver">
          <button role="tab" aria-selected={vista === "mios"} className={"solapa" + (vista === "mios" ? " activa" : "")} onClick={() => setVista("mios")}>
            Mis recortes
          </button>
          <button role="tab" aria-selected={vista === "equipo"} className={"solapa" + (vista === "equipo" ? " activa" : "")} onClick={() => setVista("equipo")}>
            <Icono nombre="usuarios" tam={15} /> Del equipo
          </button>
          {aprueba && (
            <button role="tab" aria-selected={vista === "todos"} className={"solapa" + (vista === "todos" ? " activa" : "")} onClick={() => setVista("todos")}>
              Todos (admin)
            </button>
          )}
        </div>
        <div className="buscar">
          <Icono nombre="buscar" tam={16} />
          <input type="search" placeholder="Buscar por título, video o quién lo pidió" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar recortes" />
        </div>
      </div>

      {vista === "equipo" && <p className="suave chico">Recortes listos que pidieron otras personas del equipo. Se pueden abrir y publicar; para cambiarlos o borrarlos, pedíselo a quien lo pidió o a un aprobador.</p>}
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
            <EstadoVacio titulo="Todavía no hay recortes del equipo" texto="Cuando otra persona pida un recorte y esté listo, va a aparecer acá para abrirlo o publicarlo." />
          ) : (
            <EstadoVacio
              titulo="Todavía no pediste ningún recorte"
              texto="Se piden desde los botones «Pedir el recorte» / «Pedir en vertical» debajo de cada video en el chat, o diciéndole al bot «pedime ese tramo en vertical»."
              accion={
                <a className="boton primario" href={STREAMLIT_URL} target="_blank" rel="noreferrer">
                  <Icono nombre="chat" /> Ir al chat a pedir uno
                </a>
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
  const clase = c.regenerando ? "proceso" : c.estado;

  async function reintentar() {
    setReintentando(true);
    try {
      await api.reintentar(c.id);
      avisar("Vuelto a poner en la cola.");
      onCambio();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude reintentar.", "error");
    } finally {
      setReintentando(false);
    }
  }

  return (
    <article className={"tarjeta recorte " + c.formato} aria-label={c.titulo || c.video_id}>
      <div className="recorte-mini">{listo ? <video src={c.url!} poster={c.miniatura ?? undefined} preload="metadata" controls muted playsInline /> : c.miniatura ? <img src={c.miniatura} alt="" /> : <div className="mini-vacia" />}</div>
      <div className="recorte-cuerpo">
        <h3>{(c.titulo || c.video_id).slice(0, 90)}</h3>
        <div className="recorte-meta">
          <span>{fecha(c.creado)}</span>
          <span>
            <Icono nombre={c.formato === "vertical" ? "celular" : "pelicula"} tam={14} /> {c.formato}
          </span>
          <span>
            {mmss(c.inicio_ms)}–{mmss(c.fin_ms)} · {(c.duracion_ms / 1000).toFixed(0)} s
          </span>
          <span className={"estado " + clase}>
            <Icono nombre={c.estado === "listo" ? "check" : c.estado === "error" ? "alerta" : "reloj"} tam={14} /> {c.estado_texto}
          </span>
          {c.sin_pausas && (
            <span title={`${c.sin_pausas.pausas} pausas sacadas`}>
              <Icono nombre="tijera" tam={13} /> sin pausas ({c.sin_pausas.antes.toFixed(0)} s → {c.sin_pausas.despues.toFixed(0)} s)
            </span>
          )}
          {c.segmentos_hechos && (
            <span>
              <Icono nombre="tijera" tam={13} /> {c.segmentos_hechos.length === 1 ? "1 pedazo conservado" : `${c.segmentos_hechos.length} pedazos conservados`}
            </span>
          )}
          {mostrarQuien && (
            <span>
              pidió <strong>{c.pedido_por || "—"}</strong>
            </span>
          )}
        </div>
        {c.nota && <p className="suave chico">{c.nota.slice(0, 160)}</p>}
        {c.estado === "error" && c.error && <p className="aviso error chico">{c.error.slice(0, 200)}</p>}
        <div className="acciones">
          {c.puede_editar && (
            <Link className="boton primario" to={`/recortes/${c.id}`}>
              <Icono nombre="lapiz" /> Editar
            </Link>
          )}
          {listo && (
            <a className="boton" href={c.url!} target="_blank" rel="noreferrer">
              <Icono nombre="externo" /> Abrir
            </a>
          )}
          {c.estado === "error" && aprueba && (
            <button className="boton" onClick={reintentar} disabled={reintentando}>
              <Icono nombre="regenerar" /> {reintentando ? "Reintentando…" : "Reintentar"}
            </button>
          )}
          {c.puede_borrar && (
            <button className="boton peligro sutil" onClick={onBorrar}>
              <Icono nombre="tacho" /> Borrar
            </button>
          )}
        </div>
      </div>
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

function fecha(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}
