// Reglas y textos de publicar_ui.py que la pantalla necesita ANTES de llamar a la API (la API los vuelve a aplicar):
// el aviso de qué va a pasar al enviar, el texto plano para redes (vista previa) y el armado del formulario desde una pieza guardada.
import type { Canal, OpcionesPublicar, PiezaForm, PiezaGuardada } from "../tiposPublicar";
import type { Pieza } from "../tiposChat";

export const CANALES: { clave: Canal; nombre: string; detalle: string }[] = [
  { clave: "instagram", nombre: "Instagram", detalle: "foto con la frase, reel o historia" },
  { clave: "facebook", nombre: "Facebook", detalle: "posteo en la página" },
  { clave: "wordpress", nombre: "Blogpost", detalle: "entrada en viviragradecidos.org" },
  { clave: "youtube", nombre: "YouTube", detalle: "un recorte como video" },
];
export const NOMBRE_CANAL: Record<string, string> = { wordpress: "Blogpost", instagram: "Instagram", facebook: "Facebook", youtube: "YouTube", newsletter: "Newsletter" };
const NOMBRE_API: Record<string, string> = { wordpress: "WordPress", instagram: "Instagram", facebook: "Facebook", youtube: "YouTube" };

/** publicar_ui._va_a_la_cola */
export function vaALaCola(canal: string, modo: string): boolean {
  if (modo === "apagado") return false;
  if (canal === "instagram") return true;
  if (canal === "facebook") return modo !== "real";
  return false;
}

/** publicar_ui._aviso: qué va a pasar al enviar, en una o dos frases (sin markdown). */
export function aviso(canal: string, modo: string, fechaIso: string | null): string {
  const nombre = NOMBRE_API[canal] || canal;
  const cuando = fechaIso ? fechaIso.slice(0, 16).replace("T", " ") : "";
  if (modo === "apagado") return `${nombre} está apagado. No se puede hacer nada por este canal.`;
  let a: string;
  if (modo === "simulado") {
    a = `Se arma la pieza tal cual saldría en ${nombre} y se muestra acá. No se manda.`;
    if (fechaIso && canal === "facebook") a += " (En modo real, Facebook sí acepta programación.)";
  } else if (modo === "privado") {
    a = "Se sube el video a YouTube como privado. No lo ve nadie hasta que lo publiques desde YouTube Studio.";
  } else if (modo === "borrador") {
    a = "Se crea la entrada en borrador en viviragradecidos.org. No se publica ni sale por newsletter hasta que la publiques desde WordPress.";
    if (fechaIso) a += ` La fecha ${cuando} queda guardada en el borrador.`;
  } else {
    a = `Modo REAL: se publica en ${nombre} de verdad.`;
    if (fechaIso && canal === "wordpress") a = `Modo REAL: se programa en WordPress para el ${cuando} y sale sola ese día (y por newsletter).`;
    if (fechaIso && canal === "facebook") a = `Modo REAL: se programa en Facebook para el ${cuando} (mínimo 10 minutos de anticipación).`;
    if (fechaIso && canal === "youtube") a = `Modo REAL: se sube ahora y YouTube lo publica solo el ${cuando}.`;
  }
  if (canal === "youtube" && (modo === "privado" || modo === "real")) a += " (Hasta que Google audite el proyecto, YouTube deja los videos subidos por API en privado: se publican desde YouTube Studio.)";
  if (fechaIso && vaALaCola(canal, modo)) {
    a = `Queda en la cola para el ${cuando}: no se manda ahora. Ese día sale sola por ${nombre} con el modo que tenga el canal en ese momento (hoy ${modo}${modo === "simulado" ? ": se arma y se muestra, no se publica" : ""}).`;
  }
  return a;
}

/** publicar_ui._texto_plano: para redes, saca markdown y links (la API lo vuelve a aplicar al enviar). */
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

function canalValido(c: string | null | undefined): Canal | "" {
  return c === "wordpress" || c === "instagram" || c === "facebook" || c === "youtube" ? c : "";
}

/** De una pieza guardada (borrador de Streamlit o de la web: claves cortas) al formulario. */
export function desdeGuardada(g: PiezaGuardada, op: OpcionesPublicar | null): PiezaForm {
  const base = formularioVacio(op);
  const canal = canalValido(g.canal);
  return {
    ...base,
    canal,
    titulo: g.titulo || "",
    texto: g.texto || "",
    imagen_url: g.url || null,
    imagen_busqueda: g.busq || g.imagen_busqueda || "",
    fecha: g.fecha || null,
    hora: g.hora || base.hora,
    texto_imagen: g.texto_imagen || "",
    firma: g.firma ?? base.firma,
    formato: g.fmt || op?.formato_por_canal[canal] || base.formato,
    tipografia: g.tipo || base.tipografia,
    peso: g.peso || base.peso,
    posicion: g.pos || base.posicion,
    alineacion: g.ali || base.alineacion,
    logo: g.logo || base.logo,
    posicion_logo: g.plogo || base.posicion_logo,
    usar_compuesta: g.usar_comp ?? true,
    video_url: g.video_url || null,
    video_formato: g.video_formato || null,
    vfmt: g.vfmt || base.vfmt,
    borrador_id: g._pid || null,
  };
}

/** De la pieza que propone el bot en el chat (proponer_publicacion) al formulario. */
export function desdePropuesta(p: Pieza, op: OpcionesPublicar | null): PiezaForm {
  const base = formularioVacio(op);
  const canal = canalValido(p.canal);
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

/** Desde la tarjeta de un recorte listo («Publicar»): pieza de video, como publicar_ui._mis_recortes. */
export function desdeRecorte(r: { url: string | null; formato: string; titulo: string | null }, op: OpcionesPublicar | null): PiezaForm {
  const base = formularioVacio(op);
  return { ...base, canal: r.formato === "vertical" ? "instagram" : "", titulo: (r.titulo || "").slice(0, 100), video_url: r.url, video_formato: r.formato, vfmt: "reel" };
}
