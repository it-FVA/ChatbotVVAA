// Todos los formatos de fecha y hora de la web, en un solo lugar (3/11, revisión 5.3 punto 18). Antes había una copia por pantalla.
// fechaHora / fechaCompleta / fechaCreacion: numéricas en hora local («05/11 10:30»). fechaLegible: «mié 5/11 10:30» y horaArgentina:
// «03/11 07:00», en hora de Argentina. diaMes / fechaLarga: de un día «YYYY-MM-DD». relativa (es/en/de) es la de la lista de
// conversaciones y hace (es) la de Administración. diaIso / manana / fechaIsoDe arman fechas.
const TXT = {
  es: { ahora: "recién", min: (n: number) => `hace ${n} min`, h: (n: number) => `hace ${n} h`, ayer: "ayer", dias: (n: number) => `hace ${n} días` },
  en: { ahora: "just now", min: (n: number) => `${n} min ago`, h: (n: number) => `${n} h ago`, ayer: "yesterday", dias: (n: number) => `${n} days ago` },
  de: { ahora: "gerade eben", min: (n: number) => `vor ${n} Min.`, h: (n: number) => `vor ${n} Std.`, ayer: "gestern", dias: (n: number) => `vor ${n} Tagen` },
};

export type Idioma = "es" | "en" | "de";

export function relativa(iso: string, idioma: Idioma = "es", ahora = Date.now()): string {
  const t = TXT[idioma] || TXT.es;
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "";
  const seg = Math.max(0, (ahora - d) / 1000);
  if (seg < 60) return t.ahora;
  if (seg < 3600) return t.min(Math.floor(seg / 60));
  if (seg < 86400) return t.h(Math.floor(seg / 3600));
  const dias = Math.floor(seg / 86400);
  if (dias === 1) return t.ayer;
  if (dias < 7) return t.dias(dias);
  return new Date(iso).toLocaleDateString(idioma === "en" ? "en-GB" : idioma === "de" ? "de-DE" : "es-AR", { day: "2-digit", month: "2-digit", ...(dias > 300 ? { year: "2-digit" } : {}) });
}

/** Grupo de la lista: hoy, ayer, esta semana, antes. */
export function grupo(iso: string, ahora = new Date()): "hoy" | "ayer" | "semana" | "antes" {
  const d = new Date(iso);
  const inicioHoy = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate()).getTime();
  const t = d.getTime();
  if (t >= inicioHoy) return "hoy";
  if (t >= inicioHoy - 86400000) return "ayer";
  if (t >= inicioHoy - 6 * 86400000) return "semana";
  return "antes";
}

// ---------- numéricas, en hora local ----------
export interface OpcionesFechaHora {
  /** Con el año de dos cifras («05/11/26»). */
  anio?: boolean;
  /** Con la hora. Por defecto sí. */
  hora?: boolean;
  /** Qué devolver si no hay fecha. */
  vacio?: string;
  /** Qué devolver si la fecha no se puede leer: el texto tal cual (por defecto) o vacío. */
  invalido?: "texto" | "vacio";
  /** La base guarda la fecha en UTC sin zona («2026-11-03T10:00:00»): se le agrega la «Z» antes de pasarla a hora local. */
  utc?: boolean;
}

export function fechaHora(iso: string | null | undefined, o: OpcionesFechaHora = {}): string {
  if (!iso) return o.vacio ?? "";
  const crudo = o.utc && !(iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso)) ? iso + "Z" : iso;
  const d = new Date(crudo);
  if (Number.isNaN(d.getTime())) return o.invalido === "vacio" ? "" : iso;
  const dia = d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", ...(o.anio ? { year: "2-digit" } : {}) });
  return o.hora === false ? dia : dia + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

/** Con año y «—» si falta: las tablas de Administración. */
export const fechaCompleta = (iso: string | null | undefined, conHora = true) => fechaHora(iso, { anio: true, hora: conHora, vacio: "—" });

/** Fecha de creación de una fila de la base (UTC), sin año. */
export const fechaCreacion = (iso: string | null | undefined) => fechaHora(iso, { utc: true });

/** «hace 5 min», «hace 3 h», «ayer», «hace 12 días»; pasados dos meses, la fecha. */
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
  return fechaCompleta(iso, false);
}

// ---------- hora de Argentina ----------
const ZONA_AR = "America/Argentina/Buenos_Aires";
const DIAS_CORTOS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

/** Fecha y hora legibles («mié 5/11 10:30») en hora de Argentina. Un ISO sin zona (el del formulario) se toma como hora Argentina;
 *  uno con zona (Supabase devuelve las fechas programadas en UTC) se convierte. */
export function fechaLegible(iso: string | null | undefined, conHora = true): string {
  if (!iso) return "";
  let s = String(iso);
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s) && /^\d{4}-\d{2}-\d{2}T/.test(s)) s += "-03:00";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) s += "T00:00:00-03:00";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return String(iso);
  const partes = Object.fromEntries(
    new Intl.DateTimeFormat("es-AR", { timeZone: ZONA_AR, weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })
      .formatToParts(d)
      .map((p) => [p.type, p.value]),
  );
  const dia = `${(partes.weekday || "").replace(".", "").slice(0, 3) || DIAS_CORTOS[d.getDay()]} ${partes.day}/${partes.month}`;
  return conHora && !/T00:00:00-03:00$/.test(s) ? `${dia} ${partes.hour}:${partes.minute}` : dia;
}

/** "2026-11-03T10:00:00+00:00" → "03/11 07:00" en hora Argentina (la cola guarda en UTC y la pantalla mostraba las 10:00). */
export function horaArgentina(iso?: string | null): string {
  if (!iso) return "";
  const f = new Date(iso);
  if (isNaN(f.getTime())) return String(iso).slice(0, 16).replace("T", " ");
  return f.toLocaleString("es-AR", { timeZone: ZONA_AR, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).replace(",", "");
}

// ---------- días «YYYY-MM-DD» ----------
export const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

/** Un Date local → «YYYY-MM-DD». */
export function diaIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** «2026-11-03» → «3 de noviembre de 2026». */
export function fechaLarga(s: string): string {
  const [y, m, d] = s.split("-").map(Number);
  return `${d} de ${MESES[m - 1]} de ${y}`;
}

/** «2026-11-03» → «03/11». */
export function diaMes(s: string): string {
  const [, m, d] = s.split("-").map(Number);
  return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}

/** El día de mañana, «YYYY-MM-DD». */
export function manana(): string {
  return diaIso(new Date(Date.now() + 86400000));
}

/** Fecha y hora del formulario de Publicar → ISO sin zona («2026-11-05T10:30:00»), o null si no hay fecha. */
export function fechaIsoDe(p: { fecha: string | null; hora: string | null }): string | null {
  if (!p.fecha) return null;
  const [hh, mm] = (p.hora || "09:00").split(":");
  return `${p.fecha}T${hh.padStart(2, "0")}:${(mm || "00").padStart(2, "0")}:00`;
}
