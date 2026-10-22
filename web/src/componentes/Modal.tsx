// Modal accesible: role=dialog, se cierra con Escape o clic afuera, el foco entra al abrir y vuelve al cerrar, Tab queda adentro.
import { useEffect, useRef, type ReactNode } from "react";
import { Icono } from "./Iconos";

interface Props {
  titulo: string;
  onCerrar: () => void;
  children: ReactNode;
  ancho?: number;
  peligro?: boolean;
}

export default function Modal({ titulo, onCerrar, children, ancho = 460, peligro = false }: Props) {
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const antes = document.activeElement as HTMLElement | null;
    const el = caja.current!;
    const focables = () => Array.from(el.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")).filter((f) => !f.hasAttribute("disabled"));
    // foco inicial: el primer botón que no sea el de cerrar (en un modal de borrado, «Cancelar»)
    const primero = focables().find((f) => !f.classList.contains("modal-cerrar")) ?? focables()[0];
    primero?.focus();
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCerrar();
      } else if (e.key === "Tab") {
        const fs = focables();
        if (!fs.length) return;
        const i = fs.indexOf(document.activeElement as HTMLElement);
        if (e.shiftKey && (i <= 0 || i === -1)) {
          e.preventDefault();
          fs[fs.length - 1].focus();
        } else if (!e.shiftKey && i === fs.length - 1) {
          e.preventDefault();
          fs[0].focus();
        }
      }
    };
    document.addEventListener("keydown", tecla, true);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla, true);
      document.body.style.overflow = "";
      antes?.focus?.();
    };
  }, [onCerrar]);

  return (
    <div className="fondo-modal" onClick={onCerrar}>
      <div className={"modal tarjeta" + (peligro ? " peligro" : "")} role="dialog" aria-modal="true" aria-labelledby="modal-titulo" ref={caja} style={{ maxWidth: ancho }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-cabecera">
          <h3 id="modal-titulo">{titulo}</h3>
          <button type="button" className="boton sutil icono-solo modal-cerrar" onClick={onCerrar} aria-label="Cerrar">
            <Icono nombre="cruz" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
