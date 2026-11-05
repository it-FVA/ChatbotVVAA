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

export function formularioVacio(op?: OpcionesPublicar | null): PiezaForm {
  return {
    canal: "",
    titulo: "",
    texto: "",
    imagen_url: null,
    imagenes: null,
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
    imagenes: (g as { imagenes?: string[] | null }).imagenes?.length ? (g as { imagenes?: string[] | null }).imagenes! : null,
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
