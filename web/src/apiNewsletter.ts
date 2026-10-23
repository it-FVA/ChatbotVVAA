// Cliente de la API para el editor de Newsletter (api/newsletter_rutas.py). La sesión es la cookie de siempre.
import { BASE, ErrorApi } from "./api";

export type Plantilla = "mensual" | "revivi";

export interface Video {
  titulo: string;
  texto: string;
  imagen_url: string;
  url: string;
}
export interface Actividad {
  fecha_corta: string;
  titulo: string;
  descripcion: string;
  fecha: string;
  horario: string;
  modalidad: string;
  facilitan: string;
  boton_texto: string;
  boton_url: string;
  imagen_url: string;
}
export interface Recurso {
  titulo: string;
  url: string;
  de?: string;
  con?: string;
}
/** (23/10, prueba de Julián) Un recurso de «Recursos para profundizar» con su tipo (desplegable); van los que haya, 2 o 3. */
export interface RecursoItem {
  tipo: string;
  titulo: string;
  url: string;
  con: string;
}
export type TiposRecurso = Record<string, { emoji: string; nombre: string }>;
export interface Episodio {
  titulo: string;
  texto: string;
  imagen_url: string;
  url: string;
}
/** Los campos de newsletter.vacio(): la mensual y la Reviví comparten asunto, video, cierre y firma. */
export interface Datos {
  asunto: string;
  mes?: string;
  cabecera_url?: string;
  cabecera_foto?: string; // (23/10) la foto elegida del banco; cabecera_url es la cabecera ya armada (1600×500 con el título)
  cabecera_titulo?: string;
  reflexion?: string;
  preguntas?: string[];
  encuentro?: { titulo: string; frase: string; imagen_url: string; texto: string; boton_texto: string; boton_url: string };
  agenda?: Actividad[];
  recursos?: { imagen_url: string; items?: RecursoItem[]; lectura: Recurso; ecos: Recurso; meditacion: Recurso };
  encuadre?: string;
  intro?: string;
  episodios?: Episodio[];
  cierre_destacado?: string;
  video: Video;
  cierre: string;
  firma: string;
}

export interface Material {
  titulo: string | null;
  autor: string | null;
  tag: string | null;
  url: string | null;
}
export interface BorradorResumen {
  id: string;
  titulo: string;
  plantilla: Plantilla;
  creado: string | null;
  guardado_en: string | null;
}
export interface Respuesta {
  ok: boolean;
  id: string;
  estado: "borrador" | "a_aprobar";
  mensaje: string;
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

export const apiNewsletter = {
  plantillas: () => pedir<{ plantillas: Record<Plantilla, string>; vacios: Record<Plantilla, Datos>; tipos_recurso: TiposRecurso }>("/newsletter/plantillas"),
  /** La cabecera armada (1600×500, título encima) como blob para la vista previa; devuelve también el color elegido. */
  cabeceraPrevia: async (foto_url: string, titulo: string, color: string | null, signal?: AbortSignal) => {
    const r = await fetch(BASE + "/newsletter/cabecera", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ foto_url, titulo, color }), signal });
    if (!r.ok) {
      let detalle = r.statusText || `Error ${r.status}`;
      try {
        const j = await r.json();
        detalle = typeof j.detail === "string" ? j.detail : detalle;
      } catch {
        /* sin cuerpo */
      }
      throw new ErrorApi(r.status, detalle);
    }
    return { blob: await r.blob(), color: r.headers.get("X-Color") || "" };
  },
  /** La misma cabecera subida a WordPress: la URL va a cabecera_url. */
  cabeceraSubir: (foto_url: string, titulo: string, color: string | null) => pedir<{ url: string; color: string }>("/newsletter/cabecera?subir=1", { method: "POST", body: JSON.stringify({ foto_url, titulo, color }) }),
  html: (plantilla: Plantilla, datos: Datos, signal?: AbortSignal) => pedir<{ html: string; titulo: string }>("/newsletter/html", { method: "POST", body: JSON.stringify({ plantilla, datos }), signal }),
  redactar: (plantilla: Plantilla, tema: string, datos: Datos) => pedir<{ datos: Datos; materiales: Material[]; html: string }>("/newsletter/redactar", { method: "POST", body: JSON.stringify({ plantilla, tema, datos }) }),
  borradores: () => pedir<BorradorResumen[]>("/newsletter/borradores"),
  borrador: (id: string) => pedir<{ id: string; titulo: string | null; plantilla: Plantilla; datos: Datos; creado: string | null }>(`/newsletter/borradores/${encodeURIComponent(id)}`),
  guardarBorrador: (plantilla: Plantilla, datos: Datos, borrador_id: string | null) => pedir<Respuesta>("/newsletter/borrador", { method: "POST", body: JSON.stringify({ plantilla, datos, borrador_id }) }),
  aAprobar: (plantilla: Plantilla, datos: Datos, borrador_id: string | null) => pedir<Respuesta>("/newsletter/a-aprobar", { method: "POST", body: JSON.stringify({ plantilla, datos, borrador_id }) }),
};
