import { useState } from "react";
import { ayudaDe } from "../ayuda/registro";
import GuiaInteractiva, { guiaVista } from "./GuiaInteractiva";

// (5/11, Franco) El «¿Cómo se usa?» de cada pantalla abre la guía interactiva (cartelitos sobre cada botón) y nada más: la
// página /ayuda y el menú de dos opciones confundían, así que se fueron. `pantalla` es el nombre con el que la pantalla llamó
// a definirAyuda (chat, disenar, publicaciones, recortes, newsletter, frase-del-dia, proyectos, compartidos, aprobacion, administracion).
export default function LinkAyuda({ pantalla }: { pantalla: string }) {
  const [guia, setGuia] = useState(false);
  const [vista, setVista] = useState(() => guiaVista(pantalla));
  if (!ayudaDe(pantalla)?.pasos.length) return null;
  return (
    <span className="link-ayuda-caja">
      <button type="button" className="link-ayuda chico" onClick={() => setGuia(true)} title="Guía de esta pantalla: cartelitos sobre cada botón">
        <span className="link-ayuda-signo" aria-hidden="true">
          ?
        </span>{" "}
        ¿Cómo se usa?
        {!vista && <span className="link-ayuda-punto" aria-hidden="true" />}
      </button>
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
