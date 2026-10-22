// Cliente de la API para el chat: conversaciones, el mensaje en streaming (SSE por POST, leído a mano porque EventSource
// solo hace GET), recortes desde las tarjetas, pieza propuesta y descargas. La sesión es la cookie de siempre.
import { BASE, ErrorApi } from "./api";
import type { Clip, Conversacion, ConversacionResumen, FinChat, FotoBanco, Modos, Pieza, PiezaEnviada, RespuestaPedido, RespuestaPieza, Tarjeta } from "./tiposChat";

async function pedir<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + ruta, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!r.ok) throw await errorDe(r);
  marcarViva();
  return (await r.json()) as T;
}

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

// ---------- ¿la API está despierta? (Render plan free se duerme a los 15 min; arrancar tarda ~1 min) ----------
let ultimaVezViva = 0;
const DORMIDA_TRAS_MS = 10 * 60 * 1000;
function marcarViva() {
  ultimaVezViva = Date.now();
}

async function saludRapida(ms: number): Promise<boolean> {
  const ctl = new AbortController();
  const t = window.setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(BASE + "/salud", { credentials: "include", signal: ctl.signal });
    return r.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(t);
  }
}

/** Antes de mandar un mensaje: si hace rato que no hablamos con la API, le pega a /salud. Si no contesta en unos segundos,
 *  avisa (onDespertando) y reintenta cada 5 s hasta 2 minutos. Devuelve false si nunca contestó. */
export async function esperarApi(onDespertando: () => void, signal?: AbortSignal): Promise<boolean> {
  if (Date.now() - ultimaVezViva < DORMIDA_TRAS_MS) return true;
  if (await saludRapida(6000)) {
    marcarViva();
    return true;
  }
  onDespertando();
  const limite = Date.now() + 120000;
  while (Date.now() < limite && !signal?.aborted) {
    await new Promise((ok) => window.setTimeout(ok, 5000));
    if (await saludRapida(8000)) {
      marcarViva();
      return true;
    }
  }
  return false;
}

// ---------- conversaciones ----------
export const apiChat = {
  conversaciones: () => pedir<ConversacionResumen[]>("/conversaciones"),
  conversacion: (id: string) => pedir<Conversacion>(`/conversaciones/${id}`),
  renombrar: (id: string, titulo: string) => pedir<{ ok: boolean; titulo: string }>(`/conversaciones/${id}`, { method: "PATCH", body: JSON.stringify({ titulo }) }),
  borrar: (id: string) => pedir<{ ok: boolean; dias: number }>(`/conversaciones/${id}`, { method: "DELETE" }),
  restaurar: (id: string) => pedir<{ ok: boolean; titulo: string | null }>(`/conversaciones/${id}/restaurar`, { method: "POST" }),
  recortesDe: (id: string) => pedir<Clip[]>(`/conversaciones/${id}/recortes`),
  pedirRecorte: (datos: { video_id: string; inicio_ms: number; fin_ms: number; formato: "horizontal" | "vertical"; titulo: string | null }) =>
    pedir<RespuestaPedido>("/recortes", { method: "POST", body: JSON.stringify(datos) }),
  banco: (consulta: string, formato?: string | null) => {
    const q = new URLSearchParams({ consulta });
    if (formato) q.set("formato", formato);
    return pedir<FotoBanco[]>("/banco?" + q.toString());
  },
  modos: () => pedir<Modos>("/publicaciones/modos"),
  guardarBorrador: (p: PiezaEnviada) => pedir<RespuestaPieza>("/publicaciones/borrador", { method: "POST", body: JSON.stringify(p) }),
  enviarAAprobacion: (p: PiezaEnviada) => pedir<RespuestaPieza>("/publicaciones/a-aprobar", { method: "POST", body: JSON.stringify(p) }),

  /** Baja el Word o el Excel de la respuesta n (con la cookie, para que el error se pueda leer). */
  async descargar(id: string, n: number, tipo: "docx" | "xlsx"): Promise<void> {
    const r = await fetch(BASE + `/conversaciones/${id}/mensajes/${n}/${tipo}`, { credentials: "include" });
    if (!r.ok) throw await errorDe(r);
    const nombre = /filename\*=UTF-8''([^;]+)/.exec(r.headers.get("content-disposition") || "")?.[1];
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nombre ? decodeURIComponent(nombre) : `respuesta.${tipo}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  },
};

// ---------- el mensaje en streaming ----------
export type EventoChat =
  | { nombre: "inicio"; datos: { conversacion_id: string | null; titulo: string | null } }
  | { nombre: "estado"; datos: { texto: string; herramienta?: string } }
  | { nombre: "fuentes"; datos: { tarjetas: Tarjeta[] } }
  | { nombre: "pieza"; datos: Pieza }
  | { nombre: "texto"; datos: { delta: string } }
  | { nombre: "fin"; datos: FinChat }
  | { nombre: "error"; datos: { detalle: string } };

/** POST /conversaciones/{id|nueva}/mensajes con Accept: text/event-stream; llama a onEvento por cada evento. */
export async function enviarMensaje(id: string | null, texto: string, onEvento: (e: EventoChat) => void, signal?: AbortSignal): Promise<void> {
  const r = await fetch(BASE + `/conversaciones/${id || "nueva"}/mensajes`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ texto, stream: true }),
    signal,
  });
  if (!r.ok) throw await errorDe(r);
  marcarViva();
  if (!r.body) throw new ErrorApi(0, "El navegador no pudo leer la respuesta en streaming.");
  const lector = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  const procesar = (bloque: string) => {
    let nombre = "mensaje";
    const datos: string[] = [];
    for (const linea of bloque.split("\n")) {
      if (linea.startsWith("event:")) nombre = linea.slice(6).trim();
      else if (linea.startsWith("data:")) datos.push(linea.slice(5).trimStart());
    }
    if (!datos.length) return;
    try {
      onEvento({ nombre, datos: JSON.parse(datos.join("\n")) } as EventoChat);
    } catch {
      /* un bloque que no es JSON: se ignora */
    }
  };
  for (;;) {
    const { done, value } = await lector.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      procesar(buf.slice(0, i).replace(/\r/g, ""));
      buf = buf.slice(i + 2);
    }
  }
  if (buf.trim()) procesar(buf.replace(/\r/g, ""));
}
