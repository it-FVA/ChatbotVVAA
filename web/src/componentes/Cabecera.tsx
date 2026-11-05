// (5/11, QA visual) La cabecera de toda pantalla: título, subtítulo corto con el «¿Cómo se usa?» y las acciones a la derecha.
// `arriba` va antes del título (migas); `children` va debajo del subtítulo (presencia, chips).
import type { ReactNode } from "react";
import LinkAyuda from "./LinkAyuda";

interface Props {
  titulo: ReactNode;
  subtitulo?: ReactNode;
  /** Nombre de la pantalla en el registro de ayuda: agrega el «¿Cómo se usa?» al final del subtítulo. */
  ayuda?: string;
  acciones?: ReactNode;
  arriba?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export default function Cabecera({ titulo, subtitulo, ayuda, acciones, arriba, children, className }: Props) {
  return (
    <header className={"pagina-cabecera" + (className ? " " + className : "")}>
      {arriba}
      <div className="pagina-cabecera-fila">
        <div className="pagina-cabecera-texto">
          <h1>{titulo}</h1>
          {(subtitulo || ayuda) && (
            <p className="suave pagina-subtitulo">
              {subtitulo}
              {ayuda && (
                <>
                  {" "}
                  <LinkAyuda pantalla={ayuda} />
                </>
              )}
            </p>
          )}
          {children}
        </div>
        {acciones && <div className="acciones pagina-cabecera-acciones">{acciones}</div>}
      </div>
    </header>
  );
}
