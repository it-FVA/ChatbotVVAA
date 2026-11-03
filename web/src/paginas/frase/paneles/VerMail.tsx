// Ventana «Ver el mail» de un día (reproducción de la plantilla de Perfit).
import { fechaLarga } from "../../../util/fechas";
import { useEffect, useState } from "react";
import { type MailPrevia, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import Modal from "../../../componentes/Modal";
import { mensajeDe } from "../comun";

export function VerMail({ fecha, onCerrar, onCambiarFoto }: { fecha: string; onCerrar: () => void; onCambiarFoto?: () => void }) {
  const [m, setM] = useState<MailPrevia | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setM(null);
    setError(null);
    apiFrases
      .mailPrevia(fecha)
      .then(setM)
      .catch((e) => setError(mensajeDe(e)));
  }, [fecha]);
  return (
    <Modal titulo={`El mail del ${fechaLarga(fecha)}`} onCerrar={onCerrar} ancho={760}>
      {error && <div className="aviso error">{error}</div>}
      {!m && !error && <p className="suave">Armando el mail…</p>}
      {m && (
        <div className="fd-mail-previa">
          <p className="chico">
            <strong>Asunto:</strong> {m.asunto}
            <span className="suave"> · foto: {m.imagen_de}</span>
          </p>
          <iframe title="Vista previa del mail" srcDoc={m.html} sandbox="" />
          {m.frase && (
            <div className="acciones">
              <button type="button" className="boton chico" onClick={onCambiarFoto} title={onCambiarFoto ? "Elegir otra foto de fondo para esta frase (banco de WordPress o URL)" : "Abrí el día en el calendario y pedí otra foto"}>
                <Icono nombre="imagen" tam={15} /> {onCambiarFoto ? "Cambiar la foto de fondo" : "Pedir otra foto de fondo"}
              </button>
            </div>
          )}
          <p className="suave chico">
            <Icono nombre="info" tam={14} /> {m.aviso}
          </p>
        </div>
      )}
    </Modal>
  );
}
