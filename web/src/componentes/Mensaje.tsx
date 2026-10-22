// Un mensaje del chat: el de la persona (burbuja) o el del bot (markdown, estado mientras escribe, recuadro de la pieza,
// descargas Word/Excel y las fuentes plegables). Mismo orden que app.py: respuesta → pieza → descargas → fuentes.
import { memo, useMemo, useState } from "react";
import { ErrorApi } from "../api";
import { apiChat } from "../apiChat";
import type { MensajeChat, Tarjeta } from "../tiposChat";
import { textos } from "../textos";
import type { Idioma } from "../util/fechas";
import { aHtml, tieneTablas } from "../util/markdown";
import Fuentes from "./Fuentes";
import PiezaPropuesta from "./PiezaPropuesta";
import { Icono } from "./Iconos";
import { useToast } from "./Toasts";

export const LARGO_MINIMO_WORD = 600; // documentos.LARGO_MINIMO_WORD

interface Props {
  m: MensajeChat;
  n: number; // posición en la conversación (para las descargas)
  convId: string | null;
  idioma: Idioma;
  ultimo: boolean;
  generando: boolean; // este mensaje se está escribiendo ahora
  onPedirRecorte: (t: Tarjeta, formato: "horizontal" | "vertical") => Promise<void>;
}

function MensajeBase({ m, n, convId, idioma, ultimo, generando, onPedirRecorte }: Props) {
  const html = useMemo(() => aHtml(m.content), [m.content]);

  if (m.role === "user") {
    return (
      <div className="msj persona">
        <div className="msj-burbuja">{m.content}</div>
      </div>
    );
  }

  const conPieza = !!m.pieza;
  return (
    <div className={"msj bot" + (generando ? " generando" : "")}>
      <div className="msj-avatar" aria-hidden="true">
        <img src="/logo.png" alt="" />
      </div>
      <div className="msj-cuerpo">
        {m.estado && (
          <div className="msj-estado suave" role="status">
            <span className="girando" aria-hidden="true" /> {m.estado}
          </div>
        )}
        {m.content && <div className="msj-md" dangerouslySetInnerHTML={{ __html: html }} />}
        {generando && m.content && <span className="cursor" aria-hidden="true" />}
        {m.error && (
          <div className="aviso error chico">
            <Icono nombre="alerta" tam={16} /> {m.error}
          </div>
        )}
        {!generando && m.pieza && idioma === "es" && <PiezaPropuesta pieza={m.pieza} abierto={ultimo} />}
        {!generando && convId && m.content.length >= LARGO_MINIMO_WORD && <Descargas convId={convId} n={n} conTablas={tieneTablas(m.content)} idioma={idioma} />}
        {m.tarjetas && m.tarjetas.length > 0 && <Fuentes tarjetas={m.tarjetas} idioma={idioma} abierto={!conPieza} onPedirRecorte={generando ? null : onPedirRecorte} />}
      </div>
    </div>
  );
}

const Mensaje = memo(MensajeBase);
export default Mensaje;

function Descargas({ convId, n, conTablas, idioma }: { convId: string; n: number; conTablas: boolean; idioma: Idioma }) {
  const t = textos(idioma);
  const { avisar } = useToast();
  const [bajando, setBajando] = useState<"docx" | "xlsx" | null>(null);
  async function bajar(tipo: "docx" | "xlsx") {
    setBajando(tipo);
    try {
      await apiChat.descargar(convId, n, tipo);
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude armar el archivo.", "error");
    } finally {
      setBajando(null);
    }
  }
  return (
    <div className="msj-descargas">
      <button type="button" className="boton sutil chico" onClick={() => bajar("docx")} disabled={bajando !== null} aria-label={t("word") + " (.docx)"} title={t("descargaWord")}>
        <Icono nombre="descargar" tam={14} /> {bajando === "docx" ? "…" : t("word")}
      </button>
      {conTablas && (
        <button type="button" className="boton sutil chico" onClick={() => bajar("xlsx")} disabled={bajando !== null} aria-label={t("excel") + " (.xlsx)"} title={t("descargaExcel")}>
          <Icono nombre="descargar" tam={14} /> {bajando === "xlsx" ? "…" : t("excel")}
        </button>
      )}
    </div>
  );
}
