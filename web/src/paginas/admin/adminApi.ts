// Cliente y tipos de la Administración (22/10): api/admin_rutas.py y api/salud.py. Vive acá (y no en src/api.ts) para no
// pisar a las otras pantallas que se construyen en paralelo; usa la misma cookie de sesión y el mismo manejo de errores.
// (3/11, revisión 5.3 punto 17) el cliente HTTP es el de src/api.ts; acá quedan los tipos y las llamadas de una línea.
import { pedir } from "../../api";

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

/** (5/11) GET /admin/banco: el banco de imágenes (lo que subió la cola desde Drive). */
export interface EstadoBanco {
  total: number;
  por_formato: Record<string, number>;
  ultima_sincronizacion: string | null;
  carpeta_configurada: boolean;
  solo_banco: boolean;
}
export interface ResumenSincronizacion {
  subidas: number;
  salteadas: number;
  errores: number;
  pendientes: number;
  simuladas: number;
  detalle: string[];
}

export interface CambioRegistro {
  id: number;
  cuando: string;
  quien: string;
  accion: string;
  usuario: string | null;
  detalle: Record<string, unknown> | null;
}

// (8/11, Franco) Métricas: contrato en web/maquetas/metricas-contrato.md. (8/11) provisionales: cuando la API esté mergeada se reemplazan por `components["schemas"]` de tiposApi.d.ts
export type GrupoEstado = "publicada" | "programada" | "en_aprobacion" | "borrador" | "prueba" | "no_salio";
export type PorGrupo = Record<GrupoEstado, number>;
export type DatosMetricas = Partial<Record<string, number>> & { crudo?: Record<string, unknown>; errores?: string[] };

export interface PiezaCampana {
  id: string;
  canal: string;
  canal_texto: string;
  titulo: string;
  estado: string;
  estado_grupo: GrupoEstado;
  fecha: string;
  ver_url: string | null;
  formato: "historia" | "cuadrado" | "reel" | "carrusel" | null;
  usuario: string;
  modo: string;
  metricas?: (Partial<Record<string, number>> & { fuente?: "api" | "manual"; capturado?: string }) | null;
}

export interface Campana {
  id: string;
  nombre: string;
  emoji: string | null;
  color: string | null;
  dueno: string | null;
  creado: string | null;
  piezas_total: number;
  por_canal: Record<string, PorGrupo>;
  por_estado: PorGrupo;
  primera: string | null;
  ultima: string | null;
  piezas: PiezaCampana[];
}

export interface Campanas {
  periodo: Periodo;
  campanas: Campana[];
  sueltas: Campana;
  totales: { piezas: number; por_canal: Record<string, number> } & PorGrupo;
}

export interface CanalMetricas {
  clave: string;
  texto: string;
  icono: string;
  modo: string;
  configurado: boolean;
  api: "disponible" | "sin_permiso" | "no_hay" | "pendiente" | "error";
  nota_api: string | null;
  enlace: string | null;
  enlace_texto: string | null;
  ultima: { datos: DatosMetricas; periodo_desde: string | null; periodo_hasta: string | null; capturado: string; fuente: string } | null;
  manual: { datos: DatosMetricas; periodo_desde: string | null; periodo_hasta: string | null; capturado: string; nota: string | null; por: string | null } | null;
}

export interface CanalesMetricas {
  actualizado: string | null;
  canales: CanalMetricas[];
}

export interface ResultadoActualizar {
  capturado: string;
  instagram: { ok: boolean; piezas: number; error: string | null };
  facebook: { ok: boolean; piezas: number; error: string | null };
  youtube: { ok: boolean; piezas: number; error: string | null };
}

export interface MetricaManual {
  ambito: "canal" | "pieza";
  ref: string;
  canal: string;
  periodo_desde: string | null;
  periodo_hasta: string | null;
  datos: Record<string, number>;
  nota: string | null;
}

// (8/11, Franco) asesor de campañas (sección «Agregado del 8/11» del contrato)
export interface Apertura {
  texto: string;
  fuentes: string[];
  falto: string[];
  capturado: string;
  nuevo: boolean;
}
export interface MensajeAsesor {
  rol: "usuario" | "asesor";
  texto: string;
}
export interface RespuestaAsesor {
  texto: string;
  fuentes: string[];
  falto: string[];
}

export interface ResumenCampana {
  ref: string;
  nombre: string;
  texto: string;
  fuentes: string[];
  falto: string[];
  comparado_con: string | null;
  modelo: string;
  capturado: string;
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
  banco: () => pedir<EstadoBanco>("/admin/banco"),
  sincronizarBanco: () => pedir<ResumenSincronizacion>("/admin/banco/sincronizar", { method: "POST" }),
  config: () => pedir<Config>("/admin/config"),
  guardarConfig: (cambios: Record<string, unknown>) => pedir<{ ok: boolean; guardadas: Record<string, unknown> }>("/admin/config", { method: "PUT", body: JSON.stringify({ cambios }) }),
  campanas: (dias?: number, mes?: string) => pedir<Campanas>("/admin/metricas/campanas" + q(dias, mes)),
  canalesMetricas: () => pedir<CanalesMetricas>("/admin/metricas/canales"),
  actualizarMetricas: () => pedir<ResultadoActualizar>("/admin/metricas/actualizar", { method: "POST" }),
  anotarMetrica: (body: MetricaManual) => pedir<{ id: string }>("/admin/metricas/manual", { method: "PUT", body: JSON.stringify(body) }),
  asesorApertura: (dias: number) => pedir<Apertura>(`/admin/metricas/asesor/apertura?dias=${dias}`),
  preguntarAsesor: (mensajes: MensajeAsesor[], dias: number) => pedir<RespuestaAsesor>("/admin/metricas/asesor", { method: "POST", body: JSON.stringify({ mensajes: mensajes.slice(-12), dias }) }),
  resumenGuardado: (ref: string) => pedir<ResumenCampana | null>(`/admin/metricas/resumen/${encodeURIComponent(ref)}`),
  resumir: (ref: string, dias: number) => pedir<ResumenCampana>("/admin/metricas/resumen", { method: "POST", body: JSON.stringify({ ref, dias }) }),
  cambios: (limite = 200) => pedir<CambioRegistro[]>(`/admin/cambios?limite=${limite}`),
};
