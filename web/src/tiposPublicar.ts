// Lo que devuelve la API para Publicar, Mis publicaciones y Aprobación (api/publicar_rutas.py y GET /publicaciones de api/main.py).
import type { components } from "./tiposApi";

/** (3/11) Un canal de Diseñar tal como lo arma la API (chat_rutas.info_canales, del registro canales.py). */
export interface CanalOpcion {
  nombre: string; // WordPress, Instagram…
  texto_canal: string; // Blogpost, Instagram… (nombre visible)
  detalle: string; // la línea de la tarjeta
  modo_real: string; // apagado | simulado | borrador | privado | real
  modo: string; // el que ve esta persona (quien no publica en real ve todo simulado)
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
export type PiezaApi = components["schemas"]["Pieza"];
export type PiezaGuardada = Partial<PiezaApi>;

export interface RespuestaBorrador {
  ok: boolean;
  id: string;
  estado: "borrador";
  mensaje: string;
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
  texto_imagen: string | null;
  formato: string | null;
  nota: string | null;
  propuesta_por: string | null;
  aprobada_por: string | null;
  aprobada_en: string | null;
  rechazada_por: string | null;
  rechazada_en: string | null;
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
