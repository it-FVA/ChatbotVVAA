// Cliente de la API para la Frase del día (api/frases_rutas.py). La sesión es la cookie de siempre.
import { BASE, ErrorApi } from "./api";

export interface Frase {
  id: string;
  texto: string;
  autor: string | null;
  fecha: string | null;
  estado: "programada" | "publicada" | "simulada" | "saltada" | string;
  estado_texto: string;
  validada: boolean;
  imagen_url: string | null;
  publicacion_id: string | null;
  fuente: string | null;
  tema: string | null;
  orden: number | null;
  ultima_publicada: string | null;
  veces_publicada: number;
  repetida: boolean; // ya salió antes (rotación)
  cerrada: boolean; // en la cola o ya salió: no se mueve ni se edita
}

export interface Resumen {
  disponible: boolean;
  admin: boolean;
  conteos: { total?: number; validadas?: number; con_fecha?: number; publicadas?: number; sin_fecha_validadas?: number; pendientes_validar?: number; programadas?: number };
  activa: boolean;
  hoy?: string;
  hora?: string;
  canales?: string[];
  foto_defecto?: string | null;
  frases_nuevas_hasta?: string | null;
  nuevas_sin_dia?: number;
  manana?: { fecha: string; fecha_texto: string; frase: Frase | null; en_cola: boolean };
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
export interface RespuestaFrase {
  ok: boolean;
  frase: Frase;
  mensaje?: string;
}

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + ruta, { credentials: "include", headers: { "Content-Type": "application/json", ...(init.headers || {}) }, ...init });
  if (!r.ok) {
    let detalle = r.statusText || `Error ${r.status}`;
    try {
      const j = await r.json();
      detalle = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* sin cuerpo */
    }
    throw new ErrorApi(r.status, detalle);
  }
  return (await r.json()) as T;
}

export const apiFrases = {
  resumen: () => pedir<Resumen>("/frases/resumen"),
  proximas: (dias = 14) => pedir<Proxima[]>(`/frases/proximas?dias=${dias}`),
  backlog: (q = "") => pedir<Backlog>("/frases/backlog?q=" + encodeURIComponent(q)),
  mes: (anio: number, mes: number) => pedir<Mes>(`/frases/mes/${anio}/${mes}`),
  dia: (fecha: string) => pedir<Dia>(`/frases/dia/${fecha}`),
  previaUrl: (id: string, v: string | number = "") => `${BASE}/frases/${encodeURIComponent(id)}/previa.jpg?v=${encodeURIComponent(String(v))}`,
  crear: (texto: string, autor: string) => pedir<{ ok: boolean; id: string; frase: Frase }>("/frases", { method: "POST", body: JSON.stringify({ texto, autor }) }),
  editar: (id: string, datos: { texto?: string; autor?: string; imagen_url?: string; quitar_imagen?: boolean; estado?: string }) =>
    pedir<RespuestaFrase>(`/frases/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(datos) }),
  mover: (id: string, fecha: string) => pedir<RespuestaFrase>(`/frases/${encodeURIComponent(id)}/mover`, { method: "POST", body: JSON.stringify({ fecha }) }),
  sacar: (id: string) => pedir<RespuestaFrase>(`/frases/${encodeURIComponent(id)}/sacar`, { method: "POST" }),
  intercambiar: (id_a: string, id_b: string) => pedir<{ ok: boolean; a: Frase; b: Frase; mensaje: string }>("/frases/intercambiar", { method: "POST", body: JSON.stringify({ id_a, id_b }) }),
  repartir: (modo: "orden" | "azar", desde: string) => pedir<{ ok: boolean; cantidad: number; desde: string; hasta: string; mensaje: string }>("/frases/repartir", { method: "POST", body: JSON.stringify({ modo, desde }) }),
  vaciar: () => pedir<{ ok: boolean; cantidad: number; mensaje: string }>("/frases/vaciar", { method: "POST", body: JSON.stringify({ confirmo: true }) }),
  activa: (activa: boolean) => pedir<{ ok: boolean; activa: boolean; mensaje: string }>("/frases/activa", { method: "PUT", body: JSON.stringify({ activa }) }),
  mailEstado: () => pedir<MailEstado>("/frases/mail/estado"),
  mailPrueba: (fecha?: string, emails?: string[]) => pedir<MailPrueba>("/frases/mail/prueba", { method: "POST", body: JSON.stringify({ fecha, emails }) }),
};
