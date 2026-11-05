// (5/11, Franco) Guía interactiva de una pantalla: un velo con un recorte sobre el elemento del paso y un cartelito con Atrás,
// Siguiente y una cruz. Los pasos salen del registro (ayuda/registro.ts); cada elemento se busca por data-ayuda="<pantalla>.<id>".
// Un paso sin elemento, o cuyo elemento no está en pantalla (p. ej. todavía no hay piezas), se muestra como cartelito general.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ayudaDe, selectorAyuda } from "../ayuda/registro";
import { Icono } from "./Iconos";
import "../guia.css";

const CLAVE = (pantalla: string) => `fva.guia.${pantalla}`;

/** ¿La persona ya hizo (o cerró) la guía de esta pantalla? Solo sirve para no insistir con el puntito. */
export function guiaVista(pantalla: string): boolean {
  try {
    return localStorage.getItem(CLAVE(pantalla)) === "1";
  } catch {
    return false;
  }
}
function marcarVista(pantalla: string) {
  try {
    localStorage.setItem(CLAVE(pantalla), "1");
  } catch {
    /* sin almacenamiento: no pasa nada */
  }
}

interface Caja {
  top: number;
  left: number;
  width: number;
  height: number;
}

const MARGEN = 6;
const ANCHO_CARTEL = 340;

/** El elemento del paso si existe y se ve (ancho y alto mayores que cero); si no, null. */
function buscar(pantalla: string, id?: string): HTMLElement | null {
  if (!id) return null;
  const el = document.querySelector<HTMLElement>(selectorAyuda(pantalla, id));
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0 ? el : null;
}

export default function GuiaInteractiva({ pantalla, onCerrar }: { pantalla: string; onCerrar: () => void }) {
  const def = ayudaDe(pantalla);
  const pasos = def?.pasos ?? [];
  const [n, setN] = useState(0);
  const [caja, setCaja] = useState<Caja | null>(null);
  const [estilo, setEstilo] = useState<React.CSSProperties>({});
  const [pegado, setPegado] = useState(false);
  const cartel = useRef<HTMLDivElement>(null);
  const siguiente = useRef<HTMLButtonElement>(null);
  const paso = pasos[n];
  const elemento = paso ? buscar(pantalla, paso.id) : null;
  const faltaElemento = !!paso?.id && !elemento;
  const ultimo = n === pasos.length - 1;

  const cerrar = useCallback(() => {
    marcarVista(pantalla);
    onCerrar();
  }, [pantalla, onCerrar]);

  // Ubicación del recorte y del cartelito. Se recalcula al hacer scroll y al cambiar el tamaño de la ventana.
  const medir = useCallback(() => {
    const el = paso ? buscar(pantalla, paso.id) : null;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    if (!el) {
      setCaja(null);
      setPegado(false);
      setEstilo({});
      return;
    }
    const r = el.getBoundingClientRect();
    // el recorte no puede salirse de la ventana
    const top = Math.max(r.top - MARGEN, 4);
    const left = Math.max(r.left - MARGEN, 4);
    const bottom = Math.min(r.bottom + MARGEN, vh - 4);
    const right = Math.min(r.right + MARGEN, vw - 4);
    setCaja({ top, left, width: Math.max(right - left, 0), height: Math.max(bottom - top, 0) });
    const alto = cartel.current?.offsetHeight ?? 190;
    const ancho = Math.min(ANCHO_CARTEL, vw - 16);
    const chico = vw <= 640;
    const l = Math.min(Math.max(left, 8), vw - ancho - 8);
    if (!chico && bottom + 12 + alto <= vh - 8) {
      setPegado(false);
      setEstilo({ top: bottom + 12, left: l, width: ancho });
    } else if (!chico && top - 12 - alto >= 8) {
      setPegado(false);
      setEstilo({ top: top - 12 - alto, left: l, width: ancho });
    } else {
      setPegado(true); // en el celular, o si no entra al lado: fijo abajo
      setEstilo({});
    }
  }, [pantalla, paso]);

  // Al cambiar de paso: llevar el elemento a la vista y medir. En el celular, el cartelito fijo abajo tapa el tercio de abajo:
  // el elemento se sube hacia el tercio de arriba.
  useLayoutEffect(() => {
    const el = paso ? buscar(pantalla, paso.id) : null;
    if (el) el.scrollIntoView?.({ block: window.innerWidth <= 640 ? "start" : "center", inline: "nearest" });
    medir();
  }, [pantalla, paso, medir]);

  useEffect(() => {
    let raf = 0;
    const pedir = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(medir);
    };
    window.addEventListener("resize", pedir);
    window.addEventListener("scroll", pedir, true); // true: también el scroll de los contenedores
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", pedir);
      window.removeEventListener("scroll", pedir, true);
    };
  }, [medir]);

  // Esc cierra; el foco va al botón principal en cada paso.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        cerrar();
      }
    };
    document.addEventListener("keydown", tecla, true);
    return () => document.removeEventListener("keydown", tecla, true);
  }, [cerrar]);
  useEffect(() => {
    siguiente.current?.focus({ preventScroll: true });
  }, [n]);

  if (!def || pasos.length === 0 || !paso) return null;

  const titulo = paso.titulo || (elemento ? (elemento.getAttribute("aria-label") || elemento.textContent || "").trim().slice(0, 40) : "") || (paso.id ? `Paso ${n + 1}` : def.titulo);
  const general = !elemento;

  return createPortal(
    <div className="guia" role="presentation">
      <div className="guia-bloqueo" />
      {caja ? <div className="guia-recorte" style={caja} aria-hidden="true" /> : <div className="guia-velo" aria-hidden="true" />}
      <div ref={cartel} className={"guia-cartel" + (pegado || general ? " fijo" : "")} style={pegado || general ? undefined : estilo} role="dialog" aria-modal="true" aria-label={`Guía: ${def.titulo}`}>
        <div className="guia-cabecera">
          <strong>{titulo}</strong>
          <button type="button" className="boton sutil chico icono-solo" onClick={cerrar} aria-label="Cerrar la guía" title="Cerrar (Esc)">
            <Icono nombre="cruz" tam={16} />
          </button>
        </div>
        <p>{paso.texto}</p>
        {faltaElemento && <p className="guia-nota suave chico">Ahora no se ve en pantalla: aparece cuando hay contenido o según tu rol. Pasá al siguiente cuando quieras.</p>}
        <div className="guia-pie">
          <span className="suave chico" aria-live="polite">
            {n + 1} de {pasos.length}
          </span>
          <span className="guia-botones">
            <button type="button" className="boton chico" onClick={() => setN((x) => Math.max(0, x - 1))} disabled={n === 0}>
              Atrás
            </button>
            <button ref={siguiente} type="button" className="boton primario chico" onClick={() => (ultimo ? cerrar() : setN((x) => x + 1))}>
              {ultimo ? "Listo" : "Siguiente"}
            </button>
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}
