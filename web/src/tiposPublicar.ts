// Lo que devuelve la API para Publicar, Mis publicaciones y Aprobación (api/publicar_rutas.py y GET /publicaciones de api/main.py).

export type Canal = "wordpress" | "instagram" | "facebook" | "youtube";

export interface CanalOpcion {
  nombre: string; // WordPress, Instagram…
  texto_canal: string; // Blogpost, Instagram… (nombre visible)
  modo_real: string; // apagado | simulado | borrador | privado | real
  modo: string; // el que ve esta persona (quien no publica en real ve todo simulado)
  texto: string;
  a_aprobar: boolean;
  configurado: boolean;
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

/** El estado del formulario de Publicar (= los campos de publicar_ui.formulario). Es también lo que se manda a la API. */
export interface PiezaForm {
  canal: Canal | "";
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

/** El dict `pieza` que guarda Streamlit en un borrador (claves cortas) y que devuelve GET /publicaciones/{id}. */
export interface PiezaGuardada {
  _pid?: string;
  canal?: string | null;
  titulo?: string;
  texto?: string;
  texto_imagen?: string;
  video_url?: string | null;
  video_formato?: string | null;
  vfmt?: string | null;
  url?: string;
  busq?: string;
  imagen_busqueda?: string;
  firma?: string | null;
  fmt?: string | null;
  logo?: string | null;
  plogo?: string | null;
  tipo?: string | null;
  peso?: string | null;
  pos?: string | null;
  ali?: string | null;
  usar_comp?: boolean;
  fecha?: string | null;
  hora?: string | null;
  miniatura?: string | null;
}

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
