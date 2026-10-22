// Lo que devuelve api/proyectos.py (22/10): proyectos (carpetas con subcarpetas), ítems referenciados y compartidos.

export type Permiso = "dueño" | "editar" | "ver";
export type TipoItem = "conversacion" | "recorte" | "pieza" | "imagen";

export interface Proyecto {
  id: string;
  nombre: string;
  descripcion: string | null;
  dueno: string;
  padre_id: string | null;
  color: string | null;
  emoji: string | null;
  creado: string;
  actualizado: string;
  permiso: Permiso;
  n_items?: number;
  compartido_con_n?: number;
  /** Solo en los compartidos conmigo: quién lo compartió y si es la raíz que se compartió (o una subcarpeta heredada). */
  compartido_por?: string | null;
  raiz_compartida?: boolean;
  compartido_en?: string | null;
}

/** {tipo: {item_id: proyecto_id}}: en qué carpeta está cada cosa (para el chip de la lista de conversaciones). */
export type Ubicaciones = Partial<Record<TipoItem, Record<string, string>>>;

export interface ItemProyecto {
  id: string; // id de la fila de proyecto_items
  proyecto_id: string;
  tipo: TipoItem;
  item_id: string;
  datos: { url?: string; miniatura?: string; titulo?: string } | null;
  agregado_por: string;
  agregado: string;
  // resumen (api/proyectos.resumir_items)
  titulo: string;
  fecha: string | null;
  miniatura: string | null;
  estado: string | null;
  url: string | null;
  dueno: string | null;
  existe: boolean;
  propio: boolean;
  formato?: string | null;
  canal?: string | null;
}

export interface ContenidoProyecto {
  proyecto: Proyecto;
  permiso: Permiso;
  migas: { id: string; nombre: string }[];
  subcarpetas: Proyecto[];
  items: ItemProyecto[];
  compartido_con: { usuario: string; permiso: "ver" | "editar"; creado: string | null }[];
}

export interface PersonaCompartida {
  usuario: string;
  nombre: string | null;
  permiso: "ver" | "editar";
  compartido_por: string | null;
  creado: string | null;
}

export interface UsuarioBuscado {
  usuario: string;
  nombre: string | null;
  email: string | null;
}

export interface ConversacionCompartida {
  id: string;
  titulo: string;
  actualizado: string;
  dueno: string;
  permiso: "ver" | "editar";
  compartido_por: string;
  compartido_en: string | null;
}

export interface CompartidosConmigo {
  proyectos: Proyecto[];
  conversaciones: ConversacionCompartida[];
}
