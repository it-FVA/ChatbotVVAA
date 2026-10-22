// Cliente de la API de proyectos (api/proyectos.py). Misma cookie de sesión que el resto.
import { BASE, ErrorApi } from "./api";
import type { CompartidosConmigo, ContenidoProyecto, ItemProyecto, PersonaCompartida, Proyecto, TipoItem, Ubicaciones, UsuarioBuscado } from "./tiposProyectos";

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

export const apiProyectos = {
  listar: () => pedir<{ proyectos: Proyecto[]; ubicaciones: Ubicaciones }>("/proyectos"),
  crear: (datos: { nombre: string; descripcion?: string | null; padre_id?: string | null; color?: string | null; emoji?: string | null }) =>
    pedir<Proyecto>("/proyectos", { method: "POST", body: JSON.stringify(datos) }),
  ver: (id: string) => pedir<ContenidoProyecto>(`/proyectos/${id}`),
  editar: (id: string, datos: { nombre?: string; descripcion?: string | null; padre_id?: string | null; color?: string | null; emoji?: string | null }) =>
    pedir<Proyecto>(`/proyectos/${id}`, { method: "PATCH", body: JSON.stringify(datos) }),
  borrar: (id: string) => pedir<{ ok: boolean }>(`/proyectos/${id}`, { method: "DELETE" }),
  agregarItem: (id: string, tipo: TipoItem, item_id: string, datos?: { url?: string; miniatura?: string; titulo?: string }) =>
    pedir<{ ok: boolean; ya: boolean; item: ItemProyecto }>(`/proyectos/${id}/items`, { method: "POST", body: JSON.stringify({ tipo, item_id, datos: datos || null }) }),
  quitarItem: (id: string, iid: string) => pedir<{ ok: boolean }>(`/proyectos/${id}/items/${iid}`, { method: "DELETE" }),
  moverItem: (id: string, iid: string, proyecto_id: string) => pedir<{ ok: boolean; item: ItemProyecto }>(`/proyectos/${id}/items/${iid}/mover`, { method: "POST", body: JSON.stringify({ proyecto_id }) }),

  conQuien: (tipo: "proyecto" | "conversacion", item_id: string) => pedir<{ dueno: boolean; con: PersonaCompartida[] }>(`/compartidos/${tipo}/${item_id}`),
  compartir: (tipo: "proyecto" | "conversacion", item_id: string, usuario: string, permiso: "ver" | "editar") =>
    pedir<{ ok: boolean; usuario: string; permiso: string; nuevo: boolean }>(`/compartidos/${tipo}/${item_id}`, { method: "PUT", body: JSON.stringify({ usuario, permiso }) }),
  descompartir: (tipo: "proyecto" | "conversacion", item_id: string, usuario: string) =>
    pedir<{ ok: boolean }>(`/compartidos/${tipo}/${item_id}/${encodeURIComponent(usuario)}`, { method: "DELETE" }),
  conmigo: () => pedir<CompartidosConmigo>("/compartidos-conmigo"),
  /** Las piezas de la persona (GET /publicaciones de api/main.py), para el modal «Agregar». */
  misPiezas: () => pedir<{ piezas: { id: string; canal: string; estado: string; titulo: string | null; texto: string | null; imagen_url: string | null; creado: string }[] }>("/publicaciones"),
  buscarUsuarios: (q: string) => pedir<UsuarioBuscado[]>("/usuarios/buscar?q=" + encodeURIComponent(q)),
};
