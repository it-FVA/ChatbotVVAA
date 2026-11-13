// Lo que devuelve la API para el chat (api/main.py: /conversaciones…; api/chat.py: tarjetas; api/chat_rutas.py).

export interface ConversacionResumen {
  id: string;
  titulo: string | null;
  actualizado: string;
}

export interface EstadoRecorte {
  id: string;
  estado: "pedido" | "listo" | "error";
  url: string | null;
  error: string | null;
}

/** Una fuente (api/chat.tarjetas): lo que hoy dibuja app.render_mats. */
export interface Tarjeta {
  tag: string | null;
  titulo: string | null;
  texto: string | null;
  autor: string | null;
  fuente: string | null; // 'youtube' | 'libro' | 'web' | …
  url: string | null;
  doc: string | null; // id del video en YouTube
  score?: number | null;
  inicio_ms: number | null;
  fin_ms: number | null;
  pagina: number | null;
  ir: string | null; // link al segundo o al párrafo
  citada: boolean;
  traduccion: { titulo?: string; texto?: string } | null;
  procedencia?: string | null; // directa | coautoria | cita | mixta | tercero | sin-autor
  autor_real?: string | null;
  nota?: string | null;
  recortes?: { horizontal: EstadoRecorte | null; vertical: EstadoRecorte | null };
}

/** La pieza que propone el bot (nucleo proponer_publicacion). */
export interface Pieza {
  canal: string; // wordpress | instagram | facebook | youtube | newsletter | ''
  fecha: string;
  hora: string;
  titulo: string;
  texto: string;
  texto_imagen: string;
  firma: string;
  imagen_busqueda: string;
}

/** (8/11, Beto) La campaña que guardó el chat con proponer_campana (api/campana.py): el Proyecto y un borrador por pieza. */
export interface PiezaDeCampana {
  id: string;
  canal: string;
  canal_texto: string;
  titulo: string;
  formato: string; // historia | cuadrado | reel | carrusel | ''
  fuente: string;
  porque: string;
  url_editar: string; // /publicar?borrador=<id> (o /newsletter?borrador=<id>)
}

export interface Campana {
  proyecto_id: string;
  nombre: string;
  piezas: PiezaDeCampana[];
}

export interface MensajeChat {
  role: "user" | "assistant";
  content: string;
  tarjetas?: Tarjeta[];
  pieza?: Pieza | null;
  campana?: Campana | null;
  /** Solo mientras el bot escribe: estado que se muestra arriba de la respuesta. */
  estado?: string | null;
  /** Hubo un error al generar (la respuesta quedó incompleta). */
  error?: string | null;
}

export interface Conversacion {
  id: string;
  titulo: string | null;
  mensajes: MensajeChat[];
  /** (22/10) Si no es mía: quién la compartió y con qué permiso (api/proyectos.conversacion_accesible). */
  compartida?: { por: string; permiso: "ver" | "editar" } | null;
}

export interface FinChat {
  conversacion_id: string | null;
  titulo: string | null;
  texto: string;
  pieza: Pieza | null;
  campana?: Campana | null;
  tarjetas: Tarjeta[];
}

export interface Clip {
  id: string;
  video_id: string;
  inicio_ms: number;
  fin_ms: number;
  formato: "horizontal" | "vertical";
  estado: "pedido" | "listo" | "error";
  url: string | null;
  error: string | null;
}

export interface RespuestaPedido {
  ok: boolean;
  ya: boolean;
  id: string | null;
  estado: "pedido" | "listo" | "error";
  url: string | null;
  mensaje: string;
}

export interface FotoBanco {
  id: number;
  url: string;
  miniatura: string;
  titulo: string;
  /** (5/11) «banco» = de lo que subió el banco de Drive (Configuración → Banco de imágenes, «buscar solo en el banco»); «biblioteca» = de toda la biblioteca de WordPress. */
  fuente?: "banco" | "biblioteca";
}

export interface ModoCanal {
  nombre: string;
  texto_canal: string;
  modo: string; // el modo REAL del canal
  modo_visto: string; // el que ve esta persona
  texto: string;
  a_aprobar: boolean;
  acepta_aprobacion: boolean;
}

export interface Modos {
  canales: Record<string, ModoCanal>;
  publica: boolean;
  aprobadores: string[];
  todos: import("./tipos").CanalInfo[]; // (3/11) el registro completo (canales.py)
}

export interface PiezaEnviada {
  canal: string;
  titulo: string;
  texto: string;
  imagen_url: string | null;
  fecha: string | null;
  hora: string | null;
  texto_imagen: string | null;
  firma: string | null;
  imagen_busqueda: string | null;
}

export interface RespuestaPieza {
  ok: boolean;
  id: string;
  estado: "borrador" | "a_aprobar";
  mensaje: string;
}
