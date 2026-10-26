// Cliente y tipos de la Administración (22/10): api/admin_rutas.py y api/salud.py. Vive acá (y no en src/api.ts) para no
// pisar a las otras pantallas que se construyen en paralelo; usa la misma cookie de sesión y el mismo manejo de errores.
import { BASE, ErrorApi } from "../../api";

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + ruta, { credentials: "include", headers: { "Content-Type": "application/json", ...(init.headers || {}) }, ...init });
  if (!r.ok) {
    let detalle = r.statusText;
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

export type Estado = "ok" | "aviso" | "error" | "sin_dato" | "arranque" | string;

export interface Periodo {
  tipo: "dias" | "mes";
  dias: number;
  mes?: string;
  desde: string;
  hasta: string | null;
  texto: string;
}

export interface SaludResumen {
  estado: Estado;
  creado?: string;
  hace_min?: number | null;
  chequeos?: number;
  errores?: number;
  avisos?: number;
  mal?: { nombre: string; estado: Estado; detalle: string }[];
  capacidad_mal?: { nombre: string; estado: Estado; porcentaje: number | null }[];
  arranques_24h?: number;
  detalle?: string;
}

export interface CostoResumen {
  mes: string;
  mes_texto: string;
  openai_usd: number;
  openai_llamadas: number;
  openai_por_persona: Record<string, number>;
  proyeccion_30_dias_usd: number;
  dia_del_mes: number;
  presupuesto_usd: number | null;
  total_usd: number;
  anterior: { mes: string; mes_texto: string; openai_usd: number; openai_llamadas: number; total_usd: number };
  modelos_sin_precio: string[];
  servicios_activos: number;
  servicios_total: number;
  fijo_usd: number;
  fijo_confirmado_usd: number;
  sin_confirmar: string[];
  sin_monto: string[];
  con_costo: { nombre: string; usd: number; confirmado: boolean }[];
  nota: string;
}

export interface Resumen {
  salud: SaludResumen;
  costo: CostoResumen | null;
  registro_desde: string;
  sin_supabase?: boolean;
}

export interface PersonaUso {
  usuario: string;
  nombre: string | null;
  rol: string | null;
  activo: boolean;
  ultimo_login: string | null;
  en_tabla: boolean;
  ultima_vez: string | null;
  conversaciones: number;
  mensajes: number;
  piezas: number;
  recortes: number;
  costo_usd: number;
  parte_costo: number;
  llamadas: number;
  lo_ultimo: { tipo: string; texto: string; cuando: string | null } | null;
}

export interface Uso {
  periodo: Periodo;
  resumen: { personas_activas: number; personas_total: number; conversaciones: number; mensajes?: number; piezas: number; recortes: number; costo_usd?: number };
  personas: PersonaUso[];
  sin_actividad: string[];
  por_semana: { semana: string; por_persona: Record<string, number>; total: number }[];
  ultimas: {
    conversaciones: { usuario: string; titulo: string; cuando: string | null; mensajes: number; id: string }[];
    piezas: { usuario: string; canal: string; titulo: string; estado: string; cuando: string | null }[];
    recortes: { usuario: string; formato: string; titulo: string; estado: string; cuando: string | null; id: string }[];
  };
  nota?: string;
  sin_supabase?: boolean;
}

export interface PersonaCosto {
  usuario: string;
  llamadas: number;
  chats: number;
  tokens_entrada: number;
  tokens_salida: number;
  tokens_cache: number;
  usd: number;
  parte: number;
  usd_por_chat: number | null;
}

export interface Precio {
  entrada: number;
  salida: number;
  cache?: number;
  fuente?: string;
  fecha?: string;
  nota?: string;
}

export interface Costos {
  periodo: Periodo;
  registro_desde: string;
  total_usd: number;
  llamadas: number;
  personas: number;
  tokens: { entrada: number; salida: number; cache: number };
  promedio_dia_con_uso_usd: number | null;
  por_persona: PersonaCosto[];
  por_dia: { dia: string; por_persona: Record<string, number>; usd: number }[];
  por_modelo: { modelo: string; que: string; que_texto: string; llamadas: number; tokens_entrada: number; tokens_salida: number; tokens_cache: number; usd: number; con_precio: boolean }[];
  modelos_sin_precio: string[];
  meses: { mes: string; texto: string; usd: number; tokens: number; llamadas: number; personas: number; por_persona: Record<string, number>; quien_mas: { usuario: string; usd: number } | null }[];
  precios: Record<string, Precio>;
  avisos_precios: Record<string, string>;
  nota: string;
  sin_supabase?: boolean;
}

export interface Chequeo {
  nombre: string;
  estado: Estado;
  detalle: string;
  que_hacer: string | null;
  desde?: string;
  vence?: string | null;
  ms?: number;
  cacheado?: boolean;
  url?: string;
  corrida?: { url?: string; cuando?: string; conclusion?: string; status?: string } | null;
  [k: string]: unknown;
}

export interface Capacidad {
  nombre: string;
  proveedor: string;
  plan: string | null;
  costo_mensual_usd: number | null;
  costo_confirmado: boolean;
  metrica: string;
  uso: number | null;
  limite: number | null;
  unidad: string;
  porcentaje: number | null;
  umbral: number;
  estado: Estado;
  justificacion: string;
  fuente_limite: string | null;
  referencia: boolean;
  medido: boolean;
  desde?: string;
  nota?: string;
  uso_manual?: { gb: number; fecha?: string; por?: string } | null;
  tablas?: Record<string, { filas: number | null; mb: number }>;
  arranques_24h?: number | null;
  arranques_7d?: number | null;
  proyeccion_30_dias_usd?: number;
  modelos_sin_precio?: string[];
  tokens?: { entrada: number; salida: number; cache: number; llamadas: number };
  [k: string]: unknown;
}

export interface InformeSalud {
  creado: string;
  estado: Estado;
  chequeos: Chequeo[];
  capacidad: Capacidad[];
  ms: number;
  historial_aviso?: string;
}

export interface FilaHistorial {
  id: number;
  creado: string;
  estado: Estado;
  detalle: { chequeos?: { nombre: string; estado: Estado; detalle?: string }[]; capacidad?: { nombre: string; estado: Estado }[]; ms?: number; version?: string } | null;
}

export interface Servicio {
  id?: string;
  nombre: string;
  proveedor: string | null;
  para_que: string | null;
  plan: string | null;
  costo_mensual_usd: number | null;
  confirmado: boolean;
  desde: string | null;
  url: string | null;
  notas: string | null;
  activo: boolean;
  actualizado_por?: string | null;
  actualizado?: string | null;
}

export interface Servicios {
  servicios: Servicio[];
  servicios_activos: number;
  servicios_total: number;
  fijo_usd: number;
  fijo_confirmado_usd: number;
  sin_confirmar: string[];
  sin_monto: string[];
  con_costo: { nombre: string; usd: number; confirmado: boolean }[];
  mes: string;
  mes_texto: string;
  openai_mes_usd: number;
  total_mes_usd: number;
  sin_supabase?: boolean;
}

export interface ValorConfig {
  valor: unknown;
  actualizado: string | null;
  por: string | null;
}

export interface Config {
  valores: Record<string, ValorConfig>;
  explicaciones: Record<string, string>;
  avisos_precios: Record<string, string>;
  defaults: { frase_hora: string; frase_pie: string; frase_canales: string[]; umbral: number; frase_mail_inicio?: string };
  frase_canales_posibles: Record<string, string>;
  modelos_vistos: string[];
  proveedores_umbral: string[];
}

export interface CambioRegistro {
  id: number;
  cuando: string;
  quien: string;
  accion: string;
  usuario: string | null;
  detalle: Record<string, unknown> | null;
}

const q = (dias?: number, mes?: string) => (mes ? `?mes=${encodeURIComponent(mes)}` : dias ? `?dias=${dias}` : "");

export const adminApi = {
  resumen: () => pedir<Resumen>("/admin/resumen"),
  uso: (dias?: number, mes?: string) => pedir<Uso>("/admin/uso" + q(dias, mes)),
  costos: (dias?: number, mes?: string) => pedir<Costos>("/admin/costos" + q(dias, mes)),
  salud: (guardar = true) => pedir<InformeSalud>("/salud/servicios" + (guardar ? "" : "?guardar=0")),
  historial: (limite = 150) => pedir<FilaHistorial[]>(`/salud/historial?limite=${limite}`),
  capacidad: () => pedir<{ creado: string; capacidad: Capacidad[] }>("/salud/capacidad"),
  servicios: () => pedir<Servicios>("/admin/servicios"),
  guardarServicio: (s: Servicio) => pedir<{ ok: boolean; servicio: Servicio }>("/admin/servicios", { method: "PUT", body: JSON.stringify(s) }),
  borrarServicio: (id: string) => pedir<{ ok: boolean }>(`/admin/servicios/${encodeURIComponent(id)}`, { method: "DELETE" }),
  config: () => pedir<Config>("/admin/config"),
  guardarConfig: (cambios: Record<string, unknown>) => pedir<{ ok: boolean; guardadas: Record<string, unknown> }>("/admin/config", { method: "PUT", body: JSON.stringify({ cambios }) }),
  cambios: (limite = 200) => pedir<CambioRegistro[]>(`/admin/cambios?limite=${limite}`),
};
