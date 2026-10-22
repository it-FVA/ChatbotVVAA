// Estado compartido de «Proyectos» (22/10): la lista plana de carpetas (mías + compartidas conmigo) y dónde está cada cosa.
// Lo usan el árbol de la barra lateral del chat, la vista grande, «Mover a…» y los chips. Se carga una vez por sesión y se
// vuelve a pedir después de cada cambio (recargar()).
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiProyectos } from "../../apiProyectos";
import { useSesion } from "../../App";
import type { Proyecto, TipoItem, Ubicaciones } from "../../tiposProyectos";

export interface NodoProyecto extends Proyecto {
  hijos: NodoProyecto[];
  nivel: number;
}

interface Estado {
  proyectos: Proyecto[] | null; // null = cargando
  error: string | null;
  ubicaciones: Ubicaciones;
  /** Árbol: raíces mías primero, después las compartidas conmigo. */
  arbol: NodoProyecto[];
  porId: Map<string, Proyecto>;
  recargar: () => Promise<void>;
  /** En qué carpeta está un ítem (o null si está suelto). */
  carpetaDe: (tipo: TipoItem, itemId: string) => Proyecto | null;
  /** Las carpetas donde esta persona puede agregar cosas. */
  editables: Proyecto[];
}

const Ctx = createContext<Estado>({
  proyectos: null,
  error: null,
  ubicaciones: {},
  arbol: [],
  porId: new Map(),
  recargar: async () => {},
  carpetaDe: () => null,
  editables: [],
});

export const useProyectos = () => useContext(Ctx);

export function armarArbol(lista: Proyecto[]): NodoProyecto[] {
  const nodos = new Map<string, NodoProyecto>();
  for (const p of lista) nodos.set(p.id, { ...p, hijos: [], nivel: 0 });
  const raices: NodoProyecto[] = [];
  for (const n of nodos.values()) {
    const padre = n.padre_id ? nodos.get(n.padre_id) : undefined;
    if (padre) padre.hijos.push(n);
    else raices.push(n);
  }
  const ordenar = (ns: NodoProyecto[], nivel: number) => {
    ns.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
    for (const n of ns) {
      n.nivel = nivel;
      ordenar(n.hijos, nivel + 1);
    }
  };
  ordenar(raices, 0);
  // mías primero, después las compartidas conmigo
  raices.sort((a, b) => Number(a.permiso !== "dueño") - Number(b.permiso !== "dueño") || a.nombre.localeCompare(b.nombre, "es"));
  return raices;
}

/** Recorrido en profundidad (para listas planas con sangría). */
export function aplanar(arbol: NodoProyecto[]): NodoProyecto[] {
  const out: NodoProyecto[] = [];
  const ir = (ns: NodoProyecto[]) => {
    for (const n of ns) {
      out.push(n);
      ir(n.hijos);
    }
  };
  ir(arbol);
  return out;
}

export function ProyectosProvider({ children }: { children: ReactNode }) {
  const { yo } = useSesion();
  const [proyectos, setProyectos] = useState<Proyecto[] | null>(null);
  const [ubicaciones, setUbicaciones] = useState<Ubicaciones>({});
  const [error, setError] = useState<string | null>(null);

  const recargar = useCallback(async () => {
    try {
      const r = await apiProyectos.listar();
      setProyectos(r.proyectos);
      setUbicaciones(r.ubicaciones || {});
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pude leer los proyectos.");
      setProyectos((p) => p || []);
    }
  }, []);

  useEffect(() => {
    if (yo) recargar();
    else {
      setProyectos(null);
      setUbicaciones({});
    }
  }, [yo, recargar]);

  const valor = useMemo<Estado>(() => {
    const lista = proyectos || [];
    const porId = new Map(lista.map((p) => [p.id, p]));
    return {
      proyectos,
      error,
      ubicaciones,
      arbol: armarArbol(lista),
      porId,
      recargar,
      carpetaDe: (tipo, itemId) => {
        const pid = ubicaciones[tipo]?.[itemId];
        return (pid && porId.get(pid)) || null;
      },
      editables: lista.filter((p) => p.permiso !== "ver"),
    };
  }, [proyectos, ubicaciones, error, recargar]);

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}

/** Nombre con emoji adelante, si tiene. */
export function etiqueta(p: Pick<Proyecto, "nombre" | "emoji">) {
  return (p.emoji ? p.emoji + " " : "") + p.nombre;
}
