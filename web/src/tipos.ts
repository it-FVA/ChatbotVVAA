// Lo que devuelve la API (api/main.py y api/recortes.py).

export interface Rol {
  nombre: string;
  crea: boolean;
  aprueba: boolean;
  admin: boolean; // configuración (estilo por defecto del equipo, etc.); un admin también aprueba
  publica: boolean;
}

export interface Yo {
  usuario: string;
  origen: string;
  idioma: string;
  rol: Rol;
  // (22/10) de la tabla `usuarios`; si la persona sigue solo en secrets, en_tabla = false y nombre/email = null
  nombre: string | null;
  email: string | null;
  en_tabla: boolean;
  tiene_clave: boolean;
  debe_cambiar_clave: boolean; // clave temporal puesta por un admin: hay que cambiarla antes de seguir
}

// (22/10) Administración → Usuarios (api/cuentas.py; nunca viene el hash)
export interface Usuario {
  id: string;
  usuario: string;
  email: string | null;
  nombre: string | null;
  rol: "creador" | "aprobador" | "admin" | string;
  tiene_clave: boolean;
  clave_temporal: boolean;
  activo: boolean;
  creado: string;
  actualizado: string | null;
  ultimo_login: string | null;
  creado_por: string | null;
}

export interface Autorizado {
  email: string;
  rol: string;
  nota: string | null;
  agregado_por: string | null;
  creado: string | null;
}

export interface Cambio {
  id: number;
  cuando: string;
  quien: string;
  accion: string;
  usuario: string | null;
  detalle: Record<string, unknown> | null;
}

export interface Estilo {
  tipografia: string;
  tamano: string;
  color: string;
  fondo: string;
  negrita: boolean;
  posicion: string;
}

export interface Opciones {
  tipografias: string[];
  tamanos: Record<string, number>;
  colores: Record<string, string>;
  fondos: Record<string, { tipo: string; color: string | null; alpha: string }>;
  posiciones: string[];
  estilo_defecto: Estilo;
  estilo_equipo: Estilo | null;
  limites: { min_ms: number; max_ms: number };
}

export interface SinPausas {
  antes: number;
  despues: number;
  pausas: number;
}

export interface Edicion {
  inicio_ms?: number;
  fin_ms?: number;
  srt?: string;
  estilo?: Estilo;
  quitar_pausas?: boolean;
  sin_pausas?: SinPausas;
  segmentos?: number[][];
  segmentos_hechos?: number[][];
  timeline?: number[][];
}

export interface Recorte {
  id: string;
  creado: string;
  video_id: string;
  inicio_ms: number;
  fin_ms: number;
  formato: "horizontal" | "vertical";
  titulo: string | null;
  pedido_por: string | null;
  estado: "pedido" | "listo" | "error";
  url: string | null;
  error: string | null;
  procesado_en: string | null;
  srt: string | null;
  edicion: Edicion | null;
  nota: string | null;
  estilo: Estilo | null;
  // derivados (api/recortes._decorar)
  propio: boolean;
  puede_editar: boolean;
  puede_borrar: boolean;
  regenerando: boolean;
  estado_texto: string;
  miniatura: string | null;
  duracion_ms: number;
  sin_pausas: SinPausas | null;
  segmentos_hechos: number[][] | null;
  timeline: number[][] | null;
}

export interface Linea {
  n?: string;
  inicio: string; // 'HH:MM:SS,mmm' en la timeline del video actual
  fin: string;
  texto: string;
}

export interface Detalle extends Recorte {
  srt_actual: string;
  lineas: Linea[];
  srt_corregido: boolean;
  estilo_actual: Estilo;
  estilo_propio: boolean;
}

export interface Uso {
  id: number;
  usuario?: string;
  canal: string;
  estado: string;
  titulo?: string;
}

export interface RespuestaEdicion {
  ok: boolean;
  edicion: Edicion;
  partes: string[];
  avisos: string[];
  mensaje: string;
}
