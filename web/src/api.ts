// Cliente de la API. La sesión es una cookie HttpOnly que pone POST /login: el navegador la manda solo
// (credentials: "include" por si la API está en otro dominio en producción).
import type { Detalle, Opciones, Recorte, RespuestaEdicion, Uso, Yo, Estilo } from "./tipos";

export const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";
export const STREAMLIT_URL = (import.meta.env.VITE_STREAMLIT_URL as string | undefined) || "https://chatbotvvaa.streamlit.app";

export class ErrorApi extends Error {
  status: number;
  constructor(status: number, mensaje: string) {
    super(mensaje);
    this.status = status;
  }
}

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + ruta, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
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

export const api = {
  salud: () => pedir<{ ok: boolean; supabase: boolean; login_google: boolean }>("/salud"),
  yo: () => pedir<Yo>("/yo"),
  login: (usuario: string, clave: string) => pedir<Yo>("/login", { method: "POST", body: JSON.stringify({ usuario, clave }) }),
  logout: () => pedir<{ ok: boolean }>("/logout", { method: "POST" }),

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
  editar: (id: string, datos: Record<string, unknown>) =>
    pedir<RespuestaEdicion>(`/recortes/${id}/edicion`, { method: "POST", body: JSON.stringify(datos) }),
  guardarEstiloDefecto: (estilo: Estilo) =>
    pedir<{ ok: boolean; estilo: Estilo }>("/recortes/estilo-defecto", { method: "PUT", body: JSON.stringify({ estilo }) }),
};
