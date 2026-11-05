// (5/11) El aviso cuando otra persona guardó la pieza (o el recorte) mientras esta pantalla la editaba: la API contestó 409 con el
// mensaje. Dos salidas: recargar la pieza para ver sus cambios (lo no guardado acá se pierde) o guardar igual, pisando.
import { ErrorApi } from "../api";
import Modal from "./Modal";
import "../presencia.css";

/** ¿Este error es el 409 de «otra persona guardó antes»? (el de versión trae version_actual; los otros 409 no.) */
export function esConflictoDeVersion(e: unknown): e is ErrorApi {
  return e instanceof ErrorApi && e.status === 409 && !!e.datos && "version_actual" in e.datos;
}

interface Props {
  mensaje: string;
  onRecargar: () => void;
  onPisar: () => void;
  onCerrar: () => void;
  ocupado?: boolean;
}

export default function ConflictoGuardado({ mensaje, onRecargar, onPisar, onCerrar, ocupado }: Props) {
  return (
    <Modal titulo="Alguien guardó antes que vos" onCerrar={onCerrar} peligro>
      <p>{mensaje}</p>
      <p className="suave chico">«Recargar» muestra la última versión y descarta lo que cambiaste acá sin guardar. «Guardar igual» deja tu versión y pisa la de la otra persona.</p>
      <div className="conflicto-acciones">
        <button type="button" className="boton sutil" onClick={onPisar} disabled={ocupado}>
          Guardar igual, pisando
        </button>
        <button type="button" className="boton primario" onClick={onRecargar} disabled={ocupado}>
          Recargar y ver sus cambios
        </button>
      </div>
    </Modal>
  );
}
