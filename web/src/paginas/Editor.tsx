// «Editar recorte» con editor visual (fase 1 + revisión UX + pedazos como piezas, 22/10): reproductor + línea de tiempo en dos
// carriles (el original con miniaturas, onda y manijas del tramo; abajo la secuencia de salida con un bloque por pedazo, cada uno
// con sus manijas, arrastrable para reordenar), partir y sacar pedazos, «Ver secuencia», atajos de teclado, subtítulos por línea
// sincronizados, estilo con presets y vista previa sobre el video, quitar pausas, un único «Regenerar» (en celular, en una barra
// inferior fija). La lógica de negocio (qué va a clips.edicion, validaciones) vive en la API (api/recortes.py); acá solo se arma
// el pedido. Las operaciones sobre los pedazos están en util/piezas.ts.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import type { Detalle, Estilo, Linea, Opciones, RespuestaEdicion } from "../tipos";
import LineaTiempo, { calcularPicos, sacarMiniaturas, ZOOM_MAX, type Miniatura } from "../componentes/LineaTiempo";
import Subtitulos, { lineaEn } from "../componentes/Subtitulos";
import { ControlesEstilo, cssSubtitulo } from "../componentes/Estilo";
import { Icono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { EditorEsqueleto, Migas, Tecla } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import { mmss, tramoAVideo, videoATramo } from "../util/tiempo";
import * as pz from "../util/piezas";

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

const ATAJOS: [string[], string][] = [
  [["Espacio"], "Reproducir / pausar"],
  [["P"], "Ver la secuencia (reproduce los pedazos en el orden elegido) / parar"],
  [["←", "→"], "Un segundo atrás / adelante"],
  [["Shift", "←/→"], "Una décima de segundo"],
  [["I"], "Marcar el inicio en el cabezal"],
  [["O"], "Marcar el fin en el cabezal"],
  [["S"], "Partir el pedazo que está bajo el cabezal en dos"],
  [["Supr"], "Sacar el pedazo seleccionado (clic en un pedazo o en su bloque lo selecciona)"],
  [["[", "]"], "Mover el pedazo seleccionado un lugar antes / después en la secuencia"],
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
  const [estado, setEstado] = useState<pz.Estado>(() => pz.piezasIniciales(ini0, fin0, det.edicion?.segmentos));
  const { piezas, orden } = estado;
  const [seleccion, setSeleccion] = useState<number | null>(null);
  const [lineas, setLineas] = useState<Linea[]>(det.lineas.map((l) => ({ ...l })));
  const [estilo, setEstilo] = useState<Estilo>(det.estilo_actual);
  const [quitarPausas, setQuitarPausas] = useState(!!det.edicion?.quitar_pausas);
  const [descartarSrt, setDescartarSrt] = useState(true);
  const [mostrarPrevia, setMostrarPrevia] = useState(true);
  const [tiempo, setTiempo] = useState(0);
  const [reproduciendo, setReproduciendo] = useState(false);
  const [secuencia, setSecuencia] = useState<number | null>(null); // índice en `orden` del pedazo que se está viendo (null = no)
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
  const minPedazo = opciones.limites.min_pedazo_ms ?? pz.MIN_PEDAZO_MS;

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

  // --- reproductor ↔ original ---
  const irA = useCallback(
    (msOriginal: number) => {
      const tv = tramoAVideo((msOriginal - ini0) / 1000, timeline, duracion);
      if (tv !== null && video.current) video.current.currentTime = Math.max(0, Math.min(tv, duracion));
    },
    [ini0, timeline, duracion],
  );
  const msOriginalActual = ini0 + videoATramo(tiempo, timeline) * 1000;

  // --- «Ver secuencia»: reproduce los pedazos conservados en el orden elegido, saltando lo sacado y lo que no está en el video ---
  const secRef = useRef({ secuencia, orden, piezas, timeline, duracion, ini0 });
  secRef.current = { secuencia, orden, piezas, timeline, duracion, ini0 };
  const saltarA = useCallback((i: number): boolean => {
    // busca desde `i` el primer pedazo que esté en el video actual, lleva el reproductor a su inicio y lo deja como actual
    const s = secRef.current;
    const porId = new Map(s.piezas.map((p) => [p.id, p]));
    for (let j = i; j < s.orden.length; j++) {
      const p = porId.get(s.orden[j]);
      if (!p) continue;
      const tv = tramoAVideo((p.a - s.ini0) / 1000, s.timeline, s.duracion);
      if (tv === null || tv >= s.duracion - 0.05) continue;
      if (video.current) video.current.currentTime = tv;
      setSecuencia(j);
      return true;
    }
    setSecuencia(null);
    return false;
  }, []);
  function verSecuencia() {
    const v = video.current;
    if (!v) return;
    if (secuencia !== null) {
      v.pause();
      setSecuencia(null);
      return;
    }
    if (saltarA(0)) v.play().catch(() => {});
  }

  // cabezal fluido mientras reproduce; en modo secuencia, al llegar al fin de un pedazo salta al siguiente
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const v = video.current;
      if (v) {
        setTiempo(v.currentTime);
        const s = secRef.current;
        if (s.secuencia !== null && !v.paused) {
          const p = s.piezas.find((q) => q.id === s.orden[s.secuencia!]);
          const msOrig = s.ini0 + videoATramo(v.currentTime, s.timeline) * 1000;
          if (!p || msOrig >= p.b - 40 || v.ended) {
            if (!saltarA(s.secuencia + 1)) v.pause();
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [saltarA]);

  // --- tramo: las manijas y los campos numéricos mueven lo mismo; los pedazos se acomodan al tramo nuevo ---
  const cambiarIni = useCallback(
    (ms: number) => {
      const v = Math.max(0, Math.min(Math.round(ms), fin - 100));
      setIni(v);
      setEstado((e) => pz.ajustarAlTramo(e, v, fin));
    },
    [fin],
  );
  const cambiarFin = useCallback(
    (ms: number) => {
      const v = Math.max(Math.round(ms), ini + 100);
      setFin(v);
      setEstado((e) => pz.ajustarAlTramo(e, ini, v));
    },
    [ini],
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

  // --- partir, sacar, recortar, reordenar ---
  const partir = useCallback(() => {
    const t = Math.round(msOriginalActual);
    setEstado((e) => pz.partirEn(e, t));
  }, [msOriginalActual]);
  const alternarPieza = useCallback((id: number) => setEstado((e) => (e.piezas.length > 1 ? pz.alternar(e, id) : e)), []);
  const recortarPieza = useCallback((id: number, a: number, b: number) => setEstado((e) => pz.recortar(e, id, a, b, ini, fin)), [ini, fin]);
  const moverPieza = useCallback((id: number, dir: -1 | 1) => setEstado((e) => pz.mover(e, id, dir)), []);
  const reordenar = useCallback((nuevo: number[]) => setEstado((e) => ({ ...e, orden: nuevo })), []);
  const sacarSeleccion = useCallback(() => {
    if (seleccion === null) return;
    setEstado((e) => (e.piezas.length > 1 && e.piezas.find((p) => p.id === seleccion)?.conservada ? pz.alternar(e, seleccion) : e));
  }, [seleccion]);
  function unirTodo() {
    const p = { id: pz.nuevoId(), a: ini, b: fin, conservada: true };
    setEstado({ piezas: [p], orden: [p.id] });
    setSeleccion(null);
  }
  const piezaSel = seleccion === null ? null : (piezas.find((p) => p.id === seleccion) ?? null);

  const segmentos = useMemo(() => pz.segmentosDe(estado, ini, fin), [estado, ini, fin]);
  const reordenados = pz.reordenada(segmentos);
  const porId = new Map(piezas.map((p) => [p.id, p]));
  const conservadas = orden.map((id) => porId.get(id)!).filter(Boolean);
  const durConservada = conservadas.reduce((s, p) => s + (p.b - p.a), 0);
  const tramoCambio = ini !== ini0 || fin !== fin0;
  const segmentosCambio = JSON.stringify(segmentos) !== JSON.stringify(det.edicion?.segmentos ?? []);
  const srtCambio = vertical && lineas.some((l, i) => l.texto !== det.lineas[i]?.texto);
  const estiloCambio = vertical && JSON.stringify(estilo) !== JSON.stringify(det.estilo_actual);
  const pausasCambio = quitarPausas !== !!det.edicion?.quitar_pausas;
  const cambios = [tramoCambio && "tramo", segmentosCambio && (reordenados ? "pedazos (en otro orden)" : "pedazos"), srtCambio && "subtítulos", estiloCambio && "estilo", pausasCambio && "pausas"].filter(Boolean) as string[];
  const hayCambios = cambios.length > 0;

  // --- validación (la misma que la API) ---
  let problema: string | null = null;
  const durTramo = fin - ini;
  const corto = conservadas.find((p) => p.b - p.a < minPedazo);
  if (fin <= ini) problema = "El fin tiene que ser después del inicio.";
  else if (durTramo < MIN_MS) problema = `Dura ${(durTramo / 1000).toFixed(1)} s: muy corto. Tiene que durar al menos 2 segundos.`;
  else if (durTramo > MAX_MS) problema = `Dura ${(durTramo / 60000).toFixed(1)} min: muy largo. Como mucho 3 minutos.`;
  else if (!conservadas.length) problema = "Sacaste todos los pedazos: tiene que quedar al menos uno.";
  else if (corto) problema = `Hay un pedazo que dura ${((corto.b - corto.a) / 1000).toFixed(1)} s: cada pedazo tiene que durar al menos medio segundo.`;
  else if (durConservada < MIN_MS) problema = "Lo que queda del recorte dura menos de 2 segundos.";
  else if (durConservada > MAX_MS) problema = `Los pedazos suman ${(durConservada / 60000).toFixed(1)} min: muy largo. Como mucho 3 minutos.`;
  else if (vertical && lineas.length && !tramoCambio && !segmentosCambio && lineas.every((l) => !l.texto.trim())) problema = "Quedaron todas las líneas vacías: el video saldría sin subtítulos. Dejá al menos una.";

  // --- atajos de teclado (no cuando se está escribiendo en un campo ni con un modal abierto) ---
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (ayuda || (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA" || t.isContentEditable))) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      const esManija = t?.classList.contains("manija") || t?.classList.contains("bloque-manija");
      if (k === " ") {
        e.preventDefault();
        alternarReproduccion();
      } else if ((k === "ArrowLeft" || k === "ArrowRight") && !esManija) {
        e.preventDefault();
        moverVideo((k === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 0.1 : 1));
      } else if (k === "i" || k === "I") cambiarIni(msOriginalActual);
      else if (k === "o" || k === "O") cambiarFin(msOriginalActual);
      else if (k === "s" || k === "S") partir();
      else if (k === "p" || k === "P") verSecuencia();
      else if (k === "Delete" || k === "Backspace") {
        if (seleccion !== null) {
          e.preventDefault();
          sacarSeleccion();
        }
      } else if ((k === "[" || k === "]") && seleccion !== null) moverPieza(seleccion, k === "[" ? -1 : 1);
      else if (k === "+" || k === "=") setZoom((z) => Math.min(ZOOM_MAX, z * 1.5));
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
  const hayCortes = piezas.length > 1;

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
          {det.segmentos_hechos && (
            <span>
              {det.segmentos_hechos.length} pedazos conservados{pz.reordenada(det.segmentos_hechos) ? " (en otro orden)" : ""}
            </span>
          )}
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
              onPause={() => {
                setReproduciendo(false);
                setSecuencia(null);
              }}
              onEnded={() => setReproduciendo(false)}
            />
            {vertical && mostrarPrevia && textoPrevia && (
              <div style={css.caja}>
                <span style={css.texto}>{textoPrevia}</span>
              </div>
            )}
            {secuencia !== null && (
              <div className="secuencia-marca" aria-live="polite">
                <Icono nombre="reproducir" tam={12} /> Secuencia · pedazo {secuencia + 1} de {orden.length}
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
              <Icono nombre="tramo" /> Tramo y pedazos
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
            Arriba, el original: las manijas amarillas grandes eligen dónde empieza y termina (entre 2 s y 3 min); lo rayado está fuera del video actual. Abajo, la
            secuencia de salida: un bloque por pedazo, en el orden en que va a salir. Cada bloque se recorta con sus dos manijas, se arrastra (o ◀ ▶) para cambiar el orden y se
            saca con ×.
          </p>
          <LineaTiempo
            ini={ini}
            fin={fin}
            ini0={ini0}
            fin0={fin0}
            piezas={piezas}
            orden={orden}
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
            onRecortar={recortarPieza}
            onOrden={reordenar}
            onMover={moverPieza}
          />
          <div className="tramo-controles">
            <ControlTiempo etiqueta="Inicio" icono="marcaIni" ms={ini} onCambio={cambiarIni} onMarcar={() => cambiarIni(msOriginalActual)} />
            <ControlTiempo etiqueta="Fin" icono="marcaFin" ms={fin} onCambio={cambiarFin} onMarcar={() => cambiarFin(msOriginalActual)} />
            <div className="duracion">
              <span className="suave chico">Sale</span> <strong>{(durConservada / 1000).toFixed(1)} s</strong>
              {hayCortes && (
                <span className="suave chico">
                  {" "}
                  · tramo {(durTramo / 1000).toFixed(1)} s, {conservadas.length === 1 ? "1 pedazo" : `${conservadas.length} pedazos`}
                  {reordenados ? " en otro orden" : ""}
                </span>
              )}
              {tramoCambio && !hayCortes && <span className="suave chico"> · antes {(det.duracion_ms / 1000).toFixed(1)} s</span>}
            </div>
          </div>
          <div className="acciones">
            <button type="button" className="boton" onClick={partir} title="Parte el pedazo que está bajo el cabezal (S)">
              <Icono nombre="tijera" /> Partir en {mmss(msOriginalActual, 1)}
            </button>
            <button type="button" className={"boton" + (secuencia !== null ? " activo" : "")} onClick={verSecuencia} disabled={!conservadas.length} title="Reproduce los pedazos en el orden de la secuencia, saltando lo sacado (P)">
              <Icono nombre={secuencia !== null ? "pausar" : "reproducir"} /> {secuencia !== null ? "Parar la secuencia" : "Ver secuencia"}
            </button>
            {piezaSel && hayCortes && (
              <button type="button" className="boton" onClick={() => alternarPieza(piezaSel.id)} title={piezaSel.conservada ? "Sacar el pedazo seleccionado (Supr)" : "Volver a agregar el pedazo seleccionado"}>
                <Icono nombre={piezaSel.conservada ? "cruz" : "deshacer"} /> {piezaSel.conservada ? "Sacar el pedazo" : "Volver a agregar el pedazo"}
              </button>
            )}
            {hayCortes && (
              <button type="button" className="boton sutil" onClick={unirTodo}>
                <Icono nombre="deshacer" /> Deshacer los cortes
              </button>
            )}
          </div>
          {hayCortes && (
            <p className="suave chico">
              Lo sacado queda rayado en el original y se puede volver a agregar con «Restaurar». Los pedazos se estiran por sus manijas solo sobre lo sacado o el tramo: no
              pueden pisar a otro pedazo.
            </p>
          )}
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
                    {(tramoCambio || segmentosCambio) && (
                      <label className="casilla chico">
                        <input type="checkbox" checked={descartarSrt} onChange={(e) => setDescartarSrt(e.target.checked)} /> Descartar los subtítulos corregidos y armarlos de nuevo
                        para el video nuevo (después los podés volver a corregir)
                      </label>
                    )}
                  </>
                ) : (
                  <p className="suave chico">Como cambiaste el tramo (o los pedazos / pausas), los subtítulos se arman de nuevo desde la transcripción, pedazo por pedazo. Cuando el video esté listo los podés corregir desde acá.</p>
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
          <p className="suave chico">
            Funcionan cuando no estás escribiendo en un campo. Las manijas (las del tramo y las de cada bloque) también se mueven con las flechas cuando tienen el foco (Tab).
          </p>
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
