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

export interface MensajeChat {
  role: "user" | "assistant";
  content: string;
  tarjetas?: Tarjeta[];
  pieza?: Pieza | null;
  /** Solo mientras el bot escribe: estado que se muestra arriba de la respuesta. */
  estado?: string | null;
  /** Hubo un error al generar (la respuesta quedó incompleta). */
  error?: string | null;
}

export interface Conversacion {
  id: string;
  titulo: string | null;
  mensajes: MensajeChat[];
}

export interface FinChat {
  conversacion_id: string | null;
  titulo: string | null;
  texto: string;
  pieza: Pieza | null;
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
}

export interface ModoCanal {
  nombre: string;
  modo: string;
  texto: string;
  a_aprobar: boolean;
}

export interface Modos {
  canales: Record<string, ModoCanal>;
  publica: boolean;
  aprobadores: string[];
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
