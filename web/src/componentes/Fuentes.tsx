// Las fuentes debajo de una respuesta: plegable «Fuentes (n) · k citadas» con tarjetas compactas (tag, autor, título, cita de dos
// líneas, «Ver fuente») y las citadas resaltadas; en los videos, la miniatura y los botones de recorte (= app.render_mats +
// app._botones_clip). Los botones de recorte se muestran solo en español, como en Streamlit.
import { useState } from "react";
import { Link } from "react-router-dom";
import type { EstadoRecorte, Tarjeta } from "../tiposChat";
import { textos, TAGS } from "../textos";
import type { Idioma } from "../util/fechas";
import { Icono } from "./Iconos";
import { mmss } from "../util/tiempo";

interface Props {
  tarjetas: Tarjeta[];
  idioma: Idioma;
  abierto: boolean;
  /** null = el mensaje se está generando: todavía no se puede pedir recortes. */
  onPedirRecorte: ((t: Tarjeta, formato: "horizontal" | "vertical") => Promise<void>) | null;
}

export default function Fuentes({ tarjetas, idioma, abierto, onPedirRecorte }: Props) {
  const t = textos(idioma);
  const citadas = tarjetas.filter((x) => x.citada).length;
  return (
    <details className="fuentes" open={abierto}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <span>
          {t("fuentes")} ({tarjetas.length}){citadas > 0 && <span className="suave"> · {t("citada")(citadas)}</span>}
        </span>
      </summary>
      <div className="fuentes-lista">
        {tarjetas.map((x, i) => (
          <TarjetaFuente key={i} x={x} idioma={idioma} onPedirRecorte={onPedirRecorte} />
        ))}
      </div>
    </details>
  );
}

function traducirTag(tag: string, idioma: Idioma) {
  let s = tag;
  for (const [a, b] of Object.entries(TAGS[idioma] || {})) s = s.split(a).join(b);
  return s;
}

function TarjetaFuente({ x, idioma, onPedirRecorte }: { x: Tarjeta; idioma: Idioma; onPedirRecorte: Props["onPedirRecorte"] }) {
  const t = textos(idioma);
  const [abierta, setAbierta] = useState(false);
  const esVideo = x.fuente === "youtube" && x.inicio_ms !== null && !!x.fin_ms;
  const tr = x.traduccion || {};
  const tituloTrad = tr.titulo && tr.titulo.trim().toLowerCase() !== (x.titulo || "").trim().toLowerCase() ? tr.titulo : null;
  const textoTrad = tr.texto && tr.texto.trim().slice(0, 60).toLowerCase() !== (x.texto || "").trim().slice(0, 60).toLowerCase() ? tr.texto : null;
  const mini = esVideo && x.doc ? `https://img.youtube.com/vi/${x.doc}/mqdefault.jpg` : null;

  return (
    <article className={"fuente" + (x.citada ? " citada" : "") + (esVideo ? " video" : "")}>
      {mini && (
        <a className="fuente-mini" href={x.ir || x.url || "#"} target="_blank" rel="noreferrer" tabIndex={-1} aria-hidden="true">
          <img src={mini} alt="" loading="lazy" />
          <span className="fuente-tramo">
            {mmss(x.inicio_ms!)}–{mmss(x.fin_ms!)}
          </span>
        </a>
      )}
      <div className="fuente-cuerpo">
        <div className="fuente-arriba">
          <span className="fuente-tag">{traducirTag(x.tag || "", idioma)}</span>
          {x.autor && <span className="fuente-autor suave">{x.autor}</span>}
          {x.citada && <span className="fuente-badge">{t("citadaBadge")}</span>}
        </div>
        <div className="fuente-titulo">
          {x.titulo}
          {tituloTrad && <span className="fuente-trad"> [{tituloTrad}]</span>}
        </div>
        {x.texto && (
          <button type="button" className={"fuente-cita" + (abierta ? " abierta" : "")} onClick={() => setAbierta((v) => !v)} aria-expanded={abierta} aria-label={`Cita: ${(x.texto || "").slice(0, 80)}`} title={abierta ? undefined : "Ver la cita completa"}>
            “{x.texto.slice(0, 300)}”
            {textoTrad && (
              <span className="fuente-trad">
                {" "}
                ({t("traduccion")}) {textoTrad.slice(0, 400)}
              </span>
            )}
          </button>
        )}
        <div className="fuente-pie">
          {x.ir && (
            <a className="fuente-ver" href={x.ir} target="_blank" rel="noreferrer">
              {t("verFuente")}
            </a>
          )}
          {esVideo && idioma === "es" && <BotonesRecorte x={x} onPedirRecorte={onPedirRecorte} />}
        </div>
      </div>
    </article>
  );
}

const TXT_PEDIR = { horizontal: "Pedir el recorte", vertical: "Pedir en vertical" };
const TXT_VER = { horizontal: "Ver el recorte", vertical: "Ver en vertical" };

function BotonesRecorte({ x, onPedirRecorte }: { x: Tarjeta; onPedirRecorte: Props["onPedirRecorte"] }) {
  const [pidiendo, setPidiendo] = useState<"horizontal" | "vertical" | null>(null);
  async function pedir(formato: "horizontal" | "vertical") {
    if (!onPedirRecorte) return;
    setPidiendo(formato);
    try {
      await onPedirRecorte(x, formato);
    } finally {
      setPidiendo(null);
    }
  }
  return (
    <span className="recorte-botones">
      {(["horizontal", "vertical"] as const).map((f) => {
        const c: EstadoRecorte | null = x.recortes?.[f] ?? null;
        const icono = f === "vertical" ? "celular" : "tijera";
        if (c && c.estado === "listo" && c.url)
          return (
            <span key={f} className="recorte-listo">
              <a className="boton chico" href={c.url} target="_blank" rel="noreferrer">
                <Icono nombre="reproducir" tam={14} /> {TXT_VER[f]}
              </a>
              <Link className="boton sutil chico" to={`/recortes/${c.id}`} title="Abrir en el editor de recortes">
                <Icono nombre="lapiz" tam={14} /> Editar
              </Link>
            </span>
          );
        if (c && c.estado === "pedido")
          return (
            <span key={f} className="estado proceso recorte-estado" title="La cola lo corta en unos 15 minutos; esta tarjeta se actualiza sola.">
              <Icono nombre="reloj" tam={14} /> {f === "vertical" ? "vertical" : "recorte"} en proceso
            </span>
          );
        if (c && c.estado === "error")
          return (
            <span key={f} className="estado error recorte-estado" title={c.error || undefined}>
              <Icono nombre="alerta" tam={14} /> no se pudo recortar{" "}
              <Link to="/recortes" className="chico">
                (ver recortes)
              </Link>
            </span>
          );
        return (
          <button key={f} type="button" className="boton chico" onClick={() => pedir(f)} disabled={!onPedirRecorte || pidiendo !== null} aria-label={`${TXT_PEDIR[f]}: ${x.titulo || ""}`} title="Corta el tramo exacto desde el original en Drive y lo sube a la biblioteca de WordPress. Tarda unos minutos.">
            <Icono nombre={icono} tam={14} /> {pidiendo === f ? "Pidiendo…" : TXT_PEDIR[f]}
          </button>
        );
      })}
    </span>
  );
}
