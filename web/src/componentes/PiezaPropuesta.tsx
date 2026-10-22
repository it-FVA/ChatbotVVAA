// El recuadro «Publicar esta pieza» debajo de la respuesta cuando el bot propone una pieza (publicar_ui.recuadro, versión
// fase 2): canal, título, texto, fecha opcional, foto del banco si hay, y «Enviar a aprobación» / «Guardar borrador»
// (POST /publicaciones/a-aprobar y /borrador, mismos campos que Streamlit). Publicar en real, la foto con la frase encima y el
// diseño quedan para la pantalla de Publicar completa (fase 3): hasta entonces, el link lleva a «Mis publicaciones» de Streamlit.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi, STREAMLIT_URL } from "../api";
import { apiChat } from "../apiChat";
import type { FotoBanco, Modos, Pieza, RespuestaPieza } from "../tiposChat";
import { Icono } from "./Iconos";
import { useToast } from "./Toasts";

const CANALES: { clave: string; nombre: string }[] = [
  { clave: "wordpress", nombre: "Blogpost (WordPress)" },
  { clave: "instagram", nombre: "Instagram" },
  { clave: "facebook", nombre: "Facebook" },
  { clave: "youtube", nombre: "YouTube" },
];
const FORMATO_POR_CANAL: Record<string, string | undefined> = { facebook: "cuadrado", instagram: "vertical" };

let modosCache: Promise<Modos> | null = null;
function cargarModos() {
  if (!modosCache) modosCache = apiChat.modos().catch((e) => {
    modosCache = null;
    throw e;
  });
  return modosCache;
}

export default function PiezaPropuesta({ pieza, abierto }: { pieza: Pieza; abierto: boolean }) {
  const { avisar } = useToast();
  const [canal, setCanal] = useState(pieza.canal && pieza.canal !== "newsletter" ? pieza.canal : "");
  const [titulo, setTitulo] = useState(pieza.titulo || "");
  const [texto, setTexto] = useState(pieza.texto || "");
  const [textoImagen, setTextoImagen] = useState(pieza.texto_imagen || "");
  const [programar, setProgramar] = useState(!!pieza.fecha);
  const [fecha, setFecha] = useState(pieza.fecha || manana());
  const [hora, setHora] = useState(pieza.hora || "09:00");
  const [busqueda, setBusqueda] = useState(pieza.imagen_busqueda || "");
  const [fotos, setFotos] = useState<FotoBanco[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [imagenUrl, setImagenUrl] = useState<string | null>(null);
  const [modos, setModos] = useState<Modos | null>(null);
  const [enviando, setEnviando] = useState<"aprobar" | "borrador" | null>(null);
  const [hecho, setHecho] = useState<RespuestaPieza | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    cargarModos().then(setModos).catch(() => setModos(null));
  }, []);

  // Foto del banco: si el bot sugirió una búsqueda o el canal es de redes, busca al abrir (como publicar_ui._banco).
  useEffect(() => {
    if (pieza.imagen_busqueda || canal === "instagram" || canal === "facebook") buscarFotos(pieza.imagen_busqueda || "", !!pieza.imagen_busqueda);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function buscarFotos(q: string, elegirPrimera = false) {
    setBuscando(true);
    try {
      const res = await apiChat.banco(q, FORMATO_POR_CANAL[canal]);
      setFotos(res);
      if (elegirPrimera && res.length) setImagenUrl(res[0].url);
    } catch {
      setFotos([]);
    } finally {
      setBuscando(false);
    }
  }

  const infoCanal = canal && modos ? modos.canales[canal] : null;
  const puedeAprobar = !!infoCanal?.a_aprobar;
  const motivoNoAprobar = !canal
    ? "Elegí el canal."
    : canal === "youtube"
      ? "YouTube no pasa por aprobación: se publica desde Publicar en Streamlit."
      : infoCanal && !infoCanal.a_aprobar
        ? `${infoCanal.nombre} está en modo ${infoCanal.modo}: guardalo como borrador.`
        : null;
  const faltaTitulo = (canal === "wordpress" || canal === "youtube") && !titulo.trim();

  function datos() {
    return {
      canal,
      titulo: titulo.trim(),
      texto: texto.trim(),
      imagen_url: imagenUrl,
      fecha: programar ? fecha : null,
      hora: programar ? hora : null,
      texto_imagen: textoImagen.trim() || null,
      firma: pieza.firma || null,
      imagen_busqueda: busqueda.trim() || null,
    };
  }

  async function mandar(que: "aprobar" | "borrador") {
    setError(null);
    setEnviando(que);
    try {
      const r = que === "aprobar" ? await apiChat.enviarAAprobacion(datos()) : await apiChat.guardarBorrador(datos());
      setHecho(r);
      avisar(que === "aprobar" ? "Pieza enviada a aprobación." : "Borrador guardado.");
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude guardar la pieza.");
    } finally {
      setEnviando(null);
    }
  }

  if (pieza.canal === "newsletter") {
    return (
      <div className="pieza-caja">
        <div className="pieza-cabecera">
          <Icono nombre="megafono" /> <strong>Esta pieza es un newsletter</strong>
        </div>
        <p className="suave chico">Se arma en el editor de Newsletter, con sus bloques y la vista previa del mail. El texto de la respuesta entra como reflexión del mes.</p>
        <Link className="boton primario" to="/newsletter" state={{ pieza: { titulo: pieza.titulo, texto: pieza.texto } }}>
          <Icono nombre="sobre" /> Abrir en el editor de Newsletter
        </Link>
      </div>
    );
  }

  return (
    <details className="pieza-caja" open={abierto}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre="megafono" tam={18} />
        <span>
          Publicar esta pieza
          {canal && <span className="suave"> · {CANALES.find((c) => c.clave === canal)?.nombre}</span>}
          {pieza.fecha && <span className="suave"> · {pieza.fecha}{pieza.hora ? ` ${pieza.hora}` : ""}</span>}
        </span>
      </summary>

      {hecho ? (
        <div className="pieza-hecho">
          <div className="aviso">
            <Icono nombre="check" tam={16} /> <span>{hecho.mensaje}</span>
          </div>
          <a className="boton" href={STREAMLIT_URL + "/?vista=mis"} target="_blank" rel="noreferrer">
            <Icono nombre="externo" /> Ver en Mis publicaciones
          </a>
        </div>
      ) : (
        <div className="pieza-form">
          <fieldset className="pieza-canales">
            <legend>Canal</legend>
            {CANALES.map((c) => (
              <label key={c.clave} className={"pieza-canal" + (canal === c.clave ? " activo" : "")}>
                <input type="radio" name={`canal-${pieza.titulo.slice(0, 10)}`} value={c.clave} checked={canal === c.clave} onChange={() => setCanal(c.clave)} />
                {c.nombre}
              </label>
            ))}
          </fieldset>
          {infoCanal && (
            <p className="suave chico pieza-modo">
              {infoCanal.nombre} en modo <strong>{infoCanal.modo}</strong> — {infoCanal.texto}
            </p>
          )}
          {!canal && <p className="suave chico pieza-modo">Elegí el canal para ver qué va a pasar al enviar.</p>}

          <label>
            Título {canal === "wordpress" || canal === "youtube" ? "(obligatorio)" : "(opcional, para el registro)"}
            <input value={titulo} onChange={(e) => setTitulo(e.target.value)} maxLength={150} />
          </label>
          <label>
            Texto de la pieza{canal === "instagram" || canal === "facebook" ? " (el caption)" : canal === "youtube" ? " (la descripción del video)" : ""}
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={7} />
          </label>
          {(pieza.texto_imagen || canal === "instagram" || canal === "facebook") && (
            <label>
              Texto sobre la imagen <span className="suave">(para el diseño; la foto con la frase se arma en Publicar, fase 3)</span>
              <input value={textoImagen} onChange={(e) => setTextoImagen(e.target.value)} maxLength={400} />
            </label>
          )}

          {canal !== "youtube" && (
            <div className="pieza-banco">
              <label htmlFor={`banco-${pieza.titulo.slice(0, 10)}`}>Foto del banco de WordPress</label>
              <div className="pieza-banco-buscar">
                <input id={`banco-${pieza.titulo.slice(0, 10)}`} value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="ej. amanecer montaña calma" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscarFotos(busqueda))} />
                <button type="button" className="boton" onClick={() => buscarFotos(busqueda)} disabled={buscando}>
                  <Icono nombre="buscar" tam={16} /> {buscando ? "Buscando…" : "Buscar"}
                </button>
              </div>
              {fotos && fotos.length > 0 && (
                <div className="pieza-fotos" role="radiogroup" aria-label="Elegí una foto">
                  <button type="button" className={"pieza-foto sin" + (imagenUrl === null ? " elegida" : "")} onClick={() => setImagenUrl(null)} role="radio" aria-checked={imagenUrl === null}>
                    Sin imagen
                  </button>
                  {fotos.map((f) => (
                    <button key={f.id} type="button" className={"pieza-foto" + (imagenUrl === f.url ? " elegida" : "")} onClick={() => setImagenUrl(f.url)} role="radio" aria-checked={imagenUrl === f.url} title={f.titulo || `#${f.id}`}>
                      <img src={f.miniatura} alt={f.titulo || ""} loading="lazy" />
                      <span className="chico">{(f.titulo || `#${f.id}`).slice(0, 28)}</span>
                    </button>
                  ))}
                </div>
              )}
              {fotos && fotos.length === 0 && !buscando && <p className="suave chico">El banco no tiene nada para esa búsqueda (o la API no tiene acceso a WordPress). Probá otras palabras; la foto también se puede elegir después, en Publicar.</p>}
            </div>
          )}

          <label className="casilla">
            <input type="checkbox" checked={programar} onChange={(e) => setProgramar(e.target.checked)} /> Programar para una fecha
          </label>
          {programar && (
            <div className="pieza-fecha">
              <label>
                Día
                <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
              </label>
              <label>
                Hora
                <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} />
              </label>
            </div>
          )}

          {error && <div className="aviso error">{error}</div>}
          <div className="acciones">
            <button type="button" className="boton primario" onClick={() => mandar("aprobar")} disabled={enviando !== null || !puedeAprobar || !texto.trim() || faltaTitulo} title={motivoNoAprobar || (faltaTitulo ? "Falta el título." : "La revisa un aprobador y, si la aprueba, sale por el canal.")}>
              <Icono nombre="check" /> {enviando === "aprobar" ? "Enviando…" : "Enviar a aprobación"}
            </button>
            <button type="button" className="boton" onClick={() => mandar("borrador")} disabled={enviando !== null || !canal} title="Guarda todo sin mandar nada; se retoma desde Mis publicaciones.">
              <Icono nombre="lapiz" /> {enviando === "borrador" ? "Guardando…" : "Guardar borrador"}
            </button>
            <a className="boton sutil" href={STREAMLIT_URL + "/?vista=mis"} target="_blank" rel="noreferrer">
              <Icono nombre="externo" /> Mis publicaciones
            </a>
          </div>
          {motivoNoAprobar && canal && <p className="suave chico">{motivoNoAprobar}</p>}
          {modos?.publica && <p className="suave chico">Publicar directo (sin aprobación) llega con la pantalla de Publicar de la web; mientras tanto se hace desde Streamlit.</p>}
        </div>
      )}
    </details>
  );
}

function manana() {
  const d = new Date(Date.now() + 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
