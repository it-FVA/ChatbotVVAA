// Vista previa «como se ve de verdad» de una pieza en cada canal (22/10, fase 3): Instagram (feed cuadrado/vertical, reel o historia),
// Facebook (texto arriba, foto abajo), Blogpost (entrada con foto destacada, título y cuerpo) y YouTube (reproductor, título, descripción).
// Es una maqueta aproximada hecha con CSS: la imagen que se ve es la que viaja (la compuesta con la frase, o la foto sola).
import { useState } from "react";
import { aHtml } from "../util/markdown";
import { NOMBRE_CANAL, fechaLegible, textoPlano } from "../util/publicar";
import { Icono } from "./Iconos";

export interface DatosPrevia {
  canal: string;
  titulo: string;
  texto: string;
  imagenSrc: string | null; // la compuesta (blob) o la URL de la foto
  videoUrl: string | null;
  formato: string | null; // cuadrado | vertical | historia (foto) · reel | historia (video)
  videoFormato?: string | null; // horizontal | vertical (el del recorte)
  textoImagen?: string | null;
  fechaIso?: string | null;
  componiendo?: boolean;
}

const CUENTA = "vivir.agradecidos";
const PAGINA = "Vivir Agradecidos";

export default function VistaPrevia({ d, compacta = false }: { d: DatosPrevia; compacta?: boolean }) {
  if (!d.canal) {
    return (
      <div className="previa previa-vacia suave">
        <Icono nombre="ojo" tam={28} />
        <p>Elegí el canal y acá se ve cómo quedaría la pieza.</p>
      </div>
    );
  }
  const historia = d.formato === "historia";
  return (
    <div className={"previa previa-" + d.canal + (compacta ? " compacta" : "")} aria-label={"Vista previa en " + (NOMBRE_CANAL[d.canal] || d.canal)}>
      {d.canal === "instagram" && (historia ? <Historia d={d} /> : <Instagram d={d} />)}
      {d.canal === "facebook" && <Facebook d={d} />}
      {d.canal === "wordpress" && <Blogpost d={d} />}
      {d.canal === "youtube" && <YouTube d={d} />}
    </div>
  );
}

function Medio({ d, ratio }: { d: DatosPrevia; ratio: string }) {
  const vertical = d.videoFormato === "vertical";
  return (
    <div className={"previa-medio" + (d.componiendo ? " componiendo" : "")} style={{ aspectRatio: ratio }}>
      {d.videoUrl ? (
        <video src={d.videoUrl} controls muted playsInline preload="metadata" className={vertical ? "vertical" : ""} />
      ) : d.imagenSrc ? (
        <img src={d.imagenSrc} alt={d.textoImagen ? `Foto con la frase: ${d.textoImagen}` : "Foto de la pieza"} />
      ) : (
        <div className="previa-sin-imagen suave">
          <Icono nombre="imagen" tam={26} />
          <span>Sin imagen</span>
        </div>
      )}
      {d.componiendo && <span className="previa-componiendo chico">Armando la foto…</span>}
    </div>
  );
}

function Caption({ texto, cuenta, limite = 125 }: { texto: string; cuenta?: string; limite?: number }) {
  const [todo, setTodo] = useState(false);
  const plano = textoPlano(texto);
  const corto = !todo && plano.length > limite;
  return (
    <p className="previa-caption">
      {cuenta && <strong>{cuenta} </strong>}
      <span className="previa-caption-texto">{corto ? plano.slice(0, limite).trimEnd() : plano}</span>
      {corto && (
        <button type="button" className="previa-mas suave" onClick={() => setTodo(true)}>
          … más
        </button>
      )}
      {!plano && <span className="suave">(sin texto)</span>}
    </p>
  );
}

function Instagram({ d }: { d: DatosPrevia }) {
  const ratio = d.videoUrl ? (d.videoFormato === "vertical" ? "9 / 16" : "16 / 9") : d.formato === "vertical" ? "4 / 5" : "1 / 1";
  return (
    <div className="ig">
      <div className="ig-cabecera">
        <span className="avatar">VA</span>
        <span>
          <strong>{CUENTA}</strong>
          {d.videoUrl && <span className="suave chico"> · Reel</span>}
        </span>
        <span className="suave">···</span>
      </div>
      <Medio d={d} ratio={ratio} />
      <div className="ig-acciones" aria-hidden="true">
        <span>♡</span>
        <span>○</span>
        <span>➤</span>
        <span className="derecha">⌑</span>
      </div>
      <Caption texto={d.texto} cuenta={CUENTA} />
      {d.fechaIso && <p className="suave chico previa-fecha">Programado: {fechaLegible(d.fechaIso)}</p>}
    </div>
  );
}

function Historia({ d }: { d: DatosPrevia }) {
  return (
    <div className="ig historia">
      <div className="historia-marco">
        <div className="historia-barra" />
        <div className="historia-cabecera">
          <span className="avatar chico">VA</span>
          <strong>{CUENTA}</strong>
          <span className="suave chico">ahora</span>
        </div>
        <Medio d={d} ratio="9 / 16" />
      </div>
      <p className="suave chico">Historia: dura 24 h y no lleva caption (Instagram no lo permite por API). La frase va en la imagen; el texto queda en el registro.</p>
    </div>
  );
}

function Facebook({ d }: { d: DatosPrevia }) {
  const ratio = d.videoUrl ? (d.videoFormato === "vertical" ? "9 / 16" : "16 / 9") : d.formato === "vertical" ? "4 / 5" : d.formato === "historia" ? "9 / 16" : "1 / 1";
  return (
    <div className="fb">
      <div className="fb-cabecera">
        <span className="avatar">VA</span>
        <span>
          <strong>{PAGINA}</strong>
          <br />
          <span className="suave chico">{d.fechaIso ? "Programado · " + fechaLegible(d.fechaIso) : "Ahora"} · 🌐</span>
        </span>
      </div>
      <Caption texto={d.texto} limite={400} />
      {(d.imagenSrc || d.videoUrl) && <Medio d={d} ratio={ratio} />}
      <div className="fb-reacciones suave chico" aria-hidden="true">
        <span>👍 ❤️ Me gusta</span>
        <span>Comentar</span>
        <span>Compartir</span>
      </div>
    </div>
  );
}

function Blogpost({ d }: { d: DatosPrevia }) {
  const html = aHtml(d.texto || "");
  return (
    <article className="wp">
      {d.videoUrl ? (
        <div className="wp-video">
          <video src={d.videoUrl} controls muted playsInline preload="metadata" />
          <span className="suave chico">El recorte va al principio de la entrada.</span>
        </div>
      ) : (
        d.imagenSrc && (
          <div className="wp-destacada">
            <img src={d.imagenSrc} alt="" />
          </div>
        )
      )}
      <p className="suave chico wp-meta">viviragradecidos.org · {d.fechaIso ? fechaLegible(d.fechaIso, false) : "hoy"}</p>
      <h2 className="wp-titulo">{d.titulo || <span className="suave">(sin título)</span>}</h2>
      {html ? <div className="wp-cuerpo markdown" dangerouslySetInnerHTML={{ __html: html }} /> : <p className="suave">(sin texto)</p>}
    </article>
  );
}

function YouTube({ d }: { d: DatosPrevia }) {
  const [todo, setTodo] = useState(false);
  const plano = textoPlano(d.texto);
  const vertical = d.videoFormato === "vertical";
  return (
    <div className="yt">
      <div className={"yt-player" + (vertical ? " vertical" : "")}>
        {d.videoUrl ? (
          <video src={d.videoUrl} controls muted playsInline preload="metadata" />
        ) : (
          <div className="previa-sin-imagen suave">
            <Icono nombre="pelicula" tam={26} />
            <span>Sin video: publicá un recorte desde «Mis recortes»</span>
          </div>
        )}
      </div>
      <h3 className="yt-titulo">{d.titulo || <span className="suave">(sin título)</span>}</h3>
      <div className="yt-canal">
        <span className="avatar chico">VA</span>
        <strong>{PAGINA}</strong>
        {vertical && <span className="chip suave">Short</span>}
      </div>
      <div className="yt-descripcion chico">
        {todo || plano.length <= 160 ? plano : plano.slice(0, 160) + "…"}
        {plano.length > 160 && !todo && (
          <button type="button" className="previa-mas" onClick={() => setTodo(true)}>
            Más
          </button>
        )}
      </div>
    </div>
  );
}
