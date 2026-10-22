// «Editar recorte» con editor visual (fase 1 + revisión UX): reproductor + línea de tiempo con miniaturas, onda, zoom y manijas
// grandes; partir y sacar pedazos (clic selecciona, Supr saca); atajos de teclado; subtítulos por línea sincronizados; estilo con
// presets y vista previa sobre el video; quitar pausas; un único «Regenerar» (en celular, en una barra inferior fija).
// La lógica de negocio (qué va a clips.edicion, validaciones) vive en la API (api/recortes.py); acá solo se arma el pedido.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import type { Detalle, Estilo, Linea, Opciones, RespuestaEdicion } from "../tipos";
import LineaTiempo, { calcularPicos, sacarMiniaturas, ZOOM_MAX, type Miniatura, type Pieza } from "../componentes/LineaTiempo";
import Subtitulos, { lineaEn } from "../componentes/Subtitulos";
import { ControlesEstilo, cssSubtitulo } from "../componentes/Estilo";
import { Icono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { EditorEsqueleto, Migas, Tecla } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import { mmss, tramoAVideo, videoATramo } from "../util/tiempo";

const MIN_MS = 2000;
const MAX_MS = 180000;

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const [det, setDet] = useState<Detalle | null>(null);
  const [opciones, setOpciones] = useState<Opciones | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([api.recorte(id), api.opciones()])
      .then(([d, o]) => {
        setDet(d);
        setOpciones(o);
      })
      .catch((e) => setError(e instanceof ErrorApi ? e.message : "No pude cargar el recorte."));
  }, [id]);

  if (error)
    return (
      <div className="pagina">
        <Migas pasos={[{ texto: "Recortes", a: "/recortes" }, { texto: "Editar" }]} />
        <div className="aviso error">{error}</div>
        <Link className="boton" to="/recortes">
          <Icono nombre="flechaIzq" /> Volver a los recortes
        </Link>
      </div>
    );
  if (!det || !opciones) return <EditorEsqueleto />;
  if (!det.puede_editar)
    return (
      <div className="pagina">
        <Migas pasos={[{ texto: "Recortes", a: "/recortes" }, { texto: (det.titulo || det.video_id).slice(0, 60) }]} />
        <div className="aviso">Este recorte no se puede editar desde acá (no está listo, o lo pidió otra persona).</div>
        <Link className="boton" to="/recortes">
          <Icono nombre="flechaIzq" /> Volver a los recortes
        </Link>
      </div>
    );
  return <EditorCargado det={det} opciones={opciones} />;
}

function piezasIniciales(det: Detalle): Pieza[] {
  const seg = det.edicion?.segmentos;
  const ini0 = det.inicio_ms, fin0 = det.fin_ms;
  if (!seg || !seg.length) return [{ a: ini0, b: fin0, conservada: true }];
  // los segmentos conservados, con los huecos entre ellos como pedazos sacados
  const out: Pieza[] = [];
  let t = ini0;
  for (const [a, b] of [...seg].sort((x, y) => x[0] - y[0])) {
    if (a > t) out.push({ a: t, b: a, conservada: false });
    out.push({ a, b, conservada: true });
    t = b;
  }
  if (t < fin0) out.push({ a: t, b: fin0, conservada: false });
  return out;
}

const ATAJOS: [string[], string][] = [
  [["Espacio"], "Reproducir / pausar"],
  [["←", "→"], "Un segundo atrás / adelante"],
  [["Shift", "←/→"], "Una décima de segundo"],
  [["I"], "Marcar el inicio en el cabezal"],
  [["O"], "Marcar el fin en el cabezal"],
  [["S"], "Partir en el cabezal"],
  [["Supr"], "Sacar el pedazo seleccionado (clic en un pedazo lo selecciona)"],
  [["+", "−"], "Acercar / alejar la línea de tiempo (también Ctrl + rueda)"],
  [["0"], "Ver todo el tramo"],
  [["Inicio", "Fin"], "Ir al principio / al final del video"],
  [["?"], "Esta ayuda"],
];

function EditorCargado({ det, opciones }: { det: Detalle; opciones: Opciones }) {
  const vertical = det.formato === "vertical";
  const ini0 = det.inicio_ms, fin0 = det.fin_ms;
  const { avisar } = useToast();
  const [ini, setIni] = useState(ini0);
  const [fin, setFin] = useState(fin0);
  const [piezas, setPiezas] = useState<Pieza[]>(() => piezasIniciales(det));
  const [seleccion, setSeleccion] = useState<number | null>(null);
  const [lineas, setLineas] = useState<Linea[]>(det.lineas.map((l) => ({ ...l })));
  const [estilo, setEstilo] = useState<Estilo>(det.estilo_actual);
  const [quitarPausas, setQuitarPausas] = useState(!!det.edicion?.quitar_pausas);
  const [descartarSrt, setDescartarSrt] = useState(true);
  const [mostrarPrevia, setMostrarPrevia] = useState(true);
  const [tiempo, setTiempo] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [duracion, setDuracion] = useState(det.duracion_ms / 1000);
  const [picos, setPicos] = useState<Float32Array | null>(null);
  const [miniaturas, setMiniaturas] = useState<Miniatura[] | null>(null);
  const [zoom, setZoom] = useState(1);
  const [altoVideo, setAltoVideo] = useState(0);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<RespuestaEdicion | null>(null);
  const [ayuda, setAyuda] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const timeline = det.timeline;

  // forma de onda y miniaturas (las dos se sacan del mp4 en el navegador)
  useEffect(() => {
    let vivo = true;
    if (det.url) {
      calcularPicos(det.url).then((p) => vivo && setPicos(p));
      const n = Math.min(60, Math.max(20, Math.round(det.duracion_ms / 1500)));
      sacarMiniaturas(det.url, n, 54, (m) => vivo && setMiniaturas(m)).then((m) => vivo && setMiniaturas(m));
    }
    return () => {
      vivo = false;
    };
  }, [det.url, det.duracion_ms]);

  // alto real del video en pantalla (para escalar la vista previa de los subtítulos)
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    const ro = new ResizeObserver(() => setAltoVideo(v.clientHeight));
    ro.observe(v);
    setAltoVideo(v.clientHeight);
    return () => ro.disconnect();
  }, []);

  // cabezal fluido mientras reproduce
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = video.current;
      if (v) setTiempo(v.currentTime);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  // --- tramo: las manijas y los campos numéricos mueven lo mismo; los pedazos se acomodan al tramo nuevo ---
  const ajustarPiezas = useCallback((a: number, b: number) => {
    setPiezas((ps) => {
      let out = ps.map((p) => ({ ...p, a: Math.max(p.a, a), b: Math.min(p.b, b) })).filter((p) => p.b - p.a > 0);
      if (!out.length) return [{ a, b, conservada: true }];
      if (out[0].a > a) out = [{ a, b: out[0].a, conservada: out[0].conservada }, ...out];
      out[0] = { ...out[0], a };
      const u = out[out.length - 1];
      if (u.b < b) out = [...out, { a: u.b, b, conservada: u.conservada }];
      out[out.length - 1] = { ...out[out.length - 1], b };
      return out;
    });
  }, []);
  const cambiarIni = useCallback(
    (ms: number) => {
      const v = Math.max(0, Math.min(Math.round(ms), fin - 100));
      setIni(v);
      ajustarPiezas(v, fin);
    },
    [fin, ajustarPiezas],
  );
  const cambiarFin = useCallback(
    (ms: number) => {
      const v = Math.max(Math.round(ms), ini + 100);
      setFin(v);
      ajustarPiezas(ini, v);
    },
    [ini, ajustarPiezas],
  );

  // --- reproductor ↔ original ---
  const msOriginalActual = ini0 + videoATramo(tiempo, timeline) * 1000;
  const irA = useCallback(
    (msOriginal: number) => {
      const tv = tramoAVideo((msOriginal - ini0) / 1000, timeline, duracion);
      if (tv !== null && video.current) video.current.currentTime = Math.max(0, Math.min(tv, duracion));
    },
    [ini0, timeline, duracion],
  );
  function irASegundoVideo(s: number) {
    if (video.current) video.current.currentTime = Math.max(0, Math.min(s, duracion));
  }
  function moverVideo(ds: number) {
    const v = video.current;
    if (v) v.currentTime = Math.max(0, Math.min(v.currentTime + ds, duracion));
  }
  function alternarReproduccion() {
    const v = video.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => {});
    else v.pause();
  }

  // --- partir y sacar ---
  const partir = useCallback(() => {
    const t = Math.round(msOriginalActual);
    setPiezas((ps) => {
      const i = ps.findIndex((p) => t > p.a + 300 && t < p.b - 300);
      if (i < 0) return ps;
      const p = ps[i];
      return [...ps.slice(0, i), { ...p, b: t }, { ...p, a: t }, ...ps.slice(i + 1)];
    });
  }, [msOriginalActual]);
  function alternarPieza(i: number) {
    setPiezas((ps) => ps.map((p, j) => (j === i ? { ...p, conservada: !p.conservada } : p)));
  }
  const sacarSeleccion = useCallback(() => {
    if (seleccion === null) return;
    setPiezas((ps) => (ps.length > 1 ? ps.map((p, j) => (j === seleccion ? { ...p, conservada: false } : p)) : ps));
  }, [seleccion]);
  function unirTodo() {
    setPiezas([{ a: ini, b: fin, conservada: true }]);
    setSeleccion(null);
  }

  const conservadas = piezas.filter((p) => p.conservada);
  const segmentos = useMemo(() => (piezas.length === 1 && piezas[0].conservada ? [] : conservadas.map((p) => [p.a, p.b])), [piezas, conservadas]);
  const durConservada = conservadas.reduce((s, p) => s + (p.b - p.a), 0);
  const tramoCambio = ini !== ini0 || fin !== fin0;
  const segmentosCambio = JSON.stringify(segmentos) !== JSON.stringify(det.edicion?.segmentos ?? []);
  const srtCambio = vertical && lineas.some((l, i) => l.texto !== det.lineas[i]?.texto);
  const estiloCambio = vertical && JSON.stringify(estilo) !== JSON.stringify(det.estilo_actual);
  const pausasCambio = quitarPausas !== !!det.edicion?.quitar_pausas;
  const cambios = [tramoCambio && "tramo", segmentosCambio && "pedazos", srtCambio && "subtítulos", estiloCambio && "estilo", pausasCambio && "pausas"].filter(Boolean) as string[];
  const hayCambios = cambios.length > 0;

  // --- validación (la misma que la API) ---
  let problema: string | null = null;
  const durTramo = fin - ini;
  if (fin <= ini) problema = "El fin tiene que ser después del inicio.";
  else if (durTramo < MIN_MS) problema = `Dura ${(durTramo / 1000).toFixed(1)} s: muy corto. Tiene que durar al menos 2 segundos.`;
  else if (durTramo > MAX_MS) problema = `Dura ${(durTramo / 60000).toFixed(1)} min: muy largo. Como mucho 3 minutos.`;
  else if (!conservadas.length) problema = "Sacaste todos los pedazos: tiene que quedar al menos uno.";
  else if (durConservada < MIN_MS) problema = "Lo que queda del recorte dura menos de 2 segundos.";
  else if (vertical && lineas.length && !tramoCambio && lineas.every((l) => !l.texto.trim())) problema = "Quedaron todas las líneas vacías: el video saldría sin subtítulos. Dejá al menos una.";

  // --- atajos de teclado (no cuando se está escribiendo en un campo ni con un modal abierto) ---
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (ayuda || (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA" || t.isContentEditable))) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      const esManija = t?.classList.contains("manija");
      if (k === " ") {
        e.preventDefault();
        alternarReproduccion();
      } else if ((k === "ArrowLeft" || k === "ArrowRight") && !esManija) {
        e.preventDefault();
        moverVideo((k === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 0.1 : 1));
      } else if (k === "i" || k === "I") cambiarIni(msOriginalActual);
      else if (k === "o" || k === "O") cambiarFin(msOriginalActual);
      else if (k === "s" || k === "S") partir();
      else if (k === "Delete" || k === "Backspace") {
        if (seleccion !== null) {
          e.preventDefault();
          sacarSeleccion();
        }
      } else if (k === "+" || k === "=") setZoom((z) => Math.min(ZOOM_MAX, z * 1.5));
      else if (k === "-" || k === "_") setZoom((z) => (z / 1.5 < 1.1 ? 1 : z / 1.5));
      else if (k === "0") setZoom(1);
      else if (k === "Home") irASegundoVideo(0);
      else if (k === "End") irASegundoVideo(duracion);
      else if (k === "?") setAyuda(true);
      else if (k === "Escape") setSeleccion(null);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  async function regenerar() {
    setEnviando(true);
    const datos: Record<string, unknown> = { segmentos, quitar_pausas: quitarPausas, descartar_srt: descartarSrt };
    if (tramoCambio) {
      datos.inicio_ms = ini;
      datos.fin_ms = fin;
    }
    if (vertical) {
      datos.estilo = estilo;
      if (lineas.length && srtCambio) datos.lineas = lineas.map((l) => ({ inicio: l.inicio, fin: l.fin, texto: l.texto }));
    }
    try {
      const r = await api.editar(det.id, datos);
      setResultado(r);
      avisar("Listo: el recorte se está regenerando.");
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude mandar los cambios.", "error");
    } finally {
      setEnviando(false);
    }
  }

  const idxLinea = lineaEn(lineas, tiempo);
  const css = cssSubtitulo(estilo, opciones, det.formato, altoVideo || 288);
  const textoPrevia = idxLinea >= 0 ? lineas[idxLinea].texto : lineas.length ? "" : "La gratitud es la llave de la alegría";
  const titulo = (det.titulo || det.video_id).slice(0, 90);

  if (resultado) {
    return (
      <div className="pagina">
        <Migas pasos={[{ texto: "Recortes", a: "/recortes" }, { texto: titulo }]} />
        <div className="tarjeta listo-caja">
          <div className="listo-icono">
            <Icono nombre="regenerar" tam={28} />
          </div>
          <h2>Regenerando el recorte</h2>
          <p>{resultado.mensaje}</p>
          {resultado.partes.length > 0 && <p className="suave">Cambios: {resultado.partes.join(", ")}.</p>}
          {resultado.avisos.map((a, i) => (
            <div key={i} className="aviso">
              {a}
            </div>
          ))}
          <p className="suave chico">El video anterior se reemplaza cuando termine (unos 15 minutos). La lista se actualiza sola.</p>
          <Link className="boton primario" to="/recortes">
            <Icono nombre="flechaIzq" /> Volver a los recortes
          </Link>
        </div>
      </div>
    );
  }

  const barraRegenerar = (
    <section className="editor-regenerar" aria-label="Regenerar">
      {problema && (
        <div className="aviso error chico">
          <Icono nombre="alerta" tam={16} /> {problema}
        </div>
      )}
      <div className="regenerar-fila">
        <div className="regenerar-estado chico">
          {hayCambios ? (
            <>
              <strong>{cambios.length === 1 ? "1 cambio" : `${cambios.length} cambios`}</strong> <span className="suave">({cambios.join(", ")}) · tarda unos 15 min</span>
            </>
          ) : (
            <span className="suave">Todavía no cambiaste nada.</span>
          )}
        </div>
        <button type="button" className="boton primario grande" disabled={!hayCambios || !!problema || enviando} onClick={regenerar}>
          <Icono nombre="regenerar" /> {enviando ? "Mandando…" : "Regenerar el recorte"}
        </button>
      </div>
    </section>
  );

  return (
    <div className="pagina editor">
      <header className="pagina-cabecera">
        <Migas pasos={[{ texto: "Recortes", a: "/recortes" }, { texto: titulo }]} />
        <h1>{titulo}</h1>
        <p className="suave chico meta">
          <span>
            <Icono nombre={vertical ? "celular" : "pelicula"} tam={14} /> {vertical ? "vertical" : "horizontal"}
          </span>
          <span>
            {mmss(ini0)}–{mmss(fin0)} del original · {(det.duracion_ms / 1000).toFixed(0)} s
          </span>
          {det.sin_pausas && (
            <span>
              sin pausas ({det.sin_pausas.antes.toFixed(0)} s → {det.sin_pausas.despues.toFixed(0)} s)
            </span>
          )}
          {det.segmentos_hechos && <span>{det.segmentos_hechos.length} pedazos conservados</span>}
        </p>
      </header>

      <div className="editor-grilla">
        {/* ---------- reproductor + vista previa ---------- */}
        <section className="editor-video">
          <div className={"reproductor " + det.formato}>
            <video
              ref={video}
              src={det.url!}
              controls
              playsInline
              onLoadedMetadata={(e) => setDuracion(e.currentTarget.duration || duracion)}
              onPlay={() => setReproduciendo(true)}
              onPause={() => setReproduciendo(false)}
              onEnded={() => setReproduciendo(false)}
            />
            {vertical && mostrarPrevia && textoPrevia && (
              <div style={css.caja}>
                <span style={css.texto}>{textoPrevia}</span>
              </div>
            )}
          </div>
          <div className="video-pie">
            <span className="chico tiempo-actual">
              <Icono nombre="reloj" tam={14} /> {mmss(tiempo * 1000, 1)} del recorte · <strong>{mmss(msOriginalActual, 1)}</strong> del original
            </span>
            {vertical && (
              <label className="casilla chico">
                <input type="checkbox" checked={mostrarPrevia} onChange={(e) => setMostrarPrevia(e.target.checked)} />
                <span>Vista previa del estilo encima del video</span>
              </label>
            )}
          </div>
          {vertical && <p className="suave chico">El video actual ya tiene sus subtítulos quemados: por eso se ven los dos. El nuevo sale solo con los nuevos.</p>}
        </section>

        {/* ---------- tramo + línea de tiempo ---------- */}
        <section className="editor-tramo">
          <div className="seccion-cabecera">
            <h2>
              <Icono nombre="tramo" /> Tramo y cortes
            </h2>
            <div className="linea-herramientas" role="toolbar" aria-label="Línea de tiempo">
              <button type="button" className="boton sutil icono-solo" onClick={() => setZoom((z) => (z / 1.5 < 1.1 ? 1 : z / 1.5))} disabled={zoom <= 1} title="Alejar (−)" aria-label="Alejar">
                <Icono nombre="lupaMenos" />
              </button>
              <span className="zoom-valor chico" aria-live="polite">
                {zoom.toFixed(1)}×
              </span>
              <button type="button" className="boton sutil icono-solo" onClick={() => setZoom((z) => Math.min(ZOOM_MAX, z * 1.5))} disabled={zoom >= ZOOM_MAX} title="Acercar (+)" aria-label="Acercar">
                <Icono nombre="lupaMas" />
              </button>
              <button type="button" className="boton sutil icono-solo" onClick={() => setZoom(1)} disabled={zoom <= 1} title="Ver todo el tramo (0)" aria-label="Ver todo">
                <Icono nombre="ajustar" />
              </button>
              <span className="separador-v" />
              <button type="button" className="boton sutil chico" onClick={() => setAyuda(true)} title="Atajos de teclado (?)">
                <Icono nombre="teclado" /> Atajos
              </button>
            </div>
          </div>
          <p className="suave chico">
            Arrastrá las manijas amarillas para elegir dónde empieza y termina (entre 2 s y 3 min). Lo rayado está fuera del video actual: se puede elegir, pero no
            se ve hasta regenerar.
          </p>
          <LineaTiempo
            ini={ini}
            fin={fin}
            ini0={ini0}
            fin0={fin0}
            piezas={piezas}
            seleccion={seleccion}
            timeline={timeline}
            duracionVideo={duracion}
            tiempoVideo={tiempo}
            reproduciendo={reproduciendo}
            formato={det.formato}
            picos={picos}
            miniaturas={miniaturas}
            zoom={zoom}
            onZoom={setZoom}
            onIni={cambiarIni}
            onFin={cambiarFin}
            onIr={irA}
            onPieza={alternarPieza}
            onSeleccion={setSeleccion}
            onPartir={partir}
          />
          <div className="tramo-controles">
            <ControlTiempo etiqueta="Inicio" icono="marcaIni" ms={ini} onCambio={cambiarIni} onMarcar={() => cambiarIni(msOriginalActual)} />
            <ControlTiempo etiqueta="Fin" icono="marcaFin" ms={fin} onCambio={cambiarFin} onMarcar={() => cambiarFin(msOriginalActual)} />
            <div className="duracion">
              <span className="suave chico">Dura</span> <strong>{(durConservada / 1000).toFixed(1)} s</strong>
              {segmentos.length > 0 && <span className="suave chico"> · tramo {(durTramo / 1000).toFixed(1)} s, {segmentos.length === 1 ? "1 pedazo" : `${segmentos.length} pedazos`}</span>}
              {tramoCambio && segmentos.length === 0 && <span className="suave chico"> · antes {(det.duracion_ms / 1000).toFixed(1)} s</span>}
            </div>
          </div>
          <div className="acciones">
            <button type="button" className="boton" onClick={partir} title="Parte el recorte en la posición del reproductor (S)">
              <Icono nombre="tijera" /> Partir en {mmss(msOriginalActual, 1)}
            </button>
            {seleccion !== null && piezas.length > 1 && (
              <button type="button" className="boton" onClick={() => alternarPieza(seleccion)} title={piezas[seleccion].conservada ? "Sacar el pedazo seleccionado (Supr)" : "Volver a conservar el pedazo seleccionado"}>
                <Icono nombre={piezas[seleccion].conservada ? "cruz" : "deshacer"} /> {piezas[seleccion].conservada ? "Sacar el pedazo" : "Restaurar el pedazo"}
              </button>
            )}
            {piezas.length > 1 && (
              <button type="button" className="boton sutil" onClick={unirTodo}>
                <Icono nombre="deshacer" /> Deshacer los cortes
              </button>
            )}
            {piezas.length > 1 && <span className="suave chico">Clic en un pedazo lo selecciona; el botón de cada pedazo lo saca o lo restaura.</span>}
          </div>
          <label className="casilla">
            <input type="checkbox" checked={quitarPausas} onChange={(e) => setQuitarPausas(e.target.checked)} />
            <span>
              Quitar pausas largas (más de 0,7 s)
              <span className="suave chico"> Saca los silencios largos y deja un cuarto de segundo a cada lado. En una charla suele sacar entre un 10 y un 20 % del tiempo. Los subtítulos se acomodan solos.</span>
            </span>
          </label>
          {det.sin_pausas && quitarPausas && !pausasCambio && (
            <p className="suave chico">
              Este recorte ya está sin pausas largas: duraba {det.sin_pausas.antes.toFixed(0)} s y quedó en {det.sin_pausas.despues.toFixed(0)} s ({det.sin_pausas.pausas} pausas sacadas).
            </p>
          )}
        </section>

        {/* ---------- subtítulos ---------- */}
        {vertical && (
          <section className="editor-subs">
            <div className="seccion-cabecera">
              <h2>
                <Icono nombre="subtitulos" /> Subtítulos
              </h2>
              {lineas.length > 0 && <span className="suave chico">{lineas.length} líneas</span>}
            </div>
            {tramoCambio || segmentosCambio || pausasCambio ? (
              <>
                {det.srt_corregido || srtCambio ? (
                  <>
                    <div className="aviso chico">
                      Los subtítulos corregidos corresponden al video anterior: con el tramo nuevo (o los pedazos y pausas nuevos) pueden quedar corridos o cortados.
                    </div>
                    {tramoCambio && (
                      <label className="casilla chico">
                        <input type="checkbox" checked={descartarSrt} onChange={(e) => setDescartarSrt(e.target.checked)} /> Descartar los subtítulos corregidos y armarlos de nuevo para el
                        tramo nuevo (después los podés volver a corregir)
                      </label>
                    )}
                  </>
                ) : (
                  <p className="suave chico">Como cambiaste el tramo (o los pedazos / pausas), los subtítulos se arman de nuevo desde la transcripción. Cuando el video esté listo los podés corregir desde acá.</p>
                )}
              </>
            ) : (
              <p className="suave chico">La línea que suena se resalta y la lista la sigue. Clic en el tiempo salta a ese momento. Una línea vacía se saca; los tiempos no se cambian desde acá.</p>
            )}
            <Subtitulos lineas={lineas} actual={idxLinea} onIr={irASegundoVideo} onTexto={(i, t) => setLineas((ls) => ls.map((l, j) => (j === i ? { ...l, texto: t } : l)))} />
          </section>
        )}

        {/* ---------- estilo ---------- */}
        {vertical && (
          <section className="editor-estilo">
            <div className="seccion-cabecera">
              <h2>
                <Icono nombre="paleta" /> Estilo de los subtítulos
              </h2>
              {det.estilo_propio ? <span className="suave chico">estilo propio de este recorte</span> : <span className="suave chico">arranca con el del equipo</span>}
            </div>
            <p className="suave chico">Elegí un estilo listo o ajustá cada cosa. La vista previa, sobre el reproductor, cambia al instante.</p>
            <ControlesEstilo estilo={estilo} opciones={opciones} onCambio={setEstilo} />
          </section>
        )}

        {/* ---------- regenerar ---------- */}
        {barraRegenerar}
      </div>

      {ayuda && (
        <Modal titulo="Atajos de teclado" onCerrar={() => setAyuda(false)} ancho={520}>
          <p className="suave chico">Funcionan cuando no estás escribiendo en un campo. Las manijas también se mueven con las flechas cuando tienen el foco (Tab).</p>
          <table className="atajos">
            <tbody>
              {ATAJOS.map(([teclas, que]) => (
                <tr key={que}>
                  <td>
                    {teclas.map((t, i) => (
                      <Tecla key={i}>{t}</Tecla>
                    ))}
                  </td>
                  <td>{que}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="boton primario" onClick={() => setAyuda(false)}>
              Entendido
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ControlTiempo({ etiqueta, icono, ms, onCambio, onMarcar }: { etiqueta: string; icono: "marcaIni" | "marcaFin"; ms: number; onCambio: (ms: number) => void; onMarcar: () => void }) {
  const m = Math.floor(ms / 60000);
  const s = (ms % 60000) / 1000;
  return (
    <div className="control-tiempo" role="group" aria-label={etiqueta}>
      <button type="button" className="boton sutil chico" onClick={onMarcar} title={`Poner el ${etiqueta.toLowerCase()} donde está el reproductor (${icono === "marcaIni" ? "I" : "O"})`}>
        <Icono nombre={icono} tam={15} /> {etiqueta}
      </button>
      <button type="button" className="boton chico icono-solo" onClick={() => onCambio(ms - 1000)} title="Un segundo antes" aria-label={`${etiqueta}: un segundo antes`}>
        <Icono nombre="menos" tam={14} />
      </button>
      <input type="number" min={0} max={599} value={m} onChange={(e) => onCambio(Number(e.target.value) * 60000 + s * 1000)} aria-label={`${etiqueta}: minutos`} />
      <span>:</span>
      <input type="number" min={0} max={59.9} step={0.1} value={s.toFixed(1)} onChange={(e) => onCambio(m * 60000 + Number(e.target.value) * 1000)} aria-label={`${etiqueta}: segundos`} />
      <button type="button" className="boton chico icono-solo" onClick={() => onCambio(ms + 1000)} title="Un segundo después" aria-label={`${etiqueta}: un segundo después`}>
        <Icono nombre="mas" tam={14} />
      </button>
    </div>
  );
}
