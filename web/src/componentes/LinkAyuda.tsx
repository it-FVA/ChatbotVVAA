import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ayudaDe } from "../ayuda/registro";
import GuiaInteractiva, { guiaVista } from "./GuiaInteractiva";

// (5/11, Franco) El «¿Cómo se usa?» de cada pantalla: un botón chico con dos opciones, la guía interactiva sobre la pantalla
// (cartelitos sobre cada botón) y «Leer la ayuda» (la sección de /ayuda). `pantalla` es el nombre con el que la pantalla llamó
// a definirAyuda (chat, disenar, publicaciones, recortes, newsletter, frase-del-dia, proyectos, compartidos, aprobacion, administracion).
export default function LinkAyuda({ pantalla }: { pantalla: string }) {
  const [menu, setMenu] = useState(false);
  const [guia, setGuia] = useState(false);
  const [vista, setVista] = useState(() => guiaVista(pantalla));
  const raiz = useRef<HTMLSpanElement>(null);
  const hayGuia = !!ayudaDe(pantalla)?.pasos.length;

  useEffect(() => {
    if (!menu) return;
    const fuera = (e: MouseEvent) => {
      if (!raiz.current?.contains(e.target as Node)) setMenu(false);
    };
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("mousedown", fuera);
      document.removeEventListener("keydown", tecla);
    };
  }, [menu]);

  return (
    <span className="link-ayuda-caja" ref={raiz}>
      <button type="button" className="link-ayuda chico" onClick={() => setMenu((m) => !m)} aria-expanded={menu} aria-haspopup="true" title="Ayuda de esta pantalla">
        <span className="link-ayuda-signo" aria-hidden="true">
          ?
        </span>{" "}
        ¿Cómo se usa?
        {hayGuia && !vista && <span className="link-ayuda-punto" aria-hidden="true" />}
      </button>
      {menu && (
        <span className="link-ayuda-menu" role="menu">
          {hayGuia && (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setMenu(false);
                setGuia(true);
              }}
            >
              Guía en pantalla
              <span className="suave chico">Cartelitos sobre cada botón</span>
            </button>
          )}
          <Link role="menuitem" to={`/ayuda#${pantalla}`} onClick={() => setMenu(false)}>
            Leer la ayuda
            <span className="suave chico">Instructivo corto</span>
          </Link>
        </span>
      )}
      {guia && (
        <GuiaInteractiva
          pantalla={pantalla}
          onCerrar={() => {
            setGuia(false);
            setVista(true);
          }}
        />
      )}
    </span>
  );
}
