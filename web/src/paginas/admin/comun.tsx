// Piezas compartidas por las pantallas de Administración (22/10): formatos (US$, miles, «hace»), chip de estado ok/aviso/error,
// tarjeta de métrica, plegable, iconos propios de esta sección (mismo trazo que componentes/Iconos.tsx) y la paleta de los gráficos.
import { useState, type CSSProperties, type ReactNode } from "react";
import type { Estado } from "./adminApi";

export const NOMBRES_CHEQUEO: Record<string, string> = {
  supabase: "Supabase (base de datos)",
  openai: "OpenAI (modelo)",
  wordpress: "WordPress (sitio y cola)",
  instagram: "Instagram (token)",
  facebook: "Facebook (token)",
  drive: "Google Drive (permiso)",
  youtube: "YouTube (permiso)",
  cola_publicacion: "Cola de publicación",
  recortes: "Recortes (cola)",
  frase_del_dia: "Frase del día",
  api: "API (Render)",
  web: "Web (Vercel)",
  memoria: "Memoria de la API",
};

export const nombreChequeo = (n: string) => NOMBRES_CHEQUEO[n] || n;

export const ESTADO_TEXTO: Record<string, string> = { ok: "ok", aviso: "aviso", error: "error", sin_dato: "sin dato", arranque: "arranque" };

/** US$ con dos decimales; con cuatro cuando es menos de un centavo (los primeros días del registro). */
export function usd(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  const dec = x > 0 && x < 0.01 ? 4 : 2;
  return "US$ " + x.toLocaleString("es-AR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export const miles = (n: number | null | undefined) => (n === null || n === undefined ? "—" : Math.round(n).toLocaleString("es-AR"));

export const pct = (x: number | null | undefined, dec = 0) => (x === null || x === undefined ? "—" : (x * 100).toFixed(dec).replace(".", ",") + " %");

export function fecha(iso: string | null | undefined, conHora = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const f = d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "2-digit" });
  return conHora ? f + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" }) : f;
}

/** «hace 5 min», «hace 3 h», «ayer», «hace 12 días» (como publicar_ui._hace). */
export function hace(iso: string | null | undefined): string {
  if (!iso) return "nunca";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const seg = (Date.now() - d.getTime()) / 1000;
  if (seg < 60) return "recién";
  if (seg < 3600) return `hace ${Math.floor(seg / 60)} min`;
  if (seg < 86400) return `hace ${Math.floor(seg / 3600)} h`;
  const dias = Math.floor(seg / 86400);
  if (dias === 1) return "ayer";
  if (dias < 60) return `hace ${dias} días`;
  return fecha(iso, false);
}

/** Días que faltan hasta una fecha ISO (negativo si ya pasó). */
export function diasHasta(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((d.getTime() - Date.now()) / 86400000);
}

export const diaCorto = (ymd: string) => (ymd.length >= 10 ? `${ymd.slice(8, 10)}/${ymd.slice(5, 7)}` : ymd);

export function EstadoChip({ estado, texto }: { estado: Estado; texto?: string }) {
  return (
    <span className={"estado-chip " + estado} role="status">
      <span className="punto" aria-hidden="true" />
      {texto ?? ESTADO_TEXTO[estado] ?? estado}
    </span>
  );
}

export function Metrica({ etiqueta, valor, detalle, estado, children }: { etiqueta: string; valor: ReactNode; detalle?: ReactNode; estado?: Estado; children?: ReactNode }) {
  return (
    <div className={"metrica tarjeta" + (estado ? " " + estado : "")}>
      <div className="metrica-etiqueta">{etiqueta}</div>
      <div className="metrica-valor">{valor}</div>
      {detalle && <div className="metrica-detalle suave chico">{detalle}</div>}
      {children}
    </div>
  );
}

export function Plegable({ titulo, abierto = false, children, resumen }: { titulo: ReactNode; abierto?: boolean; children: ReactNode; resumen?: ReactNode }) {
  const [open, setOpen] = useState(abierto);
  return (
    <details className="tarjeta plegable" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>
        <IconoAdmin nombre="chevron" tam={16} style={{ transform: open ? "rotate(90deg)" : undefined }} />
        <span>{titulo}</span>
        {resumen && <span className="suave chico plegable-resumen">{resumen}</span>}
      </summary>
      <div className="plegable-cuerpo">{children}</div>
    </details>
  );
}

export function Cargando({ filas = 3 }: { filas?: number }) {
  return (
    <div className="tarjeta" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: filas }, (_, i) => (
        <div key={i} className="hueso" style={{ height: 36, marginBottom: 10, borderRadius: 8 }} />
      ))}
    </div>
  );
}

export function AvisoError({ texto }: { texto: string }) {
  return (
    <div className="aviso error" role="alert">
      <IconoAdmin nombre="alerta" tam={18} /> {texto}
    </div>
  );
}

/** Iconos de esta sección (no están en componentes/Iconos.tsx, que es compartido con las otras pantallas). */
const TRAZOS: Record<string, string> = {
  tablero: "M3 3h8v8H3zM13 3h8v5h-8zM13 11h8v10h-8zM3 14h8v7H3z",
  pulso: "M3 12h4l3-8 4 16 3-8h4",
  moneda: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM15 9.5c-.6-.9-1.7-1.5-3-1.5-1.8 0-3 .9-3 2s1.2 1.7 3 2 3 .9 3 2-1.2 2-3 2c-1.3 0-2.4-.6-3-1.5M12 6v2M12 16v2",
  engranaje: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
  usuarios: "M16 19v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM22 19v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  check: "M5 12l4 4L19 7",
  cruz: "M6 6l12 12M18 6L6 18",
  alerta: "M12 3l10 18H2zM12 10v4M12 17.5v.5",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8v.5",
  reloj: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
  regenerar: "M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6",
  externo: "M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5",
  mas: "M12 5v14M5 12h14",
  lapiz: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  tacho: "M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6",
  chevron: "M9 6l6 6-6 6",
  calendario: "M4 5h16v16H4zM4 10h16M8 3v4M16 3v4",
  escudo: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  subtitulos: "M3 5h18v14H3zM6 12h6M14 12h4M6 15h3M11 15h7",
  megafono: "M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1zM17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12",
};

export type NombreIconoAdmin = keyof typeof TRAZOS;

export function IconoAdmin({ nombre, tam = 18, style }: { nombre: NombreIconoAdmin; tam?: number; style?: CSSProperties }) {
  return (
    <svg className="icono" width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" style={style}>
      <path d={TRAZOS[nombre]} />
    </svg>
  );
}

/** Paleta de los gráficos: verde y amarillo de la marca primero, después tonos que se distinguen entre sí. */
export const PALETA = ["#3a6b35", "#f4b43c", "#5b7fa6", "#b4663c", "#8a6bb5", "#3c9ba0", "#9c8b5a", "#999999"];

export function colorDe(i: number) {
  return PALETA[i % PALETA.length];
}
