// Línea de tiempo del editor, en dos carriles (22/10: «cada pedazo es una pieza propia»):
//  · ARRIBA, el ORIGINAL (eje = milisegundos absolutos del video original, desde un poco antes del inicio del recorte actual hasta
//    un poco después del fin): carril del cabezal y las burbujas, tira de miniaturas (sacadas del mp4 en el navegador), forma de
//    onda y regla. Encima, los pedazos conservados (con su número de orden) y los sacados (rayados, con «Restaurar»), la zona fuera
//    del video actual (rayada), el cabezal con su tijera y las dos manijas grandes del tramo (inicio y fin).
//  · ABAJO, la SECUENCIA DE SALIDA: los pedazos conservados como bloques contiguos, en el orden en que salen en el video final.
//    Cada bloque tiene su miniatura, su duración, dos manijas amarillas en los bordes (recortan ESE pedazo sobre el original, sin
//    pisar a sus vecinos conservados), un agarre para arrastrarlo a otro lugar de la secuencia (soltar entre dos bloques) y
//    botones ◀ ▶ × (mover un lugar, sacar). Un cabezal rojo muestra dónde está el reproductor dentro de la secuencia.
// Zoom con botones, Ctrl+rueda o teclas ± (lo maneja el Editor); los dos carriles comparten escala y desplazamiento.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { mmss, tramoAVideo, videoATramo, type Timeline } from "../util/tiempo";
import { Icono } from "./Iconos";

export interface Pieza {
  id: number;
  a: number; // ms absolutos del original
  b: number;
  conservada: boolean;
}

export interface Miniatura {
  t: number; // segundo del video actual
  img: ImageBitmap | HTMLCanvasElement;
}

interface Props {
  ini: number; // manija de inicio (ms absolutos)
  fin: number;
  ini0: number; // tramo del video actual (columnas de la fila)
  fin0: number;
  piezas: Pieza[]; // partición del tramo [ini, fin] en el orden del original
  orden: number[]; // ids de los pedazos conservados, en el orden de salida
  seleccion: number | null; // id del pedazo seleccionado (Supr lo saca)
  timeline: Timeline; // cómo el video actual mapea al tramo plano
  duracionVideo: number; // segundos del video actual
  tiempoVideo: number; // segundo actual del reproductor
  reproduciendo: boolean;
  formato: "horizontal" | "vertical";
  picos: Float32Array | null; // forma de onda del video actual (un valor cada PASO_MS)
  miniaturas: Miniatura[] | null;
  zoom: number; // 1 = todo el tramo a la vista
  onZoom: (z: number) => void;
  onIni: (ms: number) => void;
  onFin: (ms: number) => void;
  onIr: (msOriginal: number) => void; // clic en la línea
  onPieza: (id: number) => void; // chip de un pedazo (conservar / sacar)
  onSeleccion: (id: number | null) => void;
  onPartir: () => void;
  onRecortar: (id: number, a: number, b: number) => void; // manijas de un bloque
  onOrden: (orden: number[]) => void; // arrastre de un bloque a otro lugar
  onMover: (id: number, dir: -1 | 1) => void; // botones ◀ ▶
}

export const PASO_MS = 50;
export const ZOOM_MAX = 12;
export const MIN_PEDAZO_MS = 500;
const MARGEN_MS = 10000;
const CARRIL = 24; // carril de arriba (cabezal, burbujas)
const ALTO_MINI = 54;
const ALTO_ONDA = 42;
const ALTO_REGLA = 18;
const ALTO = ALTO_MINI + ALTO_ONDA + ALTO_REGLA;
const SEP = 34; // entre el original y la secuencia (título del carril)
const ALTO_SEC = 72; // bloques de la secuencia (miniatura + etiqueta)
const ALTO_SEC_MINI = 50;
const MIN_BLOQUE = 30; // px: que siempre entren las dos manijas
const GAP = 3;
const Y_SEC = CARRIL + ALTO + SEP;

type Arrastre =
  | { tipo: "ini" | "fin" }
  | { tipo: "pieza"; id: number; lado: "a" | "b"; x0: number; valor0: number } // el bloque no está donde el pedazo en el original: se mueve por diferencia
  | { tipo: "mover"; id: number; x0: number; x: number; activo: boolean };

interface Geo {
  id: number;
  left: number;
  width: number;
  pieza: Pieza;
}

export default function LineaTiempo(p: Props) {
  const marco = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ancho, setAncho] = useState(600);
  const [arrastre, setArrastre] = useState<Arrastre | null>(null);

  const desde = Math.max(0, Math.min(p.ini, p.ini0) - MARGEN_MS);
  const hasta = Math.max(p.fin, p.fin0) + MARGEN_MS;
  const anchoTotal = Math.round(ancho * p.zoom);
  const escala = anchoTotal / (hasta - desde); // px por ms
  const x = (ms: number) => (ms - desde) * escala;
  const ms = (px: number) => desde + px / escala;

  const porId = useMemo(() => new Map(p.piezas.map((z) => [z.id, z])), [p.piezas]);
  const numero = useMemo(() => new Map(p.orden.map((id, i) => [id, i + 1])), [p.orden]);

  // geometría de los bloques de la secuencia (contiguos desde x(ini); un pedazo cortito ocupa al menos MIN_BLOQUE px)
  const geo = useMemo<Geo[]>(() => {
    let left = x(p.ini);
    const out: Geo[] = [];
    for (const id of p.orden) {
      const z = porId.get(id);
      if (!z) continue;
      const width = Math.max(MIN_BLOQUE, (z.b - z.a) * escala);
      out.push({ id, left, width, pieza: z });
      left += width + GAP;
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.orden, porId, p.ini, escala, desde]);
  const geoRef = useRef(geo);
  geoRef.current = geo;

  useEffect(() => {
    const el = marco.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setAncho(el.clientWidth));
    ro.observe(el);
    setAncho(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Al cambiar el zoom, el centro de lo que se ve queda en el mismo lugar
  const previo = useRef({ escala, desde });
  useLayoutEffect(() => {
    const m = marco.current;
    if (m && previo.current.escala !== escala) {
      const centro = previo.current.desde + (m.scrollLeft + ancho / 2) / previo.current.escala;
      m.scrollLeft = (centro - desde) * escala - ancho / 2;
    }
    previo.current = { escala, desde };
  }, [escala, desde, ancho]);

  // Ctrl + rueda = zoom alrededor del mouse (listener no pasivo para poder frenar el zoom del navegador)
  useEffect(() => {
    const m = marco.current;
    if (!m) return;
    const rueda = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const z = Math.min(ZOOM_MAX, Math.max(1, p.zoom * (e.deltaY < 0 ? 1.25 : 0.8)));
      p.onZoom(Math.abs(z - 1) < 0.05 ? 1 : z);
    };
    m.addEventListener("wheel", rueda, { passive: false });
    return () => m.removeEventListener("wheel", rueda);
  }, [p.zoom, p.onZoom]);

  // la miniatura más cercana a un segundo del video actual
  const miniEn = (tv: number) => {
    if (!p.miniaturas || !p.miniaturas.length) return null;
    let mejor = p.miniaturas[0];
    for (const m of p.miniaturas) if (Math.abs(m.t - tv) < Math.abs(mejor.t - tv)) mejor = m;
    return mejor.img;
  };

  // Forma de onda, miniaturas y regla, en el eje del original: cada columna de píxel se lleva al segundo del video actual.
  // Abajo, las miniaturas de cada bloque de la secuencia.
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const altoCanvas = ALTO + SEP + ALTO_SEC;
    c.width = anchoTotal * dpr;
    c.height = altoCanvas * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, anchoTotal, altoCanvas);
    g.fillStyle = "#f4f1ea";
    g.fillRect(0, 0, anchoTotal, ALTO);
    const rayas = (x0: number, x1: number) => {
      g.save();
      g.beginPath();
      g.rect(x0, 0, x1 - x0, ALTO);
      g.clip();
      g.fillStyle = "rgba(0,0,0,0.03)";
      g.fillRect(x0, 0, x1 - x0, ALTO);
      g.strokeStyle = "rgba(0,0,0,0.07)";
      g.lineWidth = 1;
      for (let i = -ALTO; i < x1 - x0 + ALTO; i += 9) {
        g.beginPath();
        g.moveTo(x0 + i, 0);
        g.lineTo(x0 + i + ALTO, ALTO);
        g.stroke();
      }
      g.restore();
    };
    rayas(0, x(p.ini0));
    rayas(x(p.fin0), anchoTotal);

    // miniaturas (solo donde hay video actual)
    const x0v = x(p.ini0), x1v = x(p.fin0);
    const tw = Math.max(18, Math.round(ALTO_MINI * (p.formato === "vertical" ? 9 / 16 : 16 / 9)));
    g.save();
    g.beginPath();
    g.rect(x0v, 0, x1v - x0v, ALTO_MINI);
    g.clip();
    g.fillStyle = "#1a1a1a";
    g.fillRect(x0v, 0, x1v - x0v, ALTO_MINI);
    if (p.miniaturas && p.miniaturas.length) {
      for (let px = x0v; px < x1v; px += tw) {
        const tv = tramoAVideo((ms(px + tw / 2) - p.ini0) / 1000, p.timeline, p.duracionVideo);
        const img = tv === null ? null : miniEn(tv);
        if (!img) continue;
        try {
          g.drawImage(img, px, 0, tw, ALTO_MINI);
        } catch {
          /* cuadro no disponible */
        }
      }
    } else {
      g.fillStyle = "rgba(255,255,255,0.35)";
      g.font = "11px Raleway, sans-serif";
      g.fillText("cargando los cuadros…", x0v + 8, ALTO_MINI / 2 + 4);
    }
    g.restore();

    // onda
    const mid = ALTO_MINI + ALTO_ONDA / 2;
    if (p.picos && p.picos.length) {
      for (let px = Math.floor(x0v); px <= Math.ceil(x1v); px++) {
        const tv = tramoAVideo((ms(px) - p.ini0) / 1000, p.timeline, p.duracionVideo);
        if (tv === null) continue;
        const i = Math.min(p.picos.length - 1, Math.floor((tv * 1000) / PASO_MS));
        const v = p.picos[i] || 0;
        const h = Math.max(1, v * (ALTO_ONDA - 8));
        const dentro = p.piezas.some((z) => z.conservada && ms(px) >= z.a && ms(px) <= z.b);
        g.fillStyle = dentro ? "rgba(58,107,53,0.8)" : "rgba(120,120,120,0.35)";
        g.fillRect(px, mid - h / 2, 1, h);
      }
    } else {
      g.fillStyle = "rgba(58,107,53,0.35)";
      for (let t = Math.ceil(p.ini0 / 1000) * 1000; t <= p.fin0; t += 1000) {
        const alto = t % 5000 === 0 ? 24 : 12;
        g.fillRect(x(t), mid - alto / 2, 1, alto);
      }
    }

    // regla: el paso más chico que deje al menos 64 px entre etiquetas
    const y0 = ALTO_MINI + ALTO_ONDA;
    g.fillStyle = "#fff";
    g.fillRect(0, y0, anchoTotal, ALTO_REGLA);
    g.fillStyle = "rgba(0,0,0,0.08)";
    g.fillRect(0, y0, anchoTotal, 1);
    const paso = [500, 1000, 2000, 5000, 10000, 15000, 30000, 60000].find((s) => s * escala >= 64) ?? 60000;
    const menor = paso / (paso === 500 || paso === 1000 || paso === 2000 || paso === 10000 ? 2 : 5);
    g.fillStyle = "rgba(0,0,0,0.25)";
    for (let t = Math.ceil(desde / menor) * menor; t <= hasta; t += menor) g.fillRect(Math.round(x(t)), y0, 1, 4);
    g.fillStyle = "rgba(0,0,0,0.55)";
    g.font = "600 10.5px Raleway, sans-serif";
    for (let t = Math.ceil(desde / paso) * paso; t <= hasta; t += paso) {
      g.fillRect(Math.round(x(t)), y0, 1, 8);
      g.fillText(mmss(t, paso < 1000 ? 1 : 0), x(t) + 3, y0 + ALTO_REGLA - 4);
    }

    // secuencia de salida: las miniaturas de cada bloque, en su orden
    const ys = ALTO + SEP;
    for (const b of geo) {
      g.save();
      g.beginPath();
      g.rect(b.left, ys, b.width, ALTO_SEC_MINI);
      g.clip();
      g.fillStyle = "#1a1a1a";
      g.fillRect(b.left, ys, b.width, ALTO_SEC_MINI);
      const tws = Math.max(18, Math.round(ALTO_SEC_MINI * (p.formato === "vertical" ? 9 / 16 : 16 / 9)));
      for (let px = b.left; px < b.left + b.width; px += tws) {
        const tOrig = b.pieza.a + ((Math.min(px + tws / 2, b.left + b.width) - b.left) / b.width) * (b.pieza.b - b.pieza.a);
        const tv = tramoAVideo((tOrig - p.ini0) / 1000, p.timeline, p.duracionVideo);
        const img = tv === null ? null : miniEn(tv);
        if (!img) {
          // fuera del video actual: rayado
          g.fillStyle = "rgba(255,255,255,0.12)";
          g.fillRect(px, ys, tws, ALTO_SEC_MINI);
          continue;
        }
        try {
          g.drawImage(img, px, ys, tws, ALTO_SEC_MINI);
        } catch {
          /* cuadro no disponible */
        }
      }
      g.restore();
    }
  }, [anchoTotal, p.picos, p.miniaturas, p.piezas, p.ini0, p.fin0, p.timeline, p.duracionVideo, p.formato, desde, hasta, escala, geo]);

  // Arrastres (mouse y touch, vía pointer events): manijas del tramo, manijas de un bloque, mover un bloque
  useEffect(() => {
    if (!arrastre) return;
    const pxDe = (e: PointerEvent) => {
      const r = ref.current!.getBoundingClientRect();
      return Math.min(Math.max(0, e.clientX - r.left), anchoTotal);
    };
    const mover = (e: PointerEvent) => {
      const px = pxDe(e);
      if (arrastre.tipo === "mover") {
        setArrastre((a) => (a && a.tipo === "mover" ? { ...a, x: px, activo: a.activo || Math.abs(px - a.x0) > 5 } : a));
        return;
      }
      const m = Math.round(ms(px) / 100) * 100;
      if (arrastre.tipo === "ini") p.onIni(Math.max(0, Math.min(m, p.fin - 2000)));
      else if (arrastre.tipo === "fin") p.onFin(Math.max(m, p.ini + 2000));
      else if (arrastre.tipo === "pieza") {
        const z = porId.get(arrastre.id);
        if (!z) return;
        const v = Math.round((arrastre.valor0 + (px - arrastre.x0) / escala) / 100) * 100;
        if (arrastre.lado === "a") p.onRecortar(z.id, Math.min(v, z.b - MIN_PEDAZO_MS), z.b);
        else p.onRecortar(z.id, z.a, Math.max(v, z.a + MIN_PEDAZO_MS));
      }
    };
    const soltar = (e: PointerEvent) => {
      if (arrastre.tipo === "mover") {
        const z = porId.get(arrastre.id);
        if (arrastre.activo) {
          const px = pxDe(e);
          const otros = geoRef.current.filter((b) => b.id !== arrastre.id);
          const lugar = otros.filter((b) => b.left + b.width / 2 < px).length;
          const nuevo = otros.map((b) => b.id);
          nuevo.splice(lugar, 0, arrastre.id);
          if (nuevo.some((id, i) => id !== p.orden[i])) p.onOrden(nuevo);
        } else if (z) {
          // fue un clic: seleccionar y llevar el reproductor al principio del pedazo
          p.onSeleccion(z.id);
          p.onIr(z.a);
        }
      }
      setArrastre(null);
    };
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
    window.addEventListener("pointercancel", soltar);
    return () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
      window.removeEventListener("pointercancel", soltar);
    };
  });

  // Cabezal: segundo del video actual → ms del original; y su lugar en la secuencia (si cae en un pedazo conservado)
  const cabezal = p.ini0 + videoATramo(p.tiempoVideo, p.timeline) * 1000;
  const cabezalSec = useMemo(() => {
    for (const b of geo) if (cabezal >= b.pieza.a && cabezal <= b.pieza.b) return b.left + ((cabezal - b.pieza.a) / (b.pieza.b - b.pieza.a)) * b.width;
    return null;
  }, [geo, cabezal]);

  // Mientras reproduce, la vista sigue al cabezal si se va de pantalla
  useEffect(() => {
    const m = marco.current;
    if (!m || !p.reproduciendo || p.zoom <= 1) return;
    const px = x(cabezal);
    if (px < m.scrollLeft + 8 || px > m.scrollLeft + ancho - 8) m.scrollLeft = px - ancho * 0.25;
  });

  function clic(e: React.MouseEvent) {
    if (arrastre) return;
    const r = ref.current!.getBoundingClientRect();
    if (e.clientY - r.top > CARRIL + ALTO) return; // el carril de la secuencia tiene sus propios clics
    const m = Math.round(ms(e.clientX - r.left));
    p.onIr(m);
    if (p.piezas.length > 1) {
      const z = p.piezas.find((z) => m >= z.a && m < z.b);
      p.onSeleccion(z ? z.id : null);
    }
  }

  function teclaManija(cual: "ini" | "fin", e: React.KeyboardEvent) {
    const d = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
    if (!d) return;
    e.preventDefault();
    e.stopPropagation();
    const paso = e.shiftKey ? 1000 : 100;
    if (cual === "ini") p.onIni(Math.max(0, Math.min(p.ini + d * paso, p.fin - 2000)));
    else p.onFin(Math.max(p.fin + d * paso, p.ini + 2000));
  }

  function teclaBloque(z: Pieza, lado: "a" | "b", e: React.KeyboardEvent) {
    const d = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
    if (!d) return;
    e.preventDefault();
    e.stopPropagation();
    const paso = e.shiftKey ? 1000 : 100;
    if (lado === "a") p.onRecortar(z.id, Math.min(z.a + d * paso, z.b - MIN_PEDAZO_MS), z.b);
    else p.onRecortar(z.id, z.a, Math.max(z.b + d * paso, z.a + MIN_PEDAZO_MS));
  }

  const manija = (cual: "ini" | "fin") => {
    const valor = cual === "ini" ? p.ini : p.fin;
    const activa = arrastre?.tipo === cual;
    return (
      <div
        className={"manija " + cual + (activa ? " arrastrando" : "")}
        style={{ left: x(valor), height: ALTO }}
        role="slider"
        tabIndex={0}
        aria-label={cual === "ini" ? "Inicio del recorte" : "Fin del recorte"}
        aria-valuemin={cual === "ini" ? 0 : Math.round((p.ini + 2000) / 1000)}
        aria-valuemax={cual === "ini" ? Math.round((p.fin - 2000) / 1000) : Math.round(hasta / 1000)}
        aria-valuenow={Math.round(valor / 1000)}
        aria-valuetext={mmss(valor, 1)}
        onPointerDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          (e.currentTarget as HTMLElement).focus();
          setArrastre({ tipo: cual });
        }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => teclaManija(cual, e)}
        title={cual === "ini" ? "Arrastrá para mover el inicio (flechas: ±0,1 s; con Shift ±1 s)" : "Arrastrá para mover el fin (flechas: ±0,1 s; con Shift ±1 s)"}
      >
        <span className="manija-asa" aria-hidden="true">
          <i />
          <i />
        </span>
        <span className="burbuja">{mmss(valor, 1)}</span>
      </div>
    );
  };

  const moviendo = arrastre?.tipo === "mover" && arrastre.activo ? arrastre : null;
  // dónde caería el bloque que se arrastra (marca de inserción)
  let marcaX: number | null = null;
  if (moviendo) {
    const otros = geo.filter((b) => b.id !== moviendo.id);
    const lugar = otros.filter((b) => b.left + b.width / 2 < moviendo.x).length;
    if (!otros.length) marcaX = null;
    else marcaX = lugar < otros.length ? otros[lugar].left - GAP / 2 : otros[otros.length - 1].left + otros[otros.length - 1].width + GAP / 2;
  }
  const durSalida = geo.reduce((s, b) => s + (b.pieza.b - b.pieza.a), 0);
  const ultimoBloque = geo.length ? geo[geo.length - 1].left + geo[geo.length - 1].width : x(p.ini);

  return (
    <div className="linea-marco" ref={marco}>
      <div className="linea" ref={ref} onClick={clic} style={{ width: anchoTotal, height: Y_SEC + ALTO_SEC }}>
        <canvas ref={canvas} style={{ width: anchoTotal, height: ALTO + SEP + ALTO_SEC, top: CARRIL }} />
        {/* ---------- original: pedazos conservados / sacados ---------- */}
        {p.piezas.map((z) => (
          <div
            key={z.id}
            className={"pieza " + (z.conservada ? "conservada" : "sacada") + (p.seleccion === z.id && p.piezas.length > 1 ? " seleccionada" : "")}
            style={{ left: x(z.a), width: Math.max(2, x(z.b) - x(z.a)), top: CARRIL, height: ALTO }}
          >
            {p.piezas.length > 1 && z.conservada && (
              <span className="pieza-num" title={`Pedazo ${numero.get(z.id)} de la secuencia`}>
                {numero.get(z.id)}
              </span>
            )}
            {p.piezas.length > 1 && x(z.b) - x(z.a) > 44 && (
              <button
                type="button"
                className={"pieza-chip" + (z.conservada ? "" : " restaurar")}
                title={z.conservada ? "Sacar este pedazo de la secuencia" : "Volver a agregar este pedazo a la secuencia"}
                onClick={(e) => {
                  e.stopPropagation();
                  p.onPieza(z.id);
                }}
              >
                <Icono nombre={z.conservada ? "cruz" : "deshacer"} tam={13} />
                {z.conservada ? `${((z.b - z.a) / 1000).toFixed(1)} s` : "Restaurar"}
              </button>
            )}
          </div>
        ))}
        {/* fuera del tramo elegido: oscurecido */}
        <div className="fuera" style={{ left: 0, width: x(p.ini), top: CARRIL, height: ALTO }} />
        <div className="fuera" style={{ left: x(p.fin), width: Math.max(0, anchoTotal - x(p.fin)), top: CARRIL, height: ALTO }} />
        {/* cabezal con tiempo y tijera */}
        <div className="cabezal" style={{ left: x(cabezal), height: CARRIL + ALTO }}>
          <div className="cabezal-cabeza">
            <span>{mmss(cabezal, 1)}</span>
            <button
              type="button"
              className="cabezal-tijera"
              title="Partir acá (S)"
              aria-label={`Partir en ${mmss(cabezal, 1)}`}
              onClick={(e) => {
                e.stopPropagation();
                p.onPartir();
              }}
            >
              <Icono nombre="tijera" tam={13} />
            </button>
          </div>
        </div>
        {manija("ini")}
        {manija("fin")}

        {/* ---------- secuencia de salida ---------- */}
        <div className="sec-titulo chico" style={{ left: x(p.ini), top: CARRIL + ALTO + 6 }}>
          <strong>Secuencia de salida</strong> · {(durSalida / 1000).toFixed(1)} s ·{" "}
          {geo.length === 1 ? "1 pedazo" : `${geo.length} pedazos`}
          {geo.length > 1 && <span className="suave"> · arrastrá un bloque para cambiar el orden</span>}
        </div>
        <div className="sec-fondo" style={{ left: x(p.ini), width: Math.max(0, ultimoBloque - x(p.ini)), top: Y_SEC, height: ALTO_SEC }} />
        {geo.map((b, i) => {
          const z = b.pieza;
          const esMovido = moviendo?.id === z.id;
          const sel = p.seleccion === z.id;
          const dur = (z.b - z.a) / 1000;
          const recortando = arrastre?.tipo === "pieza" && arrastre.id === z.id ? arrastre.lado : null;
          return (
            <div
              key={z.id}
              className={"bloque" + (sel ? " seleccionado" : "") + (esMovido ? " movido" : "") + (b.width < 70 ? " angosto" : "")}
              style={{ left: b.left, width: b.width, top: Y_SEC, height: ALTO_SEC, transform: esMovido ? `translateX(${moviendo!.x - moviendo!.x0}px)` : undefined }}
              role="group"
              aria-label={`Pedazo ${i + 1}: ${mmss(z.a, 1)} a ${mmss(z.b, 1)} del original, ${dur.toFixed(1)} s`}
              tabIndex={0}
              onFocus={() => p.onSeleccion(z.id)}
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => {
                // con mouse, todo el bloque se arrastra; en touch solo el agarre (así el carril se puede desplazar con el dedo)
                if (e.button !== 0 || e.pointerType !== "mouse") return;
                e.preventDefault();
                e.stopPropagation();
                (e.currentTarget as HTMLElement).focus();
                const r = ref.current!.getBoundingClientRect();
                setArrastre({ tipo: "mover", id: z.id, x0: e.clientX - r.left, x: e.clientX - r.left, activo: false });
              }}
            >
              <span className="bloque-num" aria-hidden="true">
                {i + 1}
              </span>
              <span
                className="bloque-asa"
                title="Arrastrá para cambiar el orden"
                aria-hidden="true"
                onPointerDown={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const r = ref.current!.getBoundingClientRect();
                  setArrastre({ tipo: "mover", id: z.id, x0: e.clientX - r.left, x: e.clientX - r.left, activo: false });
                }}
              >
                <i />
                <i />
                <i />
              </span>
              <div className="bloque-pie">
                <span className="bloque-dur">{dur.toFixed(1)} s</span>
                <span className="bloque-botones">
                  <button
                    type="button"
                    className="bloque-boton"
                    disabled={i === 0}
                    title="Un lugar antes en la secuencia ([)"
                    aria-label="Un lugar antes"
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      p.onMover(z.id, -1);
                    }}
                  >
                    ◀
                  </button>
                  <button
                    type="button"
                    className="bloque-boton"
                    disabled={i === geo.length - 1}
                    title="Un lugar después en la secuencia (])"
                    aria-label="Un lugar después"
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      p.onMover(z.id, 1);
                    }}
                  >
                    ▶
                  </button>
                  <button
                    type="button"
                    className="bloque-boton sacar"
                    disabled={p.piezas.length <= 1}
                    title="Sacar este pedazo de la secuencia (Supr)"
                    aria-label="Sacar"
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={(e) => {
                      e.stopPropagation();
                      p.onPieza(z.id);
                    }}
                  >
                    <Icono nombre="cruz" tam={12} />
                  </button>
                </span>
              </div>
              {(["a", "b"] as const).map((lado) => (
                <div
                  key={lado}
                  className={"bloque-manija " + (lado === "a" ? "ini" : "fin") + (recortando === lado ? " arrastrando" : "")}
                  role="slider"
                  tabIndex={0}
                  aria-label={lado === "a" ? `Inicio del pedazo ${i + 1}` : `Fin del pedazo ${i + 1}`}
                  aria-valuenow={Math.round((lado === "a" ? z.a : z.b) / 1000)}
                  aria-valuetext={mmss(lado === "a" ? z.a : z.b, 1)}
                  title={lado === "a" ? "Arrastrá para recortar el inicio de este pedazo (flechas: ±0,1 s; con Shift ±1 s)" : "Arrastrá para recortar el fin de este pedazo (flechas: ±0,1 s; con Shift ±1 s)"}
                  onPointerDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    (e.currentTarget as HTMLElement).focus();
                    const r = ref.current!.getBoundingClientRect();
                    setArrastre({ tipo: "pieza", id: z.id, lado, x0: e.clientX - r.left, valor0: lado === "a" ? z.a : z.b });
                  }}
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => teclaBloque(z, lado, e)}
                >
                  <span className="burbuja">{mmss(lado === "a" ? z.a : z.b, 1)}</span>
                </div>
              ))}
            </div>
          );
        })}
        {marcaX !== null && <div className="marca-insercion" style={{ left: marcaX, top: Y_SEC - 4, height: ALTO_SEC + 8 }} />}
        {cabezalSec !== null && <div className="cabezal-sec" style={{ left: cabezalSec, top: Y_SEC - 4, height: ALTO_SEC + 8 }} />}
      </div>
    </div>
  );
}

/** Baja el mp4 y saca un pico de volumen cada PASO_MS (para dibujar la onda). null si el navegador no puede (CORS, códec…). */
export async function calcularPicos(url: string): Promise<Float32Array | null> {
  try {
    const r = await fetch(url, { mode: "cors" });
    if (!r.ok) return null;
    const buf = await r.arrayBuffer();
    const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const audio = await ctx.decodeAudioData(buf);
    const datos = audio.getChannelData(0);
    const porPaso = Math.floor((audio.sampleRate * PASO_MS) / 1000);
    const n = Math.ceil(datos.length / porPaso);
    const picos = new Float32Array(n);
    let max = 0;
    for (let i = 0; i < n; i++) {
      let m = 0;
      const fin = Math.min(datos.length, (i + 1) * porPaso);
      for (let j = i * porPaso; j < fin; j += 4) {
        const v = Math.abs(datos[j]);
        if (v > m) m = v;
      }
      picos[i] = m;
      if (m > max) max = m;
    }
    if (max > 0) for (let i = 0; i < n; i++) picos[i] = picos[i] / max;
    ctx.close();
    return picos;
  } catch {
    return null;
  }
}

/** Saca `cantidad` cuadros repartidos a lo largo del mp4 con un <video> oculto + <canvas> (sin ffmpeg ni endpoint).
 *  Avisa por `onParcial` a medida que salen, así la línea de tiempo se va llenando. Si el video no se puede cargar, devuelve []. */
export async function sacarMiniaturas(url: string, cantidad: number, altoPx: number, onParcial?: (m: Miniatura[]) => void): Promise<Miniatura[]> {
  const v = document.createElement("video");
  v.muted = true;
  v.playsInline = true;
  v.preload = "auto";
  v.crossOrigin = "anonymous";
  const cargar = () =>
    new Promise<boolean>((res) => {
      v.onloadedmetadata = () => res(true);
      v.onerror = () => res(false);
      v.src = url;
    });
  if (!(await cargar())) {
    // sin CORS el cuadro igual se puede dibujar (el canvas queda «sucio», pero nunca lo leemos)
    v.crossOrigin = null;
    if (!(await cargar())) return [];
  }
  const dur = v.duration;
  if (!dur || !isFinite(dur)) return [];
  const ancho = Math.max(2, Math.round((altoPx * v.videoWidth) / v.videoHeight)) || Math.round(altoPx * 1.5);
  const out: Miniatura[] = [];
  for (let i = 0; i < cantidad; i++) {
    const t = Math.min(dur - 0.05, (dur * (i + 0.5)) / cantidad);
    const ok = await new Promise<boolean>((res) => {
      const fin = window.setTimeout(() => res(false), 4000);
      v.onseeked = () => {
        window.clearTimeout(fin);
        res(true);
      };
      v.currentTime = t;
    });
    if (!ok) break;
    const c = document.createElement("canvas");
    c.width = ancho;
    c.height = altoPx;
    try {
      c.getContext("2d")!.drawImage(v, 0, 0, ancho, altoPx);
    } catch {
      break;
    }
    out.push({ t, img: c });
    if (onParcial && (i % 4 === 3 || i === cantidad - 1)) onParcial([...out]);
  }
  v.removeAttribute("src");
  v.load();
  return out;
}
