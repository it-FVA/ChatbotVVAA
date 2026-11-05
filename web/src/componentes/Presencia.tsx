// (5/11) Los chips de «quién está acá»: «Julián está editando» (punto naranja) / «Pato está mirando» (punto verde).
// Con `vacio` (Diseñar) se dibuja siempre y explica para qué sirve aunque no haya nadie; sin `vacio`, si no hay nadie no dibuja nada.
import type { Presente } from "../api";
import "../presencia.css";

interface Props {
  presentes: Presente[];
  /** Texto suave cuando no hay nadie más. Si viene, el componente se dibuja siempre. */
  vacio?: string;
}

export default function Presencia({ presentes, vacio }: Props) {
  if (!presentes.length && !vacio) return null;
  return (
    <div className="presencia" aria-live="polite">
      {presentes.map((p) => (
        <span key={p.usuario} className={"presencia-chip " + p.modo} title={p.hace_seg < 10 ? "Activo ahora" : `Activo hace ${p.hace_seg} s`}>
          <i aria-hidden="true" />
          {p.nombre} está {p.modo === "edita" ? "editando" : "mirando"}
        </span>
      ))}
      {!presentes.length && vacio && <span className="presencia-vacio suave chico">{vacio}</span>}
    </div>
  );
}
