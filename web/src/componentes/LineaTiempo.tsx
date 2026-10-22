// Línea de tiempo del editor: el eje es el video ORIGINAL (milisegundos absolutos), desde un poco antes del inicio del recorte
// actual hasta un poco después del fin. Encima: la forma de onda del audio del recorte (decodificada en el navegador; si el
// navegador no la puede bajar, marcas cada segundo), los pedazos conservados (color) y sacados (gris), la zona fuera del video
// actual (rayada: no se puede ver hasta regenerar), el cabezal del reproductor y dos manijas arrastrables (inicio y fin).
import { useEffect, useMemo, useRef, useState } from "react";
import { mmss, tramoAVideo, type Timeline } from "../util/tiempo";

export interface Pieza {
  a: number; // ms absolutos del original
  b: number;
  conservada: boolean;
}

interface Props {
  ini: number; // manija de inicio (ms absolutos)
  fin: number;
  ini0: number; // tramo del video actual (columnas de la fila)
  fin0: number;
  piezas: Pieza[];
  timeline: Timeline; // cómo el video actual mapea al tramo plano
  duracionVideo: number; // segundos del video actual
  tiempoVideo: number; // segundo actual del reproductor
  picos: Float32Array | null; // forma de onda del video actual (un valor cada PASO_MS)
  onIni: (ms: number) => void;
  onFin: (ms: number) => void;
  onIr: (msOriginal: number) => void; // clic en la línea
  onPieza: (i: number) => void; // clic en un pedazo (conservar / sacar)
}

export const PASO_MS = 50;
const MARGEN_MS = 10000;
const ALTO = 96;

export default function LineaTiempo(p: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [ancho, setAncho] = useState(600);
  const [arrastre, setArrastre] = useState<"ini" | "fin" | null>(null);

  const desde = Math.max(0, Math.min(p.ini, p.ini0) - MARGEN_MS);
  const hasta = Math.max(p.fin, p.fin0) + MARGEN_MS;
  const escala = ancho / (hasta - desde); // px por ms
  const x = (ms: number) => (ms - desde) * escala;
  const ms = (px: number) => desde + px / escala;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setAncho(el.clientWidth));
    ro.observe(el);
    setAncho(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Forma de onda (o marcas de segundo) dibujada en el eje del original: cada columna de píxel se lleva al segundo del video actual
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = ancho * dpr;
    c.height = ALTO * dpr;
    const g = c.getContext("2d")!;
    g.scale(dpr, dpr);
    g.clearRect(0, 0, ancho, ALTO);
    // zona fuera del video actual: rayada
    g.fillStyle = "rgba(0,0,0,0.04)";
    g.fillRect(0, 0, ancho, ALTO);
    const rayas = (x0: number, x1: number) => {
      g.save();
      g.beginPath();
      g.rect(x0, 0, x1 - x0, ALTO);
      g.clip();
      g.strokeStyle = "rgba(0,0,0,0.08)";
      g.lineWidth = 1;
      for (let i = -ALTO; i < x1 - x0 + ALTO; i += 8) {
        g.beginPath();
        g.moveTo(x0 + i, 0);
        g.lineTo(x0 + i + ALTO, ALTO);
        g.stroke();
      }
      g.restore();
    };
    rayas(0, x(p.ini0));
    rayas(x(p.fin0), ancho);
    // onda
    const mid = ALTO / 2;
    if (p.picos && p.picos.length) {
      for (let px = Math.floor(x(p.ini0)); px <= Math.ceil(x(p.fin0)); px++) {
        const tTramo = (ms(px) - p.ini0) / 1000;
        const tv = tramoAVideo(tTramo, p.timeline, p.duracionVideo);
        if (tv === null) continue;
        const i = Math.min(p.picos.length - 1, Math.floor((tv * 1000) / PASO_MS));
        const v = p.picos[i] || 0;
        const h = Math.max(1, v * (ALTO - 16));
        const dentro = p.piezas.some((z) => z.conservada && ms(px) >= z.a && ms(px) <= z.b);
        g.fillStyle = dentro ? "rgba(58,107,53,0.75)" : "rgba(120,120,120,0.35)";
        g.fillRect(px, mid - h / 2, 1, h);
      }
    } else {
      // sin onda: marcas cada segundo
      g.fillStyle = "rgba(58,107,53,0.35)";
      for (let t = Math.ceil(p.ini0 / 1000) * 1000; t <= p.fin0; t += 1000) {
        const alto = t % 5000 === 0 ? 28 : 14;
        g.fillRect(x(t), mid - alto / 2, 1, alto);
      }
    }
    // escala de tiempo (cada 5 s, o 10 s si está apretado)
    const paso = escala * 5000 < 60 ? 10000 : 5000;
    g.fillStyle = "rgba(0,0,0,0.45)";
    g.font = "11px Raleway, sans-serif";
    for (let t = Math.ceil(desde / paso) * paso; t <= hasta; t += paso) {
      g.fillRect(x(t), ALTO - 10, 1, 10);
      g.fillText(mmss(t), x(t) + 3, ALTO - 2);
    }
  }, [ancho, p.picos, p.piezas, p.ini0, p.fin0, p.timeline, p.duracionVideo, desde, hasta, escala]);

  // Arrastre de manijas (mouse y touch, vía pointer events)
  useEffect(() => {
    if (!arrastre) return;
    const mover = (e: PointerEvent) => {
      const r = ref.current!.getBoundingClientRect();
      const m = Math.round(ms(Math.min(Math.max(0, e.clientX - r.left), ancho)) / 100) * 100;
      if (arrastre === "ini") p.onIni(Math.max(0, Math.min(m, p.fin - 2000)));
      else p.onFin(Math.max(m, p.ini + 2000));
    };
    const soltar = () => setArrastre(null);
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
    return () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
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

  function clic(e: React.MouseEvent) {
    if (arrastre) return;
    const r = ref.current!.getBoundingClientRect();
    p.onIr(Math.round(ms(e.clientX - r.left)));
  }

  return (
    <div className="linea" ref={ref} onClick={clic}>
      <canvas ref={canvas} style={{ width: ancho, height: ALTO }} />
      {/* pedazos conservados / sacados */}
      {p.piezas.map((z, i) => (
        <div key={i} className={"pieza " + (z.conservada ? "conservada" : "sacada")} style={{ left: x(z.a), width: Math.max(2, x(z.b) - x(z.a)) }}>
          {p.piezas.length > 1 && x(z.b) - x(z.a) > 30 && (
            <button
              type="button"
              className="pieza-chip"
              title={z.conservada ? "Sacar este pedazo del recorte" : "Volver a conservar este pedazo"}
              onClick={(e) => {
                e.stopPropagation();
                p.onPieza(i);
              }}
            >
              {z.conservada ? "✓" : "✕"} {((z.b - z.a) / 1000).toFixed(1)} s
            </button>
          )}
        </div>
      ))}
      {/* fuera del tramo elegido: oscurecido */}
      <div className="fuera" style={{ left: 0, width: x(p.ini) }} />
      <div className="fuera" style={{ left: x(p.fin), width: Math.max(0, ancho - x(p.fin)) }} />
      {/* cabezal */}
      <div className="cabezal" style={{ left: x(cabezal) }} />
      {/* manijas */}
      <div
        className="manija ini"
        style={{ left: x(p.ini) }}
        onPointerDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setArrastre("ini");
        }}
        onClick={(e) => e.stopPropagation()}
        title="Arrastrá para mover el inicio"
      >
        <span>{mmss(p.ini, 1)}</span>
      </div>
      <div
        className="manija fin"
        style={{ left: x(p.fin) }}
        onPointerDown={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setArrastre("fin");
        }}
        onClick={(e) => e.stopPropagation()}
        title="Arrastrá para mover el fin"
      >
        <span>{mmss(p.fin, 1)}</span>
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
