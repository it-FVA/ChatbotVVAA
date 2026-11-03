// La API simulada de las pruebas: reemplaza fetch por una tabla «MÉTODO /ruta» → respuesta. Las llamadas quedan registradas
// para comprobar qué mandó la pantalla. Una ruta que la prueba no declaró devuelve 404: la prueba falla con un mensaje claro
// en vez de pegarle a una API real.
import { vi } from "vitest";

export type Manejador = unknown | ((cuerpo: unknown, url: URL) => unknown);
export interface Llamada {
  metodo: string;
  ruta: string;
  consulta: URLSearchParams;
  cuerpo: unknown;
}

export function instalarApi(rutas: Record<string, Manejador>) {
  const llamadas: Llamada[] = [];
  const falso = vi.fn(async (entrada: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(entrada), "http://localhost");
    const metodo = (init.method || "GET").toUpperCase();
    const ruta = url.pathname.replace(/^\/api/, "");
    let cuerpo: unknown = null;
    if (typeof init.body === "string") {
      try {
        cuerpo = JSON.parse(init.body);
      } catch {
        cuerpo = init.body;
      }
    }
    llamadas.push({ metodo, ruta, consulta: url.searchParams, cuerpo });
    const clave = `${metodo} ${ruta}`;
    if (!(clave in rutas)) return new Response(JSON.stringify({ detail: `La prueba no simuló ${clave}` }), { status: 404, headers: { "Content-Type": "application/json" } });
    const m = rutas[clave];
    const salida = typeof m === "function" ? (m as (c: unknown, u: URL) => unknown)(cuerpo, url) : m;
    if (salida instanceof Blob) return new Response(salida, { status: 200 });
    return new Response(JSON.stringify(salida), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", falso);
  return { llamadas, de: (metodo: string, ruta: string) => llamadas.filter((l) => l.metodo === metodo && l.ruta === ruta) };
}
