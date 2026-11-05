// Lo que devuelve la API para Publicar, Mis publicaciones y Aprobación (api/publicar_rutas.py y GET /publicaciones de api/main.py).
import type { components } from "./tiposApi";

/** (3/11) Un canal de Diseñar tal como lo arma la API (chat_rutas.info_canales, del registro canales.py). */
export interface CanalOpcion {
  nombre: string; // WordPress, Instagram…
  texto_canal: string; // Blogpost, Instagram… (nombre visible)
  detalle: string; // la línea de la tarjeta
  modo_real: string; // apagado | simulado | borrador | privado | real
  modo: string; // el que ve esta persona (desde el 5/11 todos ven simulado: nadie publica directo)
  texto: string;
  a_aprobar: boolean; // hoy se puede mandar a aprobación (el canal lo admite y está en real/borrador)
  acepta_aprobacion: boolean; // el canal pasa por aprobación (YouTube no)
  requiere_titulo: boolean;
  formato: string | null; // formato de foto sugerido
  va_a_la_cola: boolean; // con fecha, la pieza va a la cola (con el modo que ve esta persona)
  configurado: boolean;
  aviso_sin_fecha: string; // qué pasa al enviar (la API lo arma; «{cuando}» = la fecha legible)
  aviso_con_fecha: string;
}

export interface OpcionesPublicar {
  canales: Record<string, CanalOpcion>;
  publica: boolean;
  aprueba: boolean;
  rol: string;
  aprobadores: string[];
  usuario: string;
  logos: string[];
  logos_url: Record<string, string>;
  posiciones_logo: string[];
  tipografias: string[];
  tipografia_defecto: string;
  pesos: string[];
  posiciones: string[];
  alineaciones: string[];
  formatos: Record<string, [number, number]>;
  formato_por_canal: Record<string, string>;
  firma_defecto: string;
  zona: string;
}

/** El estado del formulario de Publicar (= los campos de PiezaApi, con strings en vez de null para los controles).
 *  Si la API suma un campo, `cuerpo()` en apiPublicar.ts deja de compilar hasta que se agregue acá. */
export interface PiezaForm {
  canal: string; // clave del canal ('' = sin elegir); los válidos son los de OpcionesPublicar.canales
  titulo: string;
  texto: string;
  imagen_url: string | null;
  imagenes: string[] | null; // (5/11, Franco) carrusel: de 2 a 10 URLs https en orden; imagen_url es la primera (portada)
  imagen_busqueda: string;
  fecha: string | null; // 'YYYY-MM-DD' o null = sin programar
  hora: string | null;
  texto_imagen: string;
  firma: string;
  formato: string; // cuadrado | vertical | historia
  tipografia: string;
  peso: string;
  posicion: string;
  alineacion: string;
  logo: string;
  posicion_logo: string;
  usar_compuesta: boolean;
  video_url: string | null;
  video_formato: string | null;
  vfmt: string; // reel | historia
  borrador_id: string | null;
}

/** (3/11) La pieza tal como la define la API (api/pieza.py → OpenAPI → tiposApi.d.ts, `npm run tipos`). Es lo que se manda a
 *  /publicar/borrador, /a-aprobar y /enviar, y lo que devuelve GET /publicaciones/{id} en `pieza` (con borrador_id = el id de la fila). */
// (5/11, Franco) `imagenes` (carrusel) lo suma la API en paralelo: hasta que se regeneren los tipos (`npm run tipos`) se declara acá.
export type PiezaApi = components["schemas"]["Pieza"] & { imagenes?: string[] | null };
export type PiezaGuardada = Partial<PiezaApi>;

export interface RespuestaBorrador {
  ok: boolean;
  id: string;
  estado: "borrador";
  mensaje: string;
  version?: string | null; // (5/11) la versión recién guardada
}

export interface RespuestaAprobacion {
  ok: boolean;
  id: string;
  estado: "a_aprobar";
  modo: "aprobacion";
  imagen_url: string | null;
  avisos: string[];
  mensaje: string;
}

export interface RespuestaEnvio {
  ok: boolean;
  modo: string;
  aviso?: string;
  estado?: string;
  id?: string | number;
  link?: string | null;
  link_editar?: string | null;
  permalink?: string | null;
  privacidad?: string;
  pieza?: Record<string, unknown>;
  encolada: boolean;
  imagen_url: string | null;
  avisos: string[];
  simulado: boolean;
  texto_final: string;
  formato: string | null;
  video_url: string | null;
  imagenes?: string[] | null; // (5/11) carrusel
}

export interface SubidaBanco {
  ok: boolean;
  url: string | null;
  id: number | null;
  modo: string | null;
  aviso: string | null;
}

/** Una fila de `publicaciones` decorada (api/publicar_rutas.decorar). */
export interface Publicacion {
  version?: string | null; // (5/11) resultado.guardado_en: se manda al guardar para avisar si otra persona guardó antes
  id: string;
  creado: string;
  usuario?: string;
  canal: string;
  modo: string | null;
  titulo: string | null;
  texto: string | null;
  imagen_url: string | null;
  estado: string;
  fecha_programada: string | null;
  procesado_en?: string | null;
  resultado: Record<string, unknown> | null;
  // derivados
  estado_texto: string;
  canal_texto: string;
  video_url: string | null;
  imagenes?: string[] | null; // (5/11, Franco) carrusel: 2 a 10 fotos en orden (imagen_url es la portada)
  texto_imagen: string | null;
  formato: string | null;
  nota: string | null;
  propuesta_por: string | null;
  aprobada_por: string | null;
  aprobada_en: string | null;
  rechazada_por: string | null;
  rechazada_en: string | null;
  corregible?: boolean; // (4/11) rechazada que se puede corregir en el mismo lugar y volver a mandar a aprobación (también newsletter)
  corregida_por?: string | null; // (4/11) quién la corrigió después del rechazo
  cancelada_por: string | null;
  plantilla: string | null;
  ver_url: string | null;
  link_editar: string | null;
  error_texto: string | null;
  eliminable: boolean;
  compartido?: boolean; // (2/11) compartida con el equipo
  propio?: boolean; // false en «Del equipo»
  puede_compartir?: boolean;
  retomable: boolean;
  // solo en /aprobacion/para-aprobar
  fecha_sugerida?: string;
  hora_sugerida?: string;
  // solo en /publicaciones/{id}
  pieza?: PiezaGuardada;
  propia?: boolean; // (4/11) false si es de otra persona (llegó por un proyecto compartido o por «Del equipo»)
  permiso?: "dueño" | "editar" | "ver"; // (4/11) con «editar» se retoma la misma pieza (edición en colaboración)
  editada_por?: string | null; // (4/11) quién la guardó por última vez, si no fue la dueña
}

export interface MisPublicaciones {
  piezas: Publicacion[];
  grupos: Record<string, string[]>;
  solapas: Record<string, string[]>;
  eliminables: string[];
}

export interface ParaAprobar {
  piezas: Publicacion[];
  modos: Record<string, string>;
}

export interface ConversacionBorrada {
  id: string;
  usuario: string;
  titulo: string | null;
  actualizado: string | null;
  borrada: string;
}

// (5/11, Franco) Instagram se diseña como tres cosas distintas: Posteo, Reel e Historia. «tipo» NO es un campo de la pieza: se deduce de
// lo que ya existe (el formato y si hay video). Un solo lugar para eso, usado por Diseñar, Mis publicaciones, Aprobación y la pieza.
export type TipoInstagram = "posteo" | "reel" | "historia";
export const TIPOS_INSTAGRAM: TipoInstagram[] = ["posteo", "reel", "historia"];
export const NOMBRE_TIPO_INSTAGRAM: Record<TipoInstagram, string> = { posteo: "Posteo", reel: "Reel", historia: "Historia" };

/** ¿Es un tipo válido (por ejemplo el `?tipo=` de la URL)? */
export function tipoInstagramValido(t: string | null | undefined): TipoInstagram | null {
  return TIPOS_INSTAGRAM.find((x) => x === t) ?? null;
}

/** El tipo de una pieza de Instagram, o null si no es de Instagram. Sirve para el formulario (formato + vfmt + video_url) y para una
 *  fila guardada (formato 'reel' | 'historia' | cuadrado | vertical, y video_url): historia = formato historia (con foto o con video);
 *  si no, con video es reel; si no, posteo. */
export function tipoInstagram(p: { canal?: string | null; formato?: string | null; video_url?: string | null; vfmt?: string | null }): TipoInstagram | null {
  if ((p.canal || "").toLowerCase() !== "instagram") return null;
  if (p.video_url) return (p.vfmt || p.formato) === "historia" ? "historia" : "reel";
  if (p.formato === "historia") return "historia";
  if (p.formato === "reel") return "reel";
  return "posteo";
}

/** «Instagram · Reel» para una pieza de Instagram; el nombre del canal para las demás. */
export function etiquetaCanal(p: { canal?: string | null; canal_texto?: string | null; formato?: string | null; video_url?: string | null }): string {
  const t = tipoInstagram(p);
  return t ? `${p.canal_texto || "Instagram"} · ${NOMBRE_TIPO_INSTAGRAM[t]}` : p.canal_texto || p.canal || "";
}
