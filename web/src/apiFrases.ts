// Cliente de la API para la Frase del día (api/frases_rutas.py). La sesión es la cookie de siempre.
import { BASE, pedir } from "./api";

export interface Frase {
  id: string;
  texto: string;
  autor: string | null;
  fecha: string | null;
  estado: "programada" | "publicada" | "simulada" | "saltada" | string;
  estado_texto: string;
  validada: boolean;
  imagen_url: string | null;
  estilo?: Record<string, string> | null; // (2/11 noche) diseño propio de la frase (pisa el global)
  publicacion_id: string | null;
  fuente: string | null;
  tema: string | null;
  orden: number | null;
  ultima_publicada: string | null;
  veces_publicada: number;
  repetida: boolean; // ya salió antes (rotación)
  cerrada: boolean; // en la cola o ya salió: no se mueve ni se edita
}

/** (2/11 tarde) Una fila de la tarjeta «Mañana»: el canal, si está prendido, su modo y la pieza de mañana si existe. */
export interface CanalManana {
  canal: string;
  nombre: string;
  prendido: boolean;
  modo: string;
  pieza: { id: string; estado: string; fecha_programada: string } | null;
}

export interface Resumen {
  disponible: boolean;
  admin: boolean;
  aprueba?: boolean; // (2/11) false = creador de contenido: ve el calendario y pide cambios
  solicitudes_pendientes?: number;
  conteos: { total?: number; validadas?: number; con_fecha?: number; publicadas?: number; sin_fecha_validadas?: number; pendientes_validar?: number; programadas?: number };
  activa: boolean;
  hoy?: string;
  hora?: string;
  canales?: string[];
  canales_posibles?: Record<string, string>; // (2/11) clave → nombre, para el checklist de la cabecera
  estilo_opciones?: { logos: string[]; posiciones_logo: string[]; tipografias: string[]; pesos: string[]; posiciones: string[]; alineaciones: string[] };
  estilo_global?: Record<string, string | null>; // el de Configuración → Estilo, ya con los defaults
  foto_defecto?: string | null;
  frases_nuevas_hasta?: string | null;
  nuevas_sin_dia?: number;
  manana?: { fecha: string; fecha_texto: string; dia?: string; frase: Frase | null; en_cola: boolean; canales?: CanalManana[] };
  avisos: string[];
}

export interface Proxima {
  fecha: string;
  dia: string;
  frase: Frase | null;
}
export interface Backlog {
  sin_dia: Frase[];
  sin_dia_total: number;
  pendientes: Frase[];
  pendientes_total: number;
}
export interface Mes {
  anio: number;
  mes: number;
  dias: number;
  hoy: string;
  primer_dia_semana: number; // 0 = lunes
  frases: Record<string, Frase>;
}
export interface Dia {
  fecha: string;
  fecha_texto: string;
  dia: string;
  pasado: boolean;
  frase: Frase | null;
  cola: { estado: string; fecha_programada: string | null; permalink: string | null } | null;
  foto: { url: string | null; de_donde: string } | null;
}
/** (26/10) El canal mail por Perfit: GET /frases/mail/estado. */
export interface MailEstado {
  modo: "apagado" | "simulado" | "real";
  faltan: string[];
  lista: { id: number; nombre: string; activos: number | null; total: number | null } | null;
  error: string | null;
  canal_prendido: boolean;
  inicio: string;
  hora?: string; // (3/11) la hora de las redes: si el mail arranca antes, arranca de madrugada ese mismo día
  lista_prueba: string[];
  trigger_key: string;
  limite_por_hora: number;
  envios: Record<string, { fecha_texto: string; frase: Frase | null; pieza: string | null; estado: string | null; arranca: string | null; conteo: { pendiente?: number; enviado?: number; error?: number; total?: number } | null }>;
  pruebas: { id: string; fecha: string; email: string; estado: string; enviado_en: string | null; error: string | null; creado: string }[];
  contexto_plantilla: string[];
}
export interface MailPrueba {
  ok: boolean;
  modo: string;
  aviso: string;
  imagen_de?: string;
  contexto?: Record<string, string>;
  resultados: { email: string; ok: boolean; aviso: string }[];
}
/** (2/11) Un pedido de cambio del calendario (GET /frases/solicitudes). */
export interface Solicitud {
  id: string;
  creado: string;
  usuario: string;
  fecha: string;
  fecha_texto: string;
  frase: Frase | null; // la frase pedida, si ya existe
  texto: string | null; // o una nueva
  autor: string | null;
  nota: string | null;
  imagen_url: string | null; // (2/11 tarde) foto de fondo propuesta
  solo_foto: boolean; // sin frase: cambiar solo la foto de la que ya está ese día
  estado: "pendiente" | "aceptada" | "rechazada" | "retirada" | string;
  resuelta_por: string | null;
  resuelta_en: string | null;
  respuesta: string | null;
  actual: Frase | null; // la que hoy ocupa ese día
  pasado: boolean;
}
export interface Solicitudes {
  aprueba: boolean;
  pendientes: Solicitud[];
  resueltas: Solicitud[];
}
/** (2/11 tarde) Prototipo: el mensaje al grupo de WhatsApp tal cual saldría (GET /frases/whatsapp/previa/{fecha}). */
export interface WhatsappPrevia {
  fecha: string;
  fecha_texto: string;
  texto: string;
  imagen: string;
  imagen_de: string;
  grupo: string;
  modo: string;
  canal_prendido: boolean;
  frase: Frase | null;
  pieza: { id: string; estado: string; fecha_programada: string } | null;
  aviso: string;
}
/** (2/11) El mail de un día armado con la plantilla local (GET /frases/mail/previa/{fecha}). */
export interface MailPrevia {
  fecha: string;
  fecha_texto: string;
  html: string;
  contexto: Record<string, string>;
  imagen_de: string;
  asunto: string;
  frase: Frase | null;
  aviso: string;
}
export interface RespuestaFrase {
  ok: boolean;
  frase: Frase;
  mensaje?: string;
}

export const apiFrases = {
  resumen: () => pedir<Resumen>("/frases/resumen"),
  proximas: (dias = 14) => pedir<Proxima[]>(`/frases/proximas?dias=${dias}`),
  backlog: (q = "") => pedir<Backlog>("/frases/backlog?q=" + encodeURIComponent(q)),
  mes: (anio: number, mes: number) => pedir<Mes>(`/frases/mes/${anio}/${mes}`),
  dia: (fecha: string) => pedir<Dia>(`/frases/dia/${fecha}`),
  /** La imagen compuesta; con `foto` la arma con esa otra foto sin guardarla (2/11 tarde). */
  previaUrl: (id: string, v: string | number = "", foto?: string | null) =>
    `${BASE}/frases/${encodeURIComponent(id)}/previa.jpg?v=${encodeURIComponent(String(v))}` + (foto ? `&foto=${encodeURIComponent(foto)}` : ""),
  crear: (texto: string, autor: string) => pedir<{ ok: boolean; id: string; frase: Frase }>("/frases", { method: "POST", body: JSON.stringify({ texto, autor }) }),
  editar: (id: string, datos: { texto?: string; autor?: string; imagen_url?: string; quitar_imagen?: boolean; estado?: string; estilo?: Record<string, string>; quitar_estilo?: boolean }) =>
    pedir<RespuestaFrase>(`/frases/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(datos) }),
  mover: (id: string, fecha: string) => pedir<RespuestaFrase>(`/frases/${encodeURIComponent(id)}/mover`, { method: "POST", body: JSON.stringify({ fecha }) }),
  sacar: (id: string) => pedir<RespuestaFrase>(`/frases/${encodeURIComponent(id)}/sacar`, { method: "POST" }),
  intercambiar: (id_a: string, id_b: string) => pedir<{ ok: boolean; a: Frase; b: Frase; mensaje: string }>("/frases/intercambiar", { method: "POST", body: JSON.stringify({ id_a, id_b }) }),
  repartir: (modo: "orden" | "azar", desde: string) => pedir<{ ok: boolean; cantidad: number; desde: string; hasta: string; mensaje: string }>("/frases/repartir", { method: "POST", body: JSON.stringify({ modo, desde }) }),
  vaciar: () => pedir<{ ok: boolean; cantidad: number; mensaje: string }>("/frases/vaciar", { method: "POST", body: JSON.stringify({ confirmo: true }) }),
  mananaEncolar: () => pedir<{ ok: boolean; canales: string[]; mensaje: string }>("/frases/manana/encolar", { method: "POST" }),
  mananaFrenar: () => pedir<{ ok: boolean; canceladas: number; mensaje: string }>("/frases/manana/frenar", { method: "POST" }),
  canales: (canales: string[]) => pedir<{ ok: boolean; canales: string[]; mensaje: string }>("/frases/canales", { method: "PUT", body: JSON.stringify({ canales }) }),
  activa: (activa: boolean) => pedir<{ ok: boolean; activa: boolean; mensaje: string }>("/frases/activa", { method: "PUT", body: JSON.stringify({ activa }) }),
  mailEstado: () => pedir<MailEstado>("/frases/mail/estado"),
  mailPrueba: (fecha?: string, emails?: string[]) => pedir<MailPrueba>("/frases/mail/prueba", { method: "POST", body: JSON.stringify({ fecha, emails }) }),
  whatsappPrevia: (fecha: string) => pedir<WhatsappPrevia>(`/frases/whatsapp/previa/${encodeURIComponent(fecha)}`),
  mailPrevia: (fecha: string) => pedir<MailPrevia>(`/frases/mail/previa/${fecha}`),
  solicitudes: () => pedir<Solicitudes>("/frases/solicitudes"),
  solicitar: (datos: { fecha: string; frase_id?: string | null; texto?: string | null; autor?: string | null; nota?: string | null; imagen_url?: string | null }) =>
    pedir<{ ok: boolean; id: string; solicitud: Solicitud; mensaje: string }>("/frases/solicitudes", { method: "POST", body: JSON.stringify(datos) }),
  aceptarSolicitud: (id: string, respuesta?: string) => pedir<{ ok: boolean; solicitud: Solicitud; mensaje: string }>(`/frases/solicitudes/${encodeURIComponent(id)}/aceptar`, { method: "POST", body: JSON.stringify({ respuesta }) }),
  rechazarSolicitud: (id: string, respuesta?: string) => pedir<{ ok: boolean; solicitud: Solicitud; mensaje: string }>(`/frases/solicitudes/${encodeURIComponent(id)}/rechazar`, { method: "POST", body: JSON.stringify({ respuesta }) }),
  retirarSolicitud: (id: string) => pedir<{ ok: boolean; mensaje: string }>(`/frases/solicitudes/${encodeURIComponent(id)}/retirar`, { method: "POST" }),
};
