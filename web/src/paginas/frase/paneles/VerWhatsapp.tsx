// Ventana «Ver el WhatsApp» de un día (prototipo: todavía no se manda).
import { fechaLarga } from "../../../util/fechas";
import { useEffect, useState } from "react";
import { type WhatsappPrevia, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import Modal from "../../../componentes/Modal";
import { mensajeDe } from "../comun";

/** (2/11 tarde) Prototipo de la reunión: la frase en el grupo de WhatsApp, dibujada como un chat. Todavía no se manda (sin endpoint). */
export function VerWhatsapp({ fecha, onCerrar }: { fecha: string; onCerrar: () => void }) {
  const [m, setM] = useState<WhatsappPrevia | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setM(null);
    setError(null);
    apiFrases
      .whatsappPrevia(fecha)
      .then(setM)
      .catch((e) => setError(mensajeDe(e)));
  }, [fecha]);
  const hora = "07:00";
  return (
    <Modal titulo={`El WhatsApp del ${fechaLarga(fecha)}`} onCerrar={onCerrar} ancho={520}>
      {error && <div className="aviso error">{error}</div>}
      {!m && !error && <p className="suave">Armando el mensaje…</p>}
      {m && (
        <div className="fd-wa">
          <p className="chico">
            <strong>Grupo:</strong> {m.grupo}
            <span className="suave"> · modo {m.modo}{m.canal_prendido ? " · canal prendido" : " · canal apagado en Configuración"}</span>
            {m.pieza && <span className="suave"> · pieza {m.pieza.estado}</span>}
          </p>
          <div className="wa-chat" aria-label="Así se vería en WhatsApp">
            <div className="wa-cab">
              <span className="wa-avatar">VA</span>
              <span>
                <strong>{m.grupo}</strong>
                <span className="wa-sub">Vivir Agradecidos, vos y la comunidad</span>
              </span>
            </div>
            <div className="wa-fondo">
              <div className="wa-dia">{m.fecha_texto}</div>
              <div className="wa-burbuja">
                <div className="wa-quien">Vivir Agradecidos</div>
                {m.imagen ? <img src={m.imagen} alt="La frase sobre la foto" /> : <div className="wa-sin-imagen suave chico">Sin imagen ({m.imagen_de})</div>}
                <div className="wa-texto">{m.texto}</div>
                <div className="wa-hora">{hora} ✓✓</div>
              </div>
            </div>
          </div>
          <p className="suave chico">
            <Icono nombre="info" tam={14} /> {m.aviso}
          </p>
        </div>
      )}
    </Modal>
  );
}
