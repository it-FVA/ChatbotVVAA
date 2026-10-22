// Aprobación (22/10, fase 3) = publicar_ui.panel_aprobacion, sección aparte para aprobadores: Para aprobar (vista previa completa,
// aprobar con fecha y hora editables, rechazar con nota), En cola (cancelar), Registro, Papelera de conversaciones (restaurar) y
// Clips de todo el equipo (la pantalla de recortes con la solapa «Todos» fija; los admins además fijan el estilo por defecto).
// Frase del día y Dashboard siguen en el Panel admin de Streamlit (fase siguiente).
import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useOutletContext } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { apiPublicar } from "../apiPublicar";
import { useSesion } from "../App";
import type { Estilo, Opciones } from "../tipos";
import type { ConversacionBorrada, Publicacion } from "../tiposPublicar";
import { fechaCorta, fechaLegible } from "../util/publicar";
import { ControlesEstilo } from "../componentes/Estilo";
import { Icono } from "../componentes/Iconos";
import { EstadoVacio, Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import VistaPrevia from "../componentes/VistaPrevia";
import Recortes from "./Recortes";
import { TarjetaPublicacion, descargarHtml } from "./Publicaciones";

const MENU: { a: string; texto: string; icono: string; fin?: boolean }[] = [
  { a: "/aprobacion", texto: "Para aprobar", icono: "reloj", fin: true },
  { a: "/aprobacion/cola", texto: "En cola", icono: "calendario" },
  { a: "/aprobacion/registro", texto: "Registro", icono: "info" },
  { a: "/aprobacion/papelera", texto: "Papelera", icono: "tacho" },
  { a: "/aprobacion/clips", texto: "Clips", icono: "pelicula" },
];

interface Ctx {
  pendientes: number | null;
  refrescarConteo: () => void;
}

export default function Aprobacion() {
  const { yo } = useSesion();
  const [pendientes, setPendientes] = useState<number | null>(null);
  const refrescarConteo = useCallback(() => {
    apiPublicar
      .paraAprobar()
      .then((d) => setPendientes(d.piezas.length))
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (yo?.rol.aprueba) refrescarConteo();
  }, [yo, refrescarConteo]);
  if (!yo?.rol.aprueba) return <Navigate to="/recortes" replace />;
  return (
    <div className="pagina admin aprobacion">
      <header className="pagina-cabecera">
        <div>
          <h1>Aprobación</h1>
          <p className="suave">Piezas para aprobar, la cola, el registro, la papelera y los clips del equipo. La Frase del día está en la barra; el Dashboard, en Administración.</p>
        </div>
      </header>
      <div className="admin-grilla">
        <nav className="admin-menu" aria-label="Aprobación">
          {MENU.map((m) => (
            <NavLink key={m.a} to={m.a} end={m.fin} className={({ isActive }) => "admin-link" + (isActive ? " activo" : "")}>
              <Icono nombre={m.icono} tam={16} /> {m.texto}
              {m.a === "/aprobacion" && pendientes !== null && pendientes > 0 && <span className="conteo-pendientes">{pendientes}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="admin-contenido">
          <Outlet context={{ pendientes, refrescarConteo } satisfies Ctx} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
export function ParaAprobar() {
  const { refrescarConteo } = useOutletContext<Ctx>();
  const { avisar } = useToast();
  const [piezas, setPiezas] = useState<Publicacion[] | null>(null);
  const [modos, setModos] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const d = await apiPublicar.paraAprobar();
      setPiezas(d.piezas);
      setModos(d.modos);
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer las piezas.");
      setPiezas([]);
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  function hecho(mensaje: string) {
    avisar(mensaje);
    cargar();
    refrescarConteo();
  }

  return (
    <section>
      <div className="seccion-cabecera">
        <h2>
          <Icono nombre="reloj" /> Para aprobar {piezas && <span className="chip">{piezas.length}</span>}
        </h2>
        <button type="button" className="boton chico" onClick={cargar}>
          <Icono nombre="regenerar" tam={14} /> Actualizar
        </button>
      </div>
      {error && <div className="aviso error">{error}</div>}
      {piezas === null && <Hueso ancho="100%" alto={220} radio={12} />}
      {piezas && piezas.length === 0 && !error && <EstadoVacio titulo="No hay piezas esperando aprobación" texto="Cuando alguien mande una pieza a aprobación desde el chat o desde Publicar, aparece acá con su vista previa." />}
      {piezas?.map((p) => <PiezaParaAprobar key={p.id} p={p} modo={modos[p.canal] || "?"} onHecho={hecho} />)}
    </section>
  );
}

function PiezaParaAprobar({ p, modo, onHecho }: { p: Publicacion; modo: string; onHecho: (m: string) => void }) {
  const [fecha, setFecha] = useState(p.fecha_sugerida || "");
  const [hora, setHora] = useState(p.hora_sugerida || "09:00");
  const [nota, setNota] = useState("");
  const [ocupado, setOcupado] = useState<"aprobar" | "rechazar" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esNewsletter = p.canal === "newsletter";

  async function accion(que: "aprobar" | "rechazar") {
    setOcupado(que);
    setError(null);
    try {
      const r = que === "aprobar" ? await apiPublicar.aprobar(p.id, fecha, hora) : await apiPublicar.rechazar(p.id, nota);
      onHecho(r.mensaje);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude conectarme con la API.");
    } finally {
      setOcupado(null);
    }
  }

  return (
    <article className="tarjeta aprobar">
      <div className="aprobar-cabecera">
        <strong>{p.canal_texto}</strong>
        <span className="suave">
          · propuso <strong>{p.propuesta_por || p.usuario}</strong> · {fechaCorta(p.creado)}
          {p.formato ? ` · formato ${p.formato}` : ""}
        </span>
      </div>
      <div className="aprobar-grilla">
        <div className="aprobar-previa">
          {esNewsletter ? (
            <iframe title={"Newsletter " + (p.titulo || "")} className="aprobar-iframe" sandbox="" srcDoc={p.texto || ""} />
          ) : (
            <VistaPrevia d={{ canal: p.canal, titulo: p.titulo || "", texto: p.texto || "", imagenSrc: p.imagen_url, videoUrl: p.video_url, formato: p.formato, fechaIso: p.fecha_programada, textoImagen: p.texto_imagen }} compacta />
          )}
        </div>
        <div className="aprobar-datos">
          {p.titulo && <h3>{p.titulo}</h3>}
          {!esNewsletter && <pre className="aprobar-texto">{p.texto}</pre>}
          {p.texto_imagen && <p className="suave chico">Sobre la imagen: «{p.texto_imagen}»</p>}
          {!esNewsletter && (
            <>
              <p className="suave chico">
                Fecha y hora que pidió: <strong>{p.fecha_programada ? fechaLegible(p.fecha_programada) : "cuanto antes"}</strong> · el canal hoy está en modo <strong>{modo}</strong> · podés cambiarla antes de aprobar.
              </p>
              <div className="pub-fecha">
                <label>
                  Sale el
                  <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
                </label>
                <label>
                  a las
                  <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} step={300} />
                </label>
              </div>
            </>
          )}
          <label>
            Nota <span className="suave">(si rechazás, decí por qué)</span>
            <input value={nota} onChange={(e) => setNota(e.target.value)} maxLength={300} />
          </label>
          {error && <div className="aviso error chico">{error}</div>}
          <div className="acciones">
            <button type="button" className="boton primario" onClick={() => accion("aprobar")} disabled={ocupado !== null || (!esNewsletter && !fecha)}>
              <Icono nombre="check" /> {ocupado === "aprobar" ? "Aprobando…" : esNewsletter ? "Aprobar (queda listo para Perfit)" : "Aprobar y programar"}
            </button>
            <button type="button" className="boton peligro" onClick={() => accion("rechazar")} disabled={ocupado !== null}>
              <Icono nombre="cruz" /> {ocupado === "rechazar" ? "Rechazando…" : "Rechazar"}
            </button>
            {esNewsletter && (
              <button type="button" className="boton" onClick={() => descargarHtml(p)}>
                <Icono nombre="descargar" /> Descargar HTML
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
export function Cola() {
  const { avisar } = useToast();
  const [piezas, setPiezas] = useState<Publicacion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const cargar = useCallback(async () => {
    try {
      setPiezas(await apiPublicar.cola());
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer la cola.");
      setPiezas([]);
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);
  async function cancelar(p: Publicacion) {
    setOcupado(p.id);
    try {
      await apiPublicar.cancelar(p.id);
      avisar("Pieza cancelada.");
      cargar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude cancelar.", "error");
    } finally {
      setOcupado(null);
    }
  }
  return (
    <section>
      <div className="seccion-cabecera">
        <h2>
          <Icono nombre="calendario" /> En cola {piezas && <span className="chip">{piezas.length}</span>}
        </h2>
        <p className="suave chico">La cola corre cada 15 minutos (GitHub Actions) y saca cada pieza en su fecha, con el modo que tenga el canal en ese momento.</p>
      </div>
      {error && <div className="aviso error">{error}</div>}
      {piezas === null && <Hueso ancho="100%" alto={160} radio={12} />}
      {piezas && piezas.length === 0 && !error && <EstadoVacio titulo="No hay piezas en cola" texto="Las piezas aprobadas con fecha, y las programadas para Instagram o Facebook, esperan acá hasta su día." />}
      <div className="lista">
        {piezas?.map((p) => (
          <TarjetaPublicacion
            key={p.id}
            p={p}
            mostrarUsuario
            acciones={
              <button type="button" className="boton peligro sutil" onClick={() => cancelar(p)} disabled={ocupado === p.id}>
                <Icono nombre="cruz" /> {ocupado === p.id ? "Cancelando…" : "Cancelar"}
              </button>
            }
          />
        ))}
      </div>
    </section>
  );
}

export function Registro() {
  const [piezas, setPiezas] = useState<Publicacion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [buscar, setBuscar] = useState("");
  useEffect(() => {
    apiPublicar
      .registro()
      .then(setPiezas)
      .catch((e) => {
        setError(e instanceof ErrorApi ? e.message : "No pude leer el registro.");
        setPiezas([]);
      });
  }, []);
  const b = buscar.trim().toLowerCase();
  const filtradas = piezas?.filter((p) => !b || [p.titulo, p.texto, p.usuario, p.propuesta_por, p.canal_texto, p.estado_texto].some((x) => (x || "").toLowerCase().includes(b)));
  return (
    <section>
      <div className="seccion-cabecera">
        <h2>
          <Icono nombre="info" /> Registro
        </h2>
        <div className="buscar">
          <Icono nombre="buscar" tam={16} />
          <input type="search" placeholder="Buscar por título, persona, canal o estado" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar en el registro" />
        </div>
      </div>
      <p className="suave chico">Quién creó cada pieza, quién la aprobó o rechazó, y qué pasó. Las últimas 60 (sin borradores, pruebas ni subidas de imágenes).</p>
      {error && <div className="aviso error">{error}</div>}
      {piezas === null && <Hueso ancho="100%" alto={160} radio={12} />}
      {filtradas && filtradas.length === 0 && !error && <EstadoVacio titulo={b ? "Nada coincide con la búsqueda" : "El registro está vacío"} />}
      <div className="lista">{filtradas?.map((p) => <TarjetaPublicacion key={p.id} p={p} mostrarUsuario />)}</div>
    </section>
  );
}

export function Papelera() {
  const { avisar } = useToast();
  const [datos, setDatos] = useState<{ conversaciones: ConversacionBorrada[]; dias: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const cargar = useCallback(async () => {
    try {
      setDatos(await apiPublicar.papelera());
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer la papelera.");
      setDatos({ conversaciones: [], dias: 30 });
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);
  async function restaurar(c: ConversacionBorrada) {
    setOcupado(c.id);
    try {
      await apiPublicar.restaurar(c.id);
      avisar("Restaurada: vuelve a aparecer en la lista de esa persona.");
      cargar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude restaurar.", "error");
    } finally {
      setOcupado(null);
    }
  }
  return (
    <section>
      <div className="seccion-cabecera">
        <h2>
          <Icono nombre="tacho" /> Papelera de conversaciones
        </h2>
      </div>
      <p className="suave chico">Conversaciones que alguien borró. Se restauran desde acá durante {datos?.dias ?? 30} días; después se borran de verdad.</p>
      {error && <div className="aviso error">{error}</div>}
      {datos === null && <Hueso ancho="100%" alto={120} radio={12} />}
      {datos && datos.conversaciones.length === 0 && !error && <EstadoVacio titulo="La papelera está vacía" />}
      {datos && datos.conversaciones.length > 0 && (
        <div className="tarjeta tabla-caja">
          <table className="tabla">
            <thead>
              <tr>
                <th>Conversación</th>
                <th>De</th>
                <th>Borrada</th>
                <th>Última actividad</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {datos.conversaciones.map((c) => (
                <tr key={c.id}>
                  <td data-col="Conversación">
                    <strong>{c.titulo || "(sin título)"}</strong>
                  </td>
                  <td data-col="De">{c.usuario}</td>
                  <td data-col="Borrada">{fechaCorta(c.borrada)}</td>
                  <td data-col="Última actividad">{fechaCorta(c.actualizado)}</td>
                  <td className="celda-acciones">
                    <button type="button" className="boton chico" onClick={() => restaurar(c)} disabled={ocupado === c.id}>
                      <Icono nombre="deshacer" tam={14} /> {ocupado === c.id ? "Restaurando…" : "Restaurar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function Clips() {
  const { yo } = useSesion();
  return (
    <section className="aprobacion-clips">
      <p className="suave chico">Recortes pedidos desde el chat por todo el equipo. Los corta la nube cada 15 minutos desde los originales en Drive. Los que fallaron se pueden reintentar.</p>
      {yo?.rol.admin && <EstiloDefecto />}
      <Recortes vistaFija="todos" />
    </section>
  );
}

/** publicar_ui.estilo_por_defecto_admin: el estilo con que salen los subtítulos de los recortes verticales nuevos (config clips_estilo). */
function EstiloDefecto() {
  const { avisar } = useToast();
  const [op, setOp] = useState<Opciones | null>(null);
  const [guardado, setGuardado] = useState<Estilo | null>(null);
  const [estilo, setEstilo] = useState<Estilo | null>(null);
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    api
      .opciones()
      .then((o) => {
        setOp(o);
        const e = o.estilo_equipo ?? o.estilo_defecto;
        setGuardado(e);
        setEstilo(e);
      })
      .catch(() => {});
  }, []);
  if (!op || !estilo || !guardado) return null;
  const cambio = JSON.stringify(estilo) !== JSON.stringify(guardado);
  async function guardar() {
    setGuardando(true);
    try {
      const r = await api.guardarEstiloDefecto(estilo!);
      setGuardado(r.estilo);
      setEstilo(r.estilo);
      setOp({ ...op!, estilo_equipo: r.estilo });
      avisar("Estilo por defecto guardado.");
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude guardar el estilo.", "error");
    } finally {
      setGuardando(false);
    }
  }
  return (
    <details className="tarjeta estilo-defecto" open={abierto} onToggle={(e) => setAbierto((e.target as HTMLDetailsElement).open)}>
      <summary>
        <Icono nombre="paleta" tam={16} /> Estilo por defecto de los subtítulos (recortes verticales nuevos)
      </summary>
      <p className="suave chico">Con este estilo salen los subtítulos de todos los recortes verticales que se pidan de acá en más. Los que ya están hechos no cambian; cada uno se ajusta desde «Editar».</p>
      <ControlesEstilo estilo={estilo} opciones={op} onCambio={setEstilo} />
      <div className="acciones">
        <button type="button" className="boton primario" onClick={guardar} disabled={!cambio || guardando}>
          <Icono nombre="check" /> {guardando ? "Guardando…" : "Guardar como estilo por defecto"}
        </button>
        {cambio && (
          <button type="button" className="boton" onClick={() => setEstilo(guardado)}>
            Deshacer
          </button>
        )}
      </div>
    </details>
  );
}
