// Línea de tiempo del editor: el eje es el video ORIGINAL (milisegundos absolutos), desde un poco antes del inicio del recorte
// actual hasta un poco después del fin. De arriba abajo: un carril para el cabezal y las burbujas de las manijas, la tira de
// miniaturas de cuadros (sacadas del mp4 en el navegador), la forma de onda del audio y la regla de tiempos. Encima: los pedazos
// conservados (color) y sacados (rayado), la zona fuera del video actual (rayada: no se puede ver hasta regenerar), el cabezal
// con su tijera y dos manijas grandes arrastrables (inicio y fin). Zoom con botones, Ctrl+rueda o teclas ± (lo maneja el Editor).
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { mmss, tramoAVideo, type Timeline } from "../util/tiempo";
import { Icono } from "./Iconos";

export interface Pieza {
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
  piezas: Pieza[];
  seleccion: number | null; // índice del pedazo seleccionado (Supr lo saca)
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
  onPieza: (i: number) => void; // chip de un pedazo (conservar / sacar)
  onSeleccion: (i: number | null) => void;
  onPartir: () => void;
}

export const PASO_MS = 50;
export const ZOOM_MAX = 12;
const MARGEN_MS = 10000;
const CARRIL = 24; // carril de arriba (cabezal, burbujas)
const ALTO_MINI = 54;
const ALTO_ONDA = 42;
const ALTO_REGLA = 18;
const ALTO = ALTO_MINI + ALTO_ONDA + ALTO_REGLA;

export default function LineaTiempo(p: Props) {
  const marco = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ancho, setAncho] = useState(600);
  const [arrastre, setArrastre] = useState<"ini" | "fin" | null>(null);

  const desde = Math.max(0, Math.min(p.ini, p.ini0) - MARGEN_MS);
  const hasta = Math.max(p.fin, p.fin0) + MARGEN_MS;
  const anchoTotal = Math.round(ancho * p.zoom);
  const escala = anchoTotal / (hasta - desde); // px por ms
  const x = (ms: number) => (ms - desde) * escala;
  const ms = (px: number) => desde + px / escala;

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

  // Forma de onda, miniaturas y regla, en el eje del original: cada columna de píxel se lleva al segundo del video actual
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = anchoTotal * dpr;
    c.height = ALTO * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, anchoTotal, ALTO);
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
    g.save();
    g.beginPath();
    g.rect(x0v, 0, x1v - x0v, ALTO_MINI);
    g.clip();
    g.fillStyle = "#1a1a1a";
    g.fillRect(x0v, 0, x1v - x0v, ALTO_MINI);
    if (p.miniaturas && p.miniaturas.length) {
      const tw = Math.max(18, Math.round(ALTO_MINI * (p.formato === "vertical" ? 9 / 16 : 16 / 9)));
      for (let px = x0v; px < x1v; px += tw) {
        const tTramo = (ms(px + tw / 2) - p.ini0) / 1000;
        const tv = tramoAVideo(tTramo, p.timeline, p.duracionVideo);
        if (tv === null) continue;
        let mejor = p.miniaturas[0];
        for (const m of p.miniaturas) if (Math.abs(m.t - tv) < Math.abs(mejor.t - tv)) mejor = m;
        try {
          g.drawImage(mejor.img, px, 0, tw, ALTO_MINI);
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
        const tTramo = (ms(px) - p.ini0) / 1000;
        const tv = tramoAVideo(tTramo, p.timeline, p.duracionVideo);
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
  }, [anchoTotal, p.picos, p.miniaturas, p.piezas, p.ini0, p.fin0, p.timeline, p.duracionVideo, p.formato, desde, hasta, escala]);

  // Arrastre de manijas (mouse y touch, vía pointer events)
  useEffect(() => {
    if (!arrastre) return;
    const mover = (e: PointerEvent) => {
      const r = ref.current!.getBoundingClientRect();
      const m = Math.round(ms(Math.min(Math.max(0, e.clientX - r.left), anchoTotal)) / 100) * 100;
      if (arrastre === "ini") p.onIni(Math.max(0, Math.min(m, p.fin - 2000)));
      else p.onFin(Math.max(m, p.ini + 2000));
    };
    const soltar = () => setArrastre(null);
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
    window.addEventListener("pointercancel", soltar);
    return () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
      window.removeEventListener("pointercancel", soltar);
    };
  });

  // Cabezal: segundo del video actual → ms del original
  const cabezal = useMemo(() => {
    const t = p.tiempoVideo;
    let tTramo = t;
    if (p.timeline && p.timeline.length) {
      let acum = 0;
      tTramo = p.timeline[p.timeline.length - 1][1];
      for (const [a, b] of p.timeline) {
        if (t <= acum + (b - a)) {
          tTramo = a + (t - acum);
          break;
        }
        acum += b - a;
      }
    }
    return p.ini0 + tTramo * 1000;
  }, [p.tiempoVideo, p.timeline, p.ini0]);

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
    const m = Math.round(ms(e.clientX - r.left));
    p.onIr(m);
    if (p.piezas.length > 1) {
      const i = p.piezas.findIndex((z) => m >= z.a && m < z.b);
      p.onSeleccion(i >= 0 ? i : null);
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

  const manija = (cual: "ini" | "fin") => {
    const valor = cual === "ini" ? p.ini : p.fin;
    return (
      <div
        className={"manija " + cual + (arrastre === cual ? " arrastrando" : "")}
        style={{ left: x(valor) }}
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
          setArrastre(cual);
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

  return (
    <div className="linea-marco" ref={marco}>
      <div className="linea" ref={ref} onClick={clic} style={{ width: anchoTotal, height: CARRIL + ALTO }}>
        <canvas ref={canvas} style={{ width: anchoTotal, height: ALTO, top: CARRIL }} />
        {/* pedazos conservados / sacados */}
        {p.piezas.map((z, i) => (
          <div
            key={i}
            className={"pieza " + (z.conservada ? "conservada" : "sacada") + (p.seleccion === i && p.piezas.length > 1 ? " seleccionada" : "")}
            style={{ left: x(z.a), width: Math.max(2, x(z.b) - x(z.a)), top: CARRIL }}
          >
            {p.piezas.length > 1 && x(z.b) - x(z.a) > 44 && (
              <button
                type="button"
                className={"pieza-chip" + (z.conservada ? "" : " restaurar")}
                title={z.conservada ? "Sacar este pedazo del recorte" : "Volver a conservar este pedazo"}
                onClick={(e) => {
                  e.stopPropagation();
                  p.onPieza(i);
                }}
              >
                <Icono nombre={z.conservada ? "tijera" : "deshacer"} tam={13} />
                {z.conservada ? `${((z.b - z.a) / 1000).toFixed(1)} s` : "Restaurar"}
              </button>
            )}
          </div>
        ))}
        {/* fuera del tramo elegido: oscurecido */}
        <div className="fuera" style={{ left: 0, width: x(p.ini), top: CARRIL }} />
        <div className="fuera" style={{ left: x(p.fin), width: Math.max(0, anchoTotal - x(p.fin)), top: CARRIL }} />
        {/* cabezal con tiempo y tijera */}
        <div className="cabezal" style={{ left: x(cabezal) }}>
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
