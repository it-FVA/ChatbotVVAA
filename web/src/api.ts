// Cliente de la API. La sesión es una cookie HttpOnly que pone POST /login: el navegador la manda solo
// (credentials: "include" por si la API está en otro dominio en producción).
import type { Autorizado, Cambio, Detalle, Opciones, Recorte, RespuestaEdicion, Uso, Usuario, Yo, Estilo } from "./tipos";

export const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

export class ErrorApi extends Error {
  status: number;
  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
}

/** El error que la API devolvió en el cuerpo ({detail}), o el texto del estado HTTP si no hay cuerpo. */
export async function errorDe(r: Response): Promise<ErrorApi> {
  let detalle = r.statusText || `Error ${r.status}`;
  try {
    const j = await r.json();
    detalle = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
  } catch {
    /* sin cuerpo */
  }
  return new ErrorApi(r.status, detalle);
}

// ---------- ¿la API está despierta? (Render plan free se duerme a los 15 min; arrancar tarda ~1 min) ----------
let ultimaVezViva = 0;
const DORMIDA_TRAS_MS = 10 * 60 * 1000;
/** Cada respuesta que llega anota que la API está despierta; lo usa esperarApi (apiChat) antes de un mensaje largo. */
export function marcarViva() {
  ultimaVezViva = Date.now();
}
export function haceRatoSinApi() {
  return Date.now() - ultimaVezViva >= DORMIDA_TRAS_MS;
}

/** El fetch con la cookie de sesión; lanza ErrorApi si la respuesta no es 2xx. Devuelve la Response cruda para los casos que
 *  no son JSON (un blob, un multipart, un streaming). Para JSON usar pedir(). */
export async function pedirCrudo(ruta: string, init: RequestInit = {}): Promise<Response> {
  const r = await fetch(BASE + ruta, { credentials: "include", ...init });
  if (!r.ok) throw await errorDe(r);
  marcarViva();
  return r;
}

/** (3/11) El único cliente JSON de la web: todos los api*.ts (y adminApi.ts) son llamadas de una línea sobre esta función. */
export async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const r = await pedirCrudo(ruta, { ...init, headers: { "Content-Type": "application/json", ...(init.headers || {}) } });
  return (await r.json()) as T;
}

export const api = {
  salud: () => pedir<{ ok: boolean; supabase: boolean; login_google: boolean; google_client_id: string | null }>("/salud"),
  loginGoogle: (id_token: string) => pedir<Yo>("/login/google", { method: "POST", body: JSON.stringify({ id_token }) }),
  yo: () => pedir<Yo>("/yo"),
  login: (usuario: string, clave: string) => pedir<Yo>("/login", { method: "POST", body: JSON.stringify({ usuario, clave }) }),
  logout: () => pedir<{ ok: boolean }>("/logout", { method: "POST" }),

  // (22/10) cuentas: «primera vez», mi contraseña, administración (api/cuentas.py)
  verificarEmail: (email: string) =>
    pedir<{ permitido: boolean; motivo: string; usuario: string | null; sin_clave: boolean; mensaje: string | null }>("/cuentas/verificar", { method: "POST", body: JSON.stringify({ email }) }),
  primeraVez: (email: string, usuario: string, clave: string) => pedir<Yo>("/cuentas/primera-vez", { method: "POST", body: JSON.stringify({ email, usuario, clave }) }),
  cambiarClave: (actual: string, nueva: string) => pedir<{ ok: boolean }>("/cuentas/clave", { method: "POST", body: JSON.stringify({ actual, nueva }) }),
  adminUsuarios: () => pedir<{ usuarios: Usuario[] }>("/admin/usuarios"),
  adminCrear: (datos: { usuario: string; email: string | null; nombre: string | null; rol: string; clave: "sin" | "temporal" }) =>
    pedir<{ usuario: Usuario; clave_temporal: string | null }>("/admin/usuarios", { method: "POST", body: JSON.stringify(datos) }),
  adminEditar: (id: string, datos: { nombre?: string; email?: string; rol?: string; activo?: boolean }) =>
    pedir<{ usuario: Usuario }>(`/admin/usuarios/${id}`, { method: "PATCH", body: JSON.stringify(datos) }),
  adminRenombrar: (id: string, usuario: string) =>
    pedir<{ usuario: Usuario; tablas: Record<string, number | string>; sesion_propia?: boolean }>(`/admin/usuarios/${id}/renombrar`, { method: "POST", body: JSON.stringify({ usuario }) }),
  adminResetClave: (id: string, modo: "temporal" | "sin_clave") =>
    pedir<{ ok: boolean; clave_temporal: string | null; modo: string }>(`/admin/usuarios/${id}/clave`, { method: "POST", body: JSON.stringify({ modo }) }),
  adminBorrar: (id: string) => pedir<{ ok: boolean }>(`/admin/usuarios/${id}`, { method: "DELETE" }),
  adminCambios: () => pedir<Cambio[]>("/admin/cambios"),
  listaBlanca: () => pedir<{ emails: Autorizado[]; dominio: string }>("/admin/lista-blanca"),
  listaBlancaAlta: (email: string, rol: string, nota: string) => pedir<{ ok: boolean; fila: Autorizado | null }>("/admin/lista-blanca", { method: "PUT", body: JSON.stringify({ email, rol, nota }) }),
  listaBlancaBaja: (email: string) => pedir<{ ok: boolean }>(`/admin/lista-blanca/${encodeURIComponent(email)}`, { method: "DELETE" }),

  recortes: (vista: "mios" | "equipo" | "todos", buscar = "") => {
    const q = new URLSearchParams();
    if (vista === "equipo") q.set("equipo", "1");
    if (vista === "todos") q.set("todos", "1");
    if (buscar) q.set("buscar", buscar);
    const s = q.toString();
    return pedir<Recorte[]>("/recortes" + (s ? "?" + s : ""));
  },
  recorte: (id: string) => pedir<Detalle>(`/recortes/${id}`),
  opciones: () => pedir<Opciones>("/recortes/opciones"),
  usos: (id: string) => pedir<Uso[]>(`/recortes/${id}/usos`),
  borrar: (id: string) => pedir<{ ok: boolean; aviso: string | null }>(`/recortes/${id}`, { method: "DELETE" }),
  reintentar: (id: string) => pedir<{ ok: boolean }>(`/recortes/${id}/reintentar`, { method: "POST" }),
  /** (3/11, Julián) el mp4 del recorte como archivo: la API lo baja de WordPress y lo entrega con nombre. */
  descargarRecorte: (id: string) => pedirCrudo(`/recortes/${id}/descargar`),
  /** (5/11, Julián) sube un video propio (multipart: archivo, titulo, formato); sin Content-Type manual, lo pone el navegador. */
  subirRecorte: async (form: FormData) => (await pedirCrudo("/recortes/subir", { method: "POST", body: form })).json() as Promise<{ ok: boolean; id: string | null; url: string; aviso: string | null }>,
  compartir: (id: string, compartido: boolean) => pedir<{ ok: boolean; compartido: boolean }>(`/recortes/${id}/compartir`, { method: "POST", body: JSON.stringify({ compartido }) }),
  editar: (id: string, datos: Record<string, unknown>) =>
    pedir<RespuestaEdicion>(`/recortes/${id}/edicion`, { method: "POST", body: JSON.stringify(datos) }),
  guardarEstiloDefecto: (estilo: Estilo) =>
    pedir<{ ok: boolean; estilo: Estilo }>("/recortes/estilo-defecto", { method: "PUT", body: JSON.stringify({ estilo }) }),
};
