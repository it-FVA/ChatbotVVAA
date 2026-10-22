// El recuadro «Publicar esta pieza» debajo de la respuesta cuando el bot propone una pieza (publicar_ui.recuadro). Desde la fase 3
// (22/10) el formulario completo vive en la pantalla Publicar (/publicar): acá se muestra la pieza propuesta (canal, título, texto,
// frase para la imagen, fecha) con un botón principal que la abre precargada, y «Guardar borrador» como atajo (POST /publicaciones/borrador).
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorApi, STREAMLIT_URL } from "../api";
import { apiChat } from "../apiChat";
import type { Pieza, RespuestaPieza } from "../tiposChat";
import { NOMBRE_CANAL, fechaLegible } from "../util/publicar";
import { Icono } from "./Iconos";
import { useToast } from "./Toasts";

export default function PiezaPropuesta({ pieza, abierto }: { pieza: Pieza; abierto: boolean }) {
  const { avisar } = useToast();
  const nav = useNavigate();
  const [guardando, setGuardando] = useState(false);
  const [hecho, setHecho] = useState<RespuestaPieza | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [verTodo, setVerTodo] = useState(false);
  const canal = pieza.canal && pieza.canal !== "newsletter" ? pieza.canal : "";
  const fechaIso = pieza.fecha ? `${pieza.fecha}T${(pieza.hora || "09:00").padStart(5, "0")}:00` : null;

  async function guardarBorrador() {
    if (!canal) {
      nav("/publicar", { state: { pieza } });
      return;
    }
    setError(null);
    setGuardando(true);
    try {
      const r = await apiChat.guardarBorrador({
        canal,
        titulo: pieza.titulo || "",
        texto: pieza.texto || "",
        imagen_url: null,
        fecha: pieza.fecha || null,
        hora: pieza.fecha ? pieza.hora || "09:00" : null,
        texto_imagen: pieza.texto_imagen || null,
        firma: pieza.firma || null,
        imagen_busqueda: pieza.imagen_busqueda || null,
      });
      setHecho(r);
      avisar("Borrador guardado.");
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude guardar el borrador.");
    } finally {
      setGuardando(false);
    }
  }

  if (pieza.canal === "newsletter") {
    return (
      <div className="pieza-caja">
        <div className="pieza-cabecera">
          <Icono nombre="megafono" /> <strong>Esta pieza es un newsletter</strong>
        </div>
        <p className="suave chico">Se arma en el editor de Newsletter, con sus bloques y la vista previa (por ahora en Streamlit).</p>
        <a className="boton" href={STREAMLIT_URL + "/?vista=newsletter"} target="_blank" rel="noreferrer">
          <Icono nombre="externo" /> Abrir el editor de Newsletter
        </a>
      </div>
    );
  }

  const texto = pieza.texto || "";
  const largo = texto.length > 420 && !verTodo;
  return (
    <details className="pieza-caja" open={abierto}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre="megafono" tam={18} />
        <span>
          Publicar esta pieza
          {canal && <span className="suave"> · {NOMBRE_CANAL[canal] || canal}</span>}
          {fechaIso && <span className="suave"> · {fechaLegible(fechaIso)}</span>}
        </span>
      </summary>
      {hecho ? (
        <div className="pieza-hecho">
          <div className="aviso">
            <Icono nombre="check" tam={16} /> <span>{hecho.mensaje}</span>
          </div>
          <div className="acciones">
            <Link className="boton primario" to={`/publicar?borrador=${encodeURIComponent(hecho.id)}`}>
              <Icono nombre="lapiz" /> Retomar y publicar
            </Link>
            <Link className="boton" to="/publicaciones">
              <Icono nombre="megafono" /> Mis publicaciones
            </Link>
          </div>
        </div>
      ) : (
        <div className="pieza-resumen">
          <dl className="pieza-datos">
            <div>
              <dt>Canal</dt>
              <dd>{canal ? NOMBRE_CANAL[canal] || canal : <span className="suave">a elegir</span>}</dd>
            </div>
            {pieza.titulo && (
              <div>
                <dt>Título</dt>
                <dd>{pieza.titulo}</dd>
              </div>
            )}
            {pieza.texto_imagen && (
              <div>
                <dt>Frase para la imagen</dt>
                <dd>
                  «{pieza.texto_imagen}»{pieza.firma ? ` ${pieza.firma}` : ""}
                </dd>
              </div>
            )}
            {pieza.imagen_busqueda && (
              <div>
                <dt>Foto sugerida</dt>
                <dd>buscar «{pieza.imagen_busqueda}» en el banco</dd>
              </div>
            )}
            {fechaIso && (
              <div>
                <dt>Cuándo</dt>
                <dd>{fechaLegible(fechaIso)}</dd>
              </div>
            )}
          </dl>
          {texto && (
            <div className="pieza-texto">
              <pre>{largo ? texto.slice(0, 420).trimEnd() + "…" : texto}</pre>
              {largo && (
                <button type="button" className="boton sutil chico" onClick={() => setVerTodo(true)}>
                  Ver todo el texto
                </button>
              )}
            </div>
          )}
          {error && <div className="aviso error">{error}</div>}
          <div className="acciones">
            <button type="button" className="boton primario" onClick={() => nav("/publicar", { state: { pieza } })} title="Abre Publicar con la pieza cargada: foto con la frase, diseño, fecha y envío">
              <Icono nombre="enviar" /> Abrir en Publicar
            </button>
            <button type="button" className="boton" onClick={guardarBorrador} disabled={guardando} title="Guarda la pieza tal cual la propuso el bot; se retoma desde Mis publicaciones.">
              <Icono nombre="lapiz" /> {guardando ? "Guardando…" : "Guardar borrador"}
            </button>
          </div>
        </div>
      )}
    </details>
  );
}
