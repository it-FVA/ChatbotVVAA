// Cliente de la API para Publicar, Mis publicaciones y Aprobación (api/publicar_rutas.py). La sesión es la cookie de siempre.
import { BASE, ErrorApi } from "./api";
import type { ConversacionBorrada, MisPublicaciones, OpcionesPublicar, ParaAprobar, PiezaForm, Publicacion, RespuestaAprobacion, RespuestaBorrador, RespuestaEnvio, SubidaBanco } from "./tiposPublicar";

async function errorDe(r: Response): Promise<ErrorApi> {
  let detalle = r.statusText || `Error ${r.status}`;
  try {
    const j = await r.json();
    detalle = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
  } catch {
    /* sin cuerpo */
  }
  return new ErrorApi(r.status, detalle);
}

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + ruta, { credentials: "include", headers: { "Content-Type": "application/json", ...(init.headers || {}) }, ...init });
  if (!r.ok) throw await errorDe(r);
  return (await r.json()) as T;
}

/** Lo que viaja a la API: el formulario tal cual (las claves coinciden con PiezaCompleta). */
export function cuerpo(p: PiezaForm) {
  return {
    canal: p.canal,
    titulo: p.titulo.trim(),
    texto: p.texto,
    imagen_url: p.imagen_url || null,
    imagen_busqueda: p.imagen_busqueda.trim() || null,
    fecha: p.fecha,
    hora: p.fecha ? p.hora || "09:00" : null,
    texto_imagen: p.texto_imagen.trim() || null,
    firma: p.firma,
    formato: p.formato,
    tipografia: p.tipografia,
    peso: p.peso,
    posicion: p.posicion,
    alineacion: p.alineacion,
    logo: p.logo,
    posicion_logo: p.posicion_logo,
    usar_compuesta: p.usar_compuesta,
    video_url: p.video_url,
    video_formato: p.video_formato,
    vfmt: p.vfmt,
    borrador_id: p.borrador_id,
  };
}

export const apiPublicar = {
  opciones: () => pedir<OpcionesPublicar>("/publicar/opciones"),

  /** Sube una imagen al banco de WordPress (multipart). ok=false con aviso si WordPress está en simulado/apagado. */
  async subirAlBanco(archivo: File, titulo: string): Promise<SubidaBanco> {
    const fd = new FormData();
    fd.append("archivo", archivo, archivo.name);
    fd.append("titulo", titulo);
    const r = await fetch(BASE + "/banco/subir", { method: "POST", credentials: "include", body: fd });
    if (!r.ok) throw await errorDe(r);
    return (await r.json()) as SubidaBanco;
  },

  /** La foto con la frase encima: devuelve una URL de objeto (blob) para el <img>. Quien la recibe la revoca cuando ya no la usa. */
  async componer(datos: Record<string, unknown>, signal?: AbortSignal): Promise<string> {
    const r = await fetch(BASE + "/publicar/componer", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos), signal });
    if (!r.ok) throw await errorDe(r);
    return URL.createObjectURL(await r.blob());
  },

  borrador: (p: PiezaForm) => pedir<RespuestaBorrador>("/publicar/borrador", { method: "POST", body: JSON.stringify(cuerpo(p)) }),
  aAprobar: (p: PiezaForm) => pedir<RespuestaAprobacion>("/publicar/a-aprobar", { method: "POST", body: JSON.stringify(cuerpo(p)) }),
  enviar: (p: PiezaForm, modo: "real" | "simulado") => pedir<RespuestaEnvio>("/publicar/enviar", { method: "POST", body: JSON.stringify({ ...cuerpo(p), modo }) }),

  mias: () => pedir<MisPublicaciones>("/publicaciones"),
  una: (id: string) => pedir<Publicacion>(`/publicaciones/${encodeURIComponent(id)}`),
  eliminar: (id: string) => pedir<{ ok: boolean }>(`/publicaciones/${encodeURIComponent(id)}`, { method: "DELETE" }),

  paraAprobar: () => pedir<ParaAprobar>("/aprobacion/para-aprobar"),
  aprobar: (id: string, fecha: string, hora: string) => pedir<{ ok: boolean; estado: string; mensaje: string }>(`/aprobacion/${id}/aprobar`, { method: "POST", body: JSON.stringify({ fecha, hora }) }),
  rechazar: (id: string, nota: string) => pedir<{ ok: boolean; estado: string; mensaje: string }>(`/aprobacion/${id}/rechazar`, { method: "POST", body: JSON.stringify({ nota }) }),
  cola: () => pedir<Publicacion[]>("/aprobacion/cola"),
  cancelar: (id: string) => pedir<{ ok: boolean }>(`/aprobacion/${id}/cancelar`, { method: "POST" }),
  registro: () => pedir<Publicacion[]>("/aprobacion/registro"),
  papelera: () => pedir<{ conversaciones: ConversacionBorrada[]; dias: number }>("/aprobacion/papelera"),
  restaurar: (id: string) => pedir<{ ok: boolean }>(`/aprobacion/papelera/${id}/restaurar`, { method: "POST" }),
};
