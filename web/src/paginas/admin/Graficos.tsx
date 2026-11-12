// Gráficos simples en SVG propio (22/10), sin librerías: barras apiladas por serie (conversaciones por semana por persona,
// costo por día por persona), barras simples (costo por mes) y un medidor de uso contra el límite con el umbral marcado.
// Cada barra lleva un <title> con el detalle (se ve al pasar el mouse o con lector de pantalla).
import { colorDe } from "./comun";

export interface Columna {
  etiqueta: string; // lo que se ve abajo
  titulo?: string; // el detalle del <title>
  valores: Record<string, number>; // serie → valor
}

interface Props {
  columnas: Columna[];
  series: string[];
  formato?: (n: number) => string;
  alto?: number;
  titulo: string; // aria-label
  vacio?: string;
}

const ANCHO = 720;
const MARGEN = { arriba: 10, abajo: 26, izq: 44, der: 8 };

function escalaY(max: number) {
  // 3 o 4 marcas «redondas» entre 0 y el máximo
  if (max <= 0) return [0];
  const paso = Math.pow(10, Math.floor(Math.log10(max)));
  const cand = [paso / 4, paso / 2, paso, paso * 2, paso * 5];
  const p = cand.find((c) => max / c <= 4) ?? paso * 5;
  const marcas = [];
  for (let v = 0; v <= max + 1e-9; v += p) marcas.push(v);
  if (marcas[marcas.length - 1] < max) marcas.push(marcas[marcas.length - 1] + p);
  return marcas;
}

export function BarrasApiladas({ columnas, series, formato = (n) => String(n), alto = 220, titulo, vacio = "Sin datos en el período." }: Props) {
  if (!columnas.length) return <p className="suave chico">{vacio}</p>;
  const totales = columnas.map((c) => series.reduce((s, k) => s + (c.valores[k] || 0), 0));
  const marcas = escalaY(Math.max(...totales, 0));
  const maxY = marcas[marcas.length - 1] || 1;
  const altoUtil = alto - MARGEN.arriba - MARGEN.abajo;
  const anchoUtil = ANCHO - MARGEN.izq - MARGEN.der;
  const paso = anchoUtil / columnas.length;
  const anchoBarra = Math.min(48, paso * 0.68);
  const y = (v: number) => MARGEN.arriba + altoUtil - (v / maxY) * altoUtil;
  const cadaN = Math.ceil(columnas.length / 14); // etiquetas que entran
  return (
    <figure className="grafico">
      <svg viewBox={`0 0 ${ANCHO} ${alto}`} role="img" aria-label={titulo} preserveAspectRatio="none">
        {marcas.map((m) => (
          <g key={m}>
            <line x1={MARGEN.izq} x2={ANCHO - MARGEN.der} y1={y(m)} y2={y(m)} className="grafico-grilla" />
            <text x={MARGEN.izq - 6} y={y(m) + 4} className="grafico-eje" textAnchor="end">
              {formato(m)}
            </text>
          </g>
        ))}
        {columnas.map((c, i) => {
          let acum = 0;
          const x = MARGEN.izq + paso * i + (paso - anchoBarra) / 2;
          return (
            <g key={c.etiqueta + i}>
              <title>{(c.titulo ?? c.etiqueta) + ": " + formato(totales[i]) + series.filter((k) => c.valores[k]).map((k) => `\n${k}: ${formato(c.valores[k])}`).join("")}</title>
              {series.map((k, j) => {
                const v = c.valores[k] || 0;
                if (!v) return null;
                const y1 = y(acum + v);
                const h = y(acum) - y1;
                acum += v;
                return <rect key={k} x={x} y={y1} width={anchoBarra} height={Math.max(h, 0.5)} fill={colorDe(j)} rx={j === series.length - 1 || acum >= totales[i] ? 3 : 0} />;
              })}
              {totales[i] === 0 && <rect x={x} y={y(0) - 1} width={anchoBarra} height={1} fill="#cfc7b6" />}
              {i % cadaN === 0 && (
                <text x={x + anchoBarra / 2} y={alto - 8} className="grafico-eje" textAnchor="middle">
                  {c.etiqueta}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      {series.length > 1 && (
        <figcaption className="grafico-leyenda">
          {series.map((k, j) => (
            <span key={k}>
              <i style={{ background: colorDe(j) }} aria-hidden="true" /> {k}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}

/** Barra horizontal de uso contra el límite (capacidad): el umbral marcado con una línea, el color según el estado. */
export function Medidor({ porcentaje, umbral, estado, etiqueta }: { porcentaje: number | null; umbral: number; estado: string; etiqueta: string }) {
  const p = porcentaje === null ? 0 : Math.min(porcentaje, 100);
  return (
    <div className={"medidor e-" + estado} role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={porcentaje ?? undefined} aria-label={etiqueta} title={porcentaje === null ? "Sin dato" : `${porcentaje} % del límite · umbral ${umbral} %`}>
      <div className="medidor-pista">
        <div className="medidor-uso" style={{ width: `${p}%` }} />
        <div className="medidor-umbral" style={{ left: `${Math.min(umbral, 100)}%` }} aria-hidden="true">
          <span>{umbral} %</span>
        </div>
      </div>
    </div>
  );
}

export interface PuntoLinea {
  etiqueta: string; // ej. «12/11»
  valor: number;
  titulo?: string; // el detalle del <title> de ese punto
}

/** (12/11, Franco) Línea chica tipo sparkline para las tarjetas de Métricas: una sola línea, sin ejes, el último punto marcado.
 *  Cada punto lleva su <title> (se ve al pasar el mouse o con lector de pantalla). Con un solo punto dibuja solo el punto. */
export function Linea({ puntos, titulo, formato = (n) => String(n), alto = 44 }: { puntos: PuntoLinea[]; titulo: string; formato?: (n: number) => string; alto?: number }) {
  if (!puntos.length) return null;
  const ANCHO_L = 200;
  const m = 5;
  const valores = puntos.map((p) => p.valor);
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const x = (i: number) => (puntos.length === 1 ? ANCHO_L / 2 : m + (i * (ANCHO_L - 2 * m)) / (puntos.length - 1));
  const y = (v: number) => (max === min ? alto / 2 : alto - m - ((v - min) / (max - min)) * (alto - 2 * m));
  const ultimo = puntos.length - 1;
  return (
    <svg className="linea" viewBox={`0 0 ${ANCHO_L} ${alto}`} role="img" aria-label={titulo}>
      {puntos.length > 1 && <polyline className="linea-trazo" fill="none" points={puntos.map((p, i) => `${x(i).toFixed(1)},${y(p.valor).toFixed(1)}`).join(" ")} />}
      {puntos.map((p, i) => (
        <g key={p.etiqueta + i}>
          <title>{p.titulo ?? `${p.etiqueta}: ${formato(p.valor)}`}</title>
          <circle cx={x(i)} cy={y(p.valor)} r={i === ultimo ? 3.2 : 5} className={i === ultimo ? "linea-ultimo" : "linea-toque"} />
        </g>
      ))}
    </svg>
  );
}
