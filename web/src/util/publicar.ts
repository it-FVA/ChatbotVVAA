// Textos y helpers de la pantalla de Diseñar: el texto plano para redes (vista previa) y el armado del formulario desde una pieza guardada.
// (3/11) Las listas de canales, los nombres y el aviso de qué va a pasar al enviar ya NO viven acá: vienen de la API (registro canales.py):
// GET /yo → `canales`, GET /publicar/opciones → `canales[clave]` con `aviso_sin_fecha` / `aviso_con_fecha`.
import type { CanalInfo } from "../tipos";
import type { CanalOpcion, OpcionesPublicar, PiezaForm, PiezaGuardada } from "../tiposPublicar";
import type { Pieza } from "../tiposChat";

/** El nombre visible de un canal según el registro de la API (o la clave, si no está). */
export function nombreCanal(canales: CanalInfo[] | undefined | null, clave: string | null | undefined): string {
  return canales?.find((c) => c.clave === clave)?.texto || clave || "";
}

/** Aviso: qué va a pasar al enviar, armado por la API para el modo que ve esta persona; acá solo se pone la fecha. */
export function aviso(info: CanalOpcion, fechaIso: string | null): string {
  const cuando = fechaIso ? fechaIso.slice(0, 16).replace("T", " ") : "";
  return (fechaIso ? info.aviso_con_fecha : info.aviso_sin_fecha).replace("{cuando}", cuando);
}

/** Texto plano: para redes, saca markdown y links (la API lo vuelve a aplicar al enviar). */
export function textoPlano(t: string): string {
  return (t || "")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, "$1")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")
    .replace(/^\s*>\s?/gm, "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/(^|[^\w])[_*](.+?)[_*](?!\w)/g, "$1$2")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function manana(): string {
  const d = new Date(Date.now() + 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function fechaIsoDe(p: { fecha: string | null; hora: string | null }): string | null {
  if (!p.fecha) return null;
  const [hh, mm] = (p.hora || "09:00").split(":");
  return `${p.fecha}T${hh.padStart(2, "0")}:${(mm || "00").padStart(2, "0")}:00`;
}

const ZONA_AR = "America/Argentina/Buenos_Aires";
const DIAS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

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
  const dia = `${(partes.weekday || "").replace(".", "").slice(0, 3) || DIAS[d.getDay()]} ${partes.day}/${partes.month}`;
  return conHora && !/T00:00:00-03:00$/.test(s) ? `${dia} ${partes.hour}:${partes.minute}` : dia;
}

/** Fecha de creación (UTC en la base) en hora local, corta. */
export function fechaCorta(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + "Z");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

export function formularioVacio(op?: OpcionesPublicar | null): PiezaForm {
  return {
    canal: "",
    titulo: "",
    texto: "",
    imagen_url: null,
    imagen_busqueda: "",
    fecha: null,
    hora: "09:00",
    texto_imagen: "",
    firma: op?.firma_defecto ?? "— Br. David",
    formato: "cuadrado",
    tipografia: op?.tipografia_defecto ?? "Raleway (Fundación)",
    peso: "normal",
    posicion: "centro",
    alineacion: "centro",
    logo: "Sin logo",
    posicion_logo: "abajo derecha",
    usar_compuesta: true,
    video_url: null,
    video_formato: null,
    vfmt: "reel",
    borrador_id: null,
  };
}

/** La clave si es un canal de Diseñar (los que manda la API en opciones), si no ''. */
function canalValido(c: string | null | undefined, op: OpcionesPublicar | null): string {
  return c && op?.canales[c] ? c : "";
}

/** De una pieza guardada (GET /publicaciones/{id} → `pieza`, los campos del modelo Pieza de la API) al formulario. */
export function desdeGuardada(g: PiezaGuardada, op: OpcionesPublicar | null): PiezaForm {
  const base = formularioVacio(op);
  const canal = canalValido(g.canal, op);
  return {
    ...base,
    canal,
    titulo: g.titulo || "",
    texto: g.texto || "",
    imagen_url: g.imagen_url || null,
    imagen_busqueda: g.imagen_busqueda || "",
    fecha: g.fecha || null,
    hora: g.hora || base.hora,
    texto_imagen: g.texto_imagen || "",
    firma: g.firma ?? base.firma,
    formato: g.formato || op?.formato_por_canal[canal] || base.formato,
    tipografia: g.tipografia || base.tipografia,
    peso: g.peso || base.peso,
    posicion: g.posicion || base.posicion,
    alineacion: g.alineacion || base.alineacion,
    logo: g.logo || base.logo,
    posicion_logo: g.posicion_logo || base.posicion_logo,
    usar_compuesta: g.usar_compuesta ?? true,
    video_url: g.video_url || null,
    video_formato: g.video_formato || null,
    vfmt: g.vfmt || base.vfmt,
    borrador_id: g.borrador_id || null,
  };
}

/** De la pieza que propone el bot en el chat (proponer_publicacion) al formulario. */
export function desdePropuesta(p: Pieza, op: OpcionesPublicar | null): PiezaForm {
  const base = formularioVacio(op);
  const canal = canalValido(p.canal, op);
  return {
    ...base,
    canal,
    titulo: p.titulo || "",
    texto: p.texto || "",
    imagen_busqueda: p.imagen_busqueda || "",
    texto_imagen: p.texto_imagen || "",
    firma: p.firma || base.firma,
    formato: op?.formato_por_canal[canal] || base.formato,
    fecha: p.fecha || null,
    hora: p.hora || base.hora,
  };
}

/** Desde la tarjeta de un recorte listo («Publicar»): pieza de video. */
export function desdeRecorte(r: { url: string | null; formato: string; titulo: string | null }, op: OpcionesPublicar | null): PiezaForm {
  const base = formularioVacio(op);
  return { ...base, canal: r.formato === "vertical" ? "instagram" : "", titulo: (r.titulo || "").slice(0, 100), video_url: r.url, video_formato: r.formato, vfmt: "reel" };
}
