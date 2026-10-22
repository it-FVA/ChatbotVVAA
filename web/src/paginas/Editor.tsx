// «✏️ Editar recorte» con editor visual (fase 1): reproductor + línea de tiempo con manijas, partir y sacar pedazos,
// subtítulos por línea sincronizados, estilo con vista previa sobre el video, quitar pausas, y un único «Regenerar».
// La lógica de negocio (qué va a clips.edicion, validaciones) vive en la API (api/recortes.py); acá solo se arma el pedido.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import type { Detalle, Estilo, Linea, Opciones, RespuestaEdicion } from "../tipos";
import LineaTiempo, { calcularPicos, type Pieza } from "../componentes/LineaTiempo";
import Subtitulos, { lineaEn } from "../componentes/Subtitulos";
import { ControlesEstilo, cssSubtitulo } from "../componentes/Estilo";
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
        <div className="aviso error">{error}</div>
        <Link to="/recortes">← Volver a los recortes</Link>
      </div>
    );
  if (!det || !opciones) return <div className="pagina suave">Cargando el recorte…</div>;
  if (!det.puede_editar)
    return (
      <div className="pagina">
        <div className="aviso">Este recorte no se puede editar desde acá (no está listo, o lo pidió otra persona).</div>
        <Link to="/recortes">← Volver a los recortes</Link>
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

function EditorCargado({ det, opciones }: { det: Detalle; opciones: Opciones }) {
  const vertical = det.formato === "vertical";
  const ini0 = det.inicio_ms, fin0 = det.fin_ms;
  const [ini, setIni] = useState(ini0);
  const [fin, setFin] = useState(fin0);
  const [piezas, setPiezas] = useState<Pieza[]>(() => piezasIniciales(det));
  const [lineas, setLineas] = useState<Linea[]>(det.lineas.map((l) => ({ ...l })));
  const [estilo, setEstilo] = useState<Estilo>(det.estilo_actual);
  const [quitarPausas, setQuitarPausas] = useState(!!det.edicion?.quitar_pausas);
  const [descartarSrt, setDescartarSrt] = useState(true);
  const [mostrarPrevia, setMostrarPrevia] = useState(true);
  const [tiempo, setTiempo] = useState(0);
  const [duracion, setDuracion] = useState(det.duracion_ms / 1000);
  const [picos, setPicos] = useState<Float32Array | null>(null);
  const [altoVideo, setAltoVideo] = useState(0);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<RespuestaEdicion | null>(null);
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const timeline = det.timeline;

  // forma de onda
  useEffect(() => {
    let vivo = true;
    if (det.url) calcularPicos(det.url).then((p) => vivo && setPicos(p));
    return () => {
      vivo = false;
    };
  }, [det.url]);

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
  const cambiarIni = (ms: number) => {
    const v = Math.max(0, Math.min(Math.round(ms), fin - 100));
    setIni(v);
    ajustarPiezas(v, fin);
  };
  const cambiarFin = (ms: number) => {
    const v = Math.max(Math.round(ms), ini + 100);
    setFin(v);
    ajustarPiezas(ini, v);
  };

  // --- reproductor ↔ original ---
  const msOriginalActual = ini0 + videoATramo(tiempo, timeline) * 1000;
  function irA(msOriginal: number) {
    const tv = tramoAVideo((msOriginal - ini0) / 1000, timeline, duracion);
    if (tv !== null && video.current) video.current.currentTime = Math.max(0, Math.min(tv, duracion));
  }
  function irASegundoVideo(s: number) {
    if (video.current) video.current.currentTime = Math.max(0, Math.min(s, duracion));
  }

  // --- partir y sacar ---
  function partir() {
    const t = Math.round(msOriginalActual);
    setPiezas((ps) => {
      const i = ps.findIndex((p) => t > p.a + 300 && t < p.b - 300);
      if (i < 0) return ps;
      const p = ps[i];
      return [...ps.slice(0, i), { ...p, b: t }, { ...p, a: t }, ...ps.slice(i + 1)];
    });
  }
  function alternarPieza(i: number) {
    setPiezas((ps) => ps.map((p, j) => (j === i ? { ...p, conservada: !p.conservada } : p)));
  }
  function unirTodo() {
    setPiezas([{ a: ini, b: fin, conservada: true }]);
  }

  const conservadas = piezas.filter((p) => p.conservada);
  const segmentos = useMemo(() => (piezas.length === 1 && piezas[0].conservada ? [] : conservadas.map((p) => [p.a, p.b])), [piezas, conservadas]);
  const durConservada = conservadas.reduce((s, p) => s + (p.b - p.a), 0);
  const tramoCambio = ini !== ini0 || fin !== fin0;
  const segmentosCambio = JSON.stringify(segmentos) !== JSON.stringify(det.edicion?.segmentos ?? []);
  const srtCambio = vertical && lineas.some((l, i) => l.texto !== det.lineas[i]?.texto);
  const estiloCambio = vertical && JSON.stringify(estilo) !== JSON.stringify(det.estilo_actual);
  const pausasCambio = quitarPausas !== !!det.edicion?.quitar_pausas;
  const hayCambios = tramoCambio || segmentosCambio || srtCambio || estiloCambio || pausasCambio;

  // --- validación (la misma que la API) ---
  let problema: string | null = null;
  const durTramo = fin - ini;
  if (fin <= ini) problema = "El fin tiene que ser después del inicio.";
  else if (durTramo < MIN_MS) problema = `Dura ${(durTramo / 1000).toFixed(1)} s: muy corto. Tiene que durar al menos 2 segundos.`;
  else if (durTramo > MAX_MS) problema = `Dura ${(durTramo / 60000).toFixed(1)} min: muy largo. Como mucho 3 minutos.`;
  else if (!conservadas.length) problema = "Sacaste todos los pedazos: tiene que quedar al menos uno.";
  else if (durConservada < MIN_MS) problema = "Lo que queda del recorte dura menos de 2 segundos.";
  else if (vertical && lineas.length && !tramoCambio && lineas.every((l) => !l.texto.trim())) problema = "Quedaron todas las líneas vacías: el video saldría sin subtítulos. Dejá al menos una.";

  async function regenerar() {
    setEnviando(true);
    setErrorEnvio(null);
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
      setResultado(await api.editar(det.id, datos));
    } catch (e) {
      setErrorEnvio(e instanceof ErrorApi ? e.message : "No pude mandar los cambios.");
    } finally {
      setEnviando(false);
    }
  }

  const idxLinea = lineaEn(lineas, tiempo);
  const css = cssSubtitulo(estilo, opciones, det.formato, altoVideo || 288);
  const textoPrevia = idxLinea >= 0 ? lineas[idxLinea].texto : lineas.length ? "" : "La gratitud es la llave de la alegría";

  if (resultado) {
    return (
      <div className="pagina">
        <div className="tarjeta listo-caja">
          <h2>⏳ Regenerando el recorte</h2>
          <p>{resultado.mensaje}</p>
          {resultado.partes.length > 0 && <p className="suave">Cambios: {resultado.partes.join(", ")}.</p>}
          {resultado.avisos.map((a, i) => (
            <div key={i} className="aviso">
              {a}
            </div>
          ))}
          <p className="suave chico">El video anterior se reemplaza cuando termine (unos 15 minutos). La lista se actualiza sola.</p>
          <Link className="boton primario" to="/recortes">
            ← Volver a los recortes
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="pagina editor">
      <header className="pagina-cabecera">
        <Link to="/recortes" className="chico">
          ← Recortes
        </Link>
        <h1>✏️ {(det.titulo || det.video_id).slice(0, 90)}</h1>
        <p className="suave chico">
          {vertical ? "📱 vertical" : "🎬 horizontal"} · {mmss(ini0)}–{mmss(fin0)} del original · {(det.duracion_ms / 1000).toFixed(0)} s
          {det.sin_pausas && ` · ✂️ sin pausas (${det.sin_pausas.antes.toFixed(0)} s → ${det.sin_pausas.despues.toFixed(0)} s)`}
          {det.segmentos_hechos && ` · ✂️ ${det.segmentos_hechos.length} pedazos conservados`}
        </p>
      </header>

      <div className="editor-grilla">
        {/* ---------- reproductor + vista previa ---------- */}
        <section className="editor-video">
          <div className={"reproductor " + det.formato}>
            <video ref={video} src={det.url!} controls playsInline onLoadedMetadata={(e) => setDuracion(e.currentTarget.duration || duracion)} />
            {vertical && mostrarPrevia && textoPrevia && (
              <div style={css.caja}>
                <span style={css.texto}>{textoPrevia}</span>
              </div>
            )}
          </div>
          {vertical && (
            <label className="casilla chico">
              <input type="checkbox" checked={mostrarPrevia} onChange={(e) => setMostrarPrevia(e.target.checked)} />
              <span>Mostrar la vista previa del estilo encima del video</span>
            </label>
          )}
          <p className="suave chico">
            Segundo {tiempo.toFixed(1)} del recorte = {mmss(msOriginalActual, 1)} del original.
            {vertical && " La vista previa se dibuja encima del video actual, que ya tiene sus subtítulos quemados: el video nuevo sale solo con los nuevos."}
          </p>
        </section>

        {/* ---------- tramo + línea de tiempo ---------- */}
        <section className="editor-tramo">
          <h2>Tramo</h2>
          <p className="suave chico">
            Dónde empieza y dónde termina el recorte, en el video original. Arrastrá las manijas o usá los campos y los botones de ±1 s. Tiene que durar entre 2
            segundos y 3 minutos. Lo rayado está fuera del video actual: se puede elegir, pero no se ve hasta regenerar.
          </p>
          <LineaTiempo
            ini={ini}
            fin={fin}
            ini0={ini0}
            fin0={fin0}
            piezas={piezas}
            timeline={timeline}
            duracionVideo={duracion}
            tiempoVideo={tiempo}
            picos={picos}
            onIni={cambiarIni}
            onFin={cambiarFin}
            onIr={irA}
            onPieza={alternarPieza}
          />
          <div className="tramo-controles">
            <ControlTiempo etiqueta="Inicio" ms={ini} onCambio={cambiarIni} />
            <ControlTiempo etiqueta="Fin" ms={fin} onCambio={cambiarFin} />
            <div className="duracion">
              Duración: <strong>{(durConservada / 1000).toFixed(1)} s</strong>
              {segmentos.length > 0 && <span className="suave"> (tramo {(durTramo / 1000).toFixed(1)} s, {segmentos.length === 1 ? "1 pedazo conservado" : `${segmentos.length} pedazos conservados`})</span>}
              {tramoCambio && segmentos.length === 0 && <span className="suave"> (antes {(det.duracion_ms / 1000).toFixed(1)} s)</span>}
            </div>
          </div>
          <div className="acciones">
            <button type="button" className="boton" onClick={partir} title="Parte el recorte en la posición actual del reproductor">
              ✂️ Partir acá ({mmss(msOriginalActual, 1)})
            </button>
            {piezas.length > 1 && (
              <button type="button" className="boton" onClick={unirTodo}>
                Deshacer los cortes
              </button>
            )}
            <span className="suave chico">Después de partir, hacé clic en un pedazo para sacarlo (gris) o volver a conservarlo (verde).</span>
          </div>
          <label className="casilla">
            <input type="checkbox" checked={quitarPausas} onChange={(e) => setQuitarPausas(e.target.checked)} />
            <span>
              Quitar pausas largas (más de 0,7 s)
              <span className="suave chico">
                {" "}
                Saca automáticamente los silencios largos (deja un cuarto de segundo a cada lado). En una charla suele sacar entre un 10 y un 20 % del tiempo;
                en una meditación casi no cambia nada. Los subtítulos se acomodan solos.
              </span>
            </span>
          </label>
          {det.sin_pausas && quitarPausas && !pausasCambio && (
            <p className="suave chico">
              Este recorte ya está sin pausas largas: duraba {det.sin_pausas.antes.toFixed(0)} s y quedó en {det.sin_pausas.despues.toFixed(0)} s (
              {det.sin_pausas.pausas} pausas sacadas).
            </p>
          )}
        </section>

        {/* ---------- subtítulos ---------- */}
        {vertical && (
          <section className="editor-subs">
            <h2>Subtítulos</h2>
            {tramoCambio || segmentosCambio || pausasCambio ? (
              <>
                {det.srt_corregido || srtCambio ? (
                  <>
                    <div className="aviso">
                      Los subtítulos corregidos corresponden al video anterior: con el tramo nuevo (o los pedazos y pausas nuevos) pueden quedar corridos o
                      cortados.
                    </div>
                    {tramoCambio && (
                      <label className="casilla chico">
                        <input type="checkbox" checked={descartarSrt} onChange={(e) => setDescartarSrt(e.target.checked)} /> Descartar los subtítulos corregidos
                        y armarlos de nuevo para el tramo nuevo (después los podés volver a corregir)
                      </label>
                    )}
                  </>
                ) : (
                  <p className="suave chico">
                    Como cambiaste el tramo (o los pedazos / pausas), los subtítulos se arman de nuevo desde la transcripción. Cuando el video esté listo los
                    podés corregir desde acá.
                  </p>
                )}
              </>
            ) : (
              <p className="suave chico">Una caja por línea. Clic en el tiempo salta a ese momento del video. Corregí el texto; una línea vacía se saca. Los tiempos no se cambian desde acá.</p>
            )}
            <Subtitulos lineas={lineas} actual={idxLinea} onIr={irASegundoVideo} onTexto={(i, t) => setLineas((ls) => ls.map((l, j) => (j === i ? { ...l, texto: t } : l)))} />
          </section>
        )}

        {/* ---------- estilo ---------- */}
        {vertical && (
          <section className="editor-estilo">
            <h2>Estilo de los subtítulos</h2>
            <p className="suave chico">
              Cómo se ven las letras sobre el video. Arranca con el estilo de este recorte{det.estilo_propio ? "" : " (el por defecto del equipo)"}. La vista previa
              se dibuja arriba, sobre el reproductor.
            </p>
            <ControlesEstilo estilo={estilo} opciones={opciones} onCambio={setEstilo} />
          </section>
        )}

        {/* ---------- regenerar ---------- */}
        <section className="editor-regenerar">
          {problema && <div className="aviso error">{problema}</div>}
          {errorEnvio && <div className="aviso error">{errorEnvio}</div>}
          <div className="acciones">
            <button type="button" className="boton primario grande" disabled={!hayCambios || !!problema || enviando} onClick={regenerar}>
              {enviando ? "Mandando…" : "🔁 Regenerar el recorte"}
            </button>
            <span className="suave chico">{hayCambios ? "Vuelve a cortar el video con los cambios. Tarda unos 15 minutos, como cualquier recorte." : "Todavía no cambiaste nada."}</span>
          </div>
        </section>
      </div>
    </div>
  );
}

function ControlTiempo({ etiqueta, ms, onCambio }: { etiqueta: string; ms: number; onCambio: (ms: number) => void }) {
  const m = Math.floor(ms / 60000);
  const s = (ms % 60000) / 1000;
  return (
    <div className="control-tiempo">
      <strong>{etiqueta}</strong>
      <button type="button" className="boton chico" onClick={() => onCambio(ms - 1000)} title="Un segundo antes">
        −1 s
      </button>
      <input type="number" min={0} max={599} value={m} onChange={(e) => onCambio(Number(e.target.value) * 60000 + s * 1000)} aria-label="minutos" />
      <span>:</span>
      <input type="number" min={0} max={59.9} step={0.1} value={s.toFixed(1)} onChange={(e) => onCambio(m * 60000 + Number(e.target.value) * 1000)} aria-label="segundos" />
      <button type="button" className="boton chico" onClick={() => onCambio(ms + 1000)} title="Un segundo después">
        +1 s
      </button>
    </div>
  );
}
