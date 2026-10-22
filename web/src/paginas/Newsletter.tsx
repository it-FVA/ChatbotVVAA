// Newsletter (22/10): paridad con la solapa «✉️ Newsletter» de Streamlit (newsletter_ui.py) y mejor UX. Editor por bloques de las
// dos plantillas reales (mensual y Reviví) a la izquierda y la vista previa del mail en vivo a la derecha (iframe de 600 px, el ancho
// real); en celular, dos solapas. El bot redacta los textos (POST /newsletter/redactar), las fotos salen del banco de WordPress
// (GET /banco) y el bloque «Un recorte para ver» se carga desde un recorte (?recorte=<id> o el selector). «Descargar HTML» para pegar
// en Perfit, «Guardar borrador» (se retoma desde acá o desde Mis publicaciones: ?borrador=<id>) y «Enviar a aprobación» (tabla
// publicaciones, canal newsletter, mismos estados que las demás piezas). El email NO sale de acá.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { apiChat } from "../apiChat";
import { apiNewsletter, type Actividad, type BorradorResumen, type Datos, type Material, type Plantilla } from "../apiNewsletter";
import type { FotoBanco } from "../tiposChat";
import type { Recorte } from "../tipos";
import { Icono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import "../newsletter.css";

const NOMBRE: Record<Plantilla, string> = { mensual: "Mensual", revivi: "Reviví" };
const DESCRIPCION: Record<Plantilla, string> = { mensual: "reflexión + agenda + recursos", revivi: "tres episodios de Ecos" };
type Destino = { clave: string; nombre: string; poner: (d: Datos, url: string) => void };

/** La pieza que llega desde el chat cuando el bot propone un newsletter (PiezaPropuesta → location.state). */
interface PiezaChat {
  titulo?: string;
  texto?: string;
}

export default function Newsletter() {
  const { avisar } = useToast();
  const nav = useNavigate();
  const loc = useLocation();
  const [params, setParams] = useSearchParams();
  const [vacios, setVacios] = useState<Record<Plantilla, Datos> | null>(null);
  const [plantilla, setPlantilla] = useState<Plantilla>("mensual");
  const [d, setD] = useState<Datos | null>(null);
  const [borradorId, setBorradorId] = useState<string | null>(null);
  const [tema, setTema] = useState("");
  const [redactando, setRedactando] = useState(false);
  const [materiales, setMateriales] = useState<Material[]>([]);
  const [html, setHtml] = useState("");
  const [titulo, setTitulo] = useState("Newsletter");
  const [armando, setArmando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<"borrador" | "aprobar" | null>(null);
  const [solapa, setSolapa] = useState<"editor" | "previa">("editor");
  const [abrirBorradores, setAbrirBorradores] = useState(false);
  const [confirmarReinicio, setConfirmarReinicio] = useState(false);
  const [elegirRecorte, setElegirRecorte] = useState(false);
  const [hecho, setHecho] = useState<{ mensaje: string; estado: string } | null>(null);
  const previaRef = useRef<HTMLIFrameElement>(null);

  // Carga inicial: plantillas vacías y, si vienen, el borrador a retomar (?borrador=), el recorte (?recorte=) o la pieza del chat.
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const p = await apiNewsletter.plantillas();
        if (!vivo) return;
        setVacios(p.vacios);
        const idBorrador = params.get("borrador");
        const idRecorte = params.get("recorte");
        const pieza = (loc.state as { pieza?: PiezaChat } | null)?.pieza;
        let pl: Plantilla = "mensual";
        let datos: Datos = clonar(p.vacios.mensual);
        if (idBorrador) {
          try {
            const b = await apiNewsletter.borrador(idBorrador);
            pl = b.plantilla;
            datos = b.datos;
            setBorradorId(b.id);
            avisar("Retomaste el borrador: al guardar se actualiza el mismo.", "info");
          } catch (e) {
            setError(e instanceof ErrorApi ? e.message : "No pude abrir ese borrador.");
          }
        } else if (pieza) {
          if (pieza.texto) datos.reflexion = pieza.texto;
          if (pieza.titulo) {
            datos.asunto = pieza.titulo;
            setTema(pieza.titulo);
          }
        }
        if (idRecorte) {
          try {
            const r = await api.recorte(idRecorte);
            datos.video = videoDeRecorte(r);
            avisar("El recorte quedó en el bloque «Un recorte para ver».");
          } catch (e) {
            setError(e instanceof ErrorApi ? e.message : "No pude leer ese recorte.");
          }
        }
        setPlantilla(pl);
        setD(datos);
      } catch (e) {
        if (vivo) setError(e instanceof ErrorApi ? e.message : "No pude conectarme con la API.");
      }
    })();
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Vista previa en vivo: el HTML lo arma la API (newsletter.armar_html) con un pequeño retardo para no pegarle en cada tecla.
  useEffect(() => {
    if (!d) return;
    const ctl = new AbortController();
    setArmando(true);
    const t = window.setTimeout(async () => {
      try {
        const r = await apiNewsletter.html(plantilla, d, ctl.signal);
        setHtml(r.html);
        setTitulo(r.titulo);
        setArmando(false);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setArmando(false);
      }
    }, 350);
    return () => {
      window.clearTimeout(t);
      ctl.abort();
    };
  }, [d, plantilla]);

  const cambiar = useCallback((f: (x: Datos) => void) => {
    setD((prev) => {
      if (!prev) return prev;
      const n = clonar(prev);
      f(n);
      return n;
    });
  }, []);

  function cambiarPlantilla(p: Plantilla) {
    if (!vacios || p === plantilla) return;
    setPlantilla(p);
    setD(clonar(vacios[p]));
    setMateriales([]);
    setBorradorId(null);
    setParams({}, { replace: true });
  }

  async function redactar() {
    if (!d || !tema.trim()) return;
    setRedactando(true);
    setError(null);
    try {
      const r = await apiNewsletter.redactar(plantilla, tema.trim(), d);
      setD(r.datos);
      setMateriales(r.materiales);
      avisar("Listo: el bot redactó los textos. Revisalos y cargá fechas, links y fotos.");
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude redactar.");
    } finally {
      setRedactando(false);
    }
  }

  function descargar() {
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `newsletter-${new Date().toISOString().slice(0, 10)}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
    avisar("HTML descargado: se pega en Perfit.");
  }

  async function guardar(que: "borrador" | "aprobar") {
    if (!d) return;
    setEnviando(que);
    setError(null);
    try {
      if (que === "borrador") {
        const r = await apiNewsletter.guardarBorrador(plantilla, d, borradorId);
        setBorradorId(r.id);
        setParams({ borrador: r.id }, { replace: true });
        avisar(r.mensaje);
      } else {
        const r = await apiNewsletter.aAprobar(plantilla, d, borradorId);
        setHecho({ mensaje: r.mensaje, estado: r.estado });
        setBorradorId(null);
        setParams({}, { replace: true });
      }
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude guardar la pieza.");
    } finally {
      setEnviando(null);
    }
  }

  function reiniciar() {
    if (!vacios) return;
    setD(clonar(vacios[plantilla]));
    setMateriales([]);
    setBorradorId(null);
    setHecho(null);
    setTema("");
    setParams({}, { replace: true });
    setConfirmarReinicio(false);
  }

  function retomar(b: BorradorResumen) {
    setAbrirBorradores(false);
    setHecho(null);
    nav(`/newsletter?borrador=${encodeURIComponent(b.id)}`);
    apiNewsletter
      .borrador(b.id)
      .then((r) => {
        setPlantilla(r.plantilla);
        setD(r.datos);
        setBorradorId(r.id);
        setMateriales([]);
        avisar("Retomaste el borrador: al guardar se actualiza el mismo.", "info");
      })
      .catch((e) => setError(e instanceof ErrorApi ? e.message : "No pude abrir ese borrador."));
  }

  const destinos = useMemo<Destino[]>(() => (d ? destinosDe(plantilla, d) : []), [plantilla, d]);
  const vacioTotal = !!d && !d.asunto && !(d.reflexion || d.encuadre) && !(d.video?.url);

  if (!d || !vacios) {
    return (
      <div className="pagina newsletter" aria-busy="true" aria-label="Cargando el editor">
        {error ? (
          <div className="aviso error">
            <Icono nombre="alerta" tam={18} /> {error}
          </div>
        ) : (
          <>
            <Hueso ancho="40%" alto={26} />
            <Hueso ancho="70%" style={{ margin: "10px 0 18px" }} />
            <div className="nl-grilla">
              <Hueso alto={520} radio={12} />
              <Hueso alto={520} radio={12} />
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="pagina newsletter">
      <header className="pagina-cabecera">
        <div>
          <h1>Newsletter</h1>
          <p className="suave">
            El email a la comunidad, bloque por bloque, con las plantillas reales de la Fundación. El bot redacta los textos desde el material; la agenda, las fotos y los links los cargás vos. El email no sale de acá: el HTML aprobado se pega en Perfit. (Una entrada de la web es un «blogpost» y va por Publicar.)
          </p>
        </div>
        <div className="acciones">
          <button type="button" className="boton" onClick={() => setAbrirBorradores(true)}>
            <Icono nombre="lapiz" tam={16} /> Retomar un borrador
          </button>
          <button type="button" className="boton sutil" onClick={() => (vacioTotal ? reiniciar() : setConfirmarReinicio(true))} title="Vaciar el editor y empezar un newsletter nuevo">
            <Icono nombre="tacho" tam={16} /> Empezar de nuevo
          </button>
        </div>
      </header>

      {hecho && (
        <div className="aviso nl-hecho" role="status">
          <Icono nombre="check" tam={18} />
          <div>
            <strong>Enviado a aprobación.</strong> {hecho.mensaje}
            <div className="acciones">
              <Link className="boton chico" to="/publicaciones">
                <Icono nombre="megafono" tam={15} /> Mis publicaciones
              </Link>
              <button type="button" className="boton chico" onClick={reiniciar}>
                <Icono nombre="mas" tam={15} /> Armar otro
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="nl-arriba tarjeta">
        <div className="nl-plantillas" role="radiogroup" aria-label="Plantilla">
          {(Object.keys(NOMBRE) as Plantilla[]).map((p) => (
            <button key={p} type="button" role="radio" aria-checked={plantilla === p} className={"nl-plantilla" + (plantilla === p ? " activa" : "")} onClick={() => cambiarPlantilla(p)}>
              <strong>{NOMBRE[p]}</strong>
              <span className="chico suave">{DESCRIPCION[p]}</span>
            </button>
          ))}
        </div>
        <div className="nl-redactar">
          <label htmlFor="nl-tema">
            Tema <span className="suave">(para que el bot redacte los textos)</span>
          </label>
          <div className="campo-con-boton">
            <input id="nl-tema" value={tema} onChange={(e) => setTema(e.target.value)} placeholder="ej. la confianza en la vida · los vínculos familiares" onKeyDown={(e) => e.key === "Enter" && redactar()} />
            <button type="button" className="boton primario" onClick={redactar} disabled={!tema.trim() || redactando}>
              {redactando ? <span className="girando" aria-hidden="true" /> : <Icono nombre="chat" tam={16} />} {redactando ? "Buscando material y redactando…" : "Redactar"}
            </button>
          </div>
          {materiales.length > 0 && (
            <details className="nl-materiales">
              <summary>
                <Icono nombre="chevron" tam={14} /> Material que usó el bot ({materiales.length})
              </summary>
              <ul>
                {materiales.map((m, i) => (
                  <li key={i}>
                    <strong>{m.titulo}</strong> · {m.autor} · {m.tag}
                    {m.url && (
                      <>
                        {" "}
                        <a href={m.url} target="_blank" rel="noreferrer">
                          ver
                        </a>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>

      {borradorId && (
        <p className="suave chico nl-retomando">
          <Icono nombre="info" tam={14} /> Estás retomando un borrador: al guardar se actualiza el mismo.
        </p>
      )}
      {error && (
        <div className="aviso error" role="alert">
          <Icono nombre="alerta" tam={18} /> {error}
        </div>
      )}

      <div className="solapas nl-solapas" role="tablist" aria-label="Editor o vista previa">
        <button role="tab" aria-selected={solapa === "editor"} className={"solapa" + (solapa === "editor" ? " activa" : "")} onClick={() => setSolapa("editor")}>
          <Icono nombre="lapiz" tam={15} /> Contenido
        </button>
        <button role="tab" aria-selected={solapa === "previa"} className={"solapa" + (solapa === "previa" ? " activa" : "")} onClick={() => setSolapa("previa")}>
          <Icono nombre="ojo" tam={15} /> Vista previa
        </button>
      </div>

      <div className={"nl-grilla " + solapa}>
        <section className="nl-editor" aria-label="Contenido">
          <Fotos destinos={destinos} onUsar={(destino, url) => cambiar((x) => destino.poner(x, url))} />
          {plantilla === "mensual" ? <EditorMensual d={d} cambiar={cambiar} /> : <EditorRevivi d={d} cambiar={cambiar} />}
          <Bloque titulo="Un recorte para ver (video)" icono="pelicula" abierto={!!d.video?.url}>
            <p className="suave chico">El mail no reproduce video: va la miniatura con el link al recorte (en WordPress) o a YouTube.</p>
            <div className="acciones" style={{ marginTop: 0 }}>
              <button type="button" className="boton chico" onClick={() => setElegirRecorte(true)}>
                <Icono nombre="pelicula" tam={15} /> Elegir uno de mis recortes
              </button>
              {d.video?.url && (
                <button type="button" className="boton chico sutil" onClick={() => cambiar((x) => (x.video = { titulo: "", texto: "", imagen_url: "", url: "" }))}>
                  <Icono nombre="cruz" tam={14} /> Sacar el video
                </button>
              )}
            </div>
            <Campo etiqueta="Título del video" valor={d.video.titulo} onChange={(v) => cambiar((x) => (x.video.titulo = v))} />
            <Campo etiqueta="Una línea de presentación (opcional)" valor={d.video.texto} onChange={(v) => cambiar((x) => (x.video.texto = v))} filas={2} />
            <div className="nl-dos">
              <Campo etiqueta="Link del video" valor={d.video.url} onChange={(v) => cambiar((x) => (x.video.url = v))} placeholder="https://…" />
              <Campo etiqueta="Imagen (miniatura)" valor={d.video.imagen_url} onChange={(v) => cambiar((x) => (x.video.imagen_url = v))} placeholder="URL del banco" />
            </div>
          </Bloque>
        </section>

        <aside className="nl-previa" aria-label="Vista previa del mail">
          <div className="nl-previa-cabecera">
            <div>
              <strong>Vista previa</strong> <span className="suave chico">· así se ve el mail (600 px)</span>
              {armando && <span className="suave chico"> · actualizando…</span>}
            </div>
            <span className="chico suave nl-asunto" title="Asunto del email">
              <Icono nombre="sobre" tam={14} /> {titulo}
            </span>
          </div>
          <div className="nl-mail">
            <iframe ref={previaRef} title="Vista previa del newsletter" srcDoc={html} sandbox="" />
          </div>
        </aside>
      </div>

      <div className="nl-acciones">
        <button type="button" className="boton" onClick={descargar} disabled={!html} title="El HTML completo del mail, para pegarlo en Perfit">
          <Icono nombre="descargar" tam={16} /> Descargar HTML
        </button>
        <button type="button" className="boton" onClick={() => guardar("borrador")} disabled={enviando !== null} title="Guarda todo sin mandar nada; se retoma desde acá o desde Mis publicaciones">
          <Icono nombre="lapiz" tam={16} /> {enviando === "borrador" ? "Guardando…" : borradorId ? "Guardar el borrador" : "Guardar como borrador"}
        </button>
        <button type="button" className="boton primario" onClick={() => guardar("aprobar")} disabled={enviando !== null || !d.asunto.trim()} title={d.asunto.trim() ? "Un aprobador lo revisa; aprobado, el HTML queda listo para Perfit" : "Falta el asunto del email"}>
          <Icono nombre="check" tam={16} /> {enviando === "aprobar" ? "Enviando…" : "Enviar a aprobación"}
        </button>
      </div>

      {abrirBorradores && <Borradores onCerrar={() => setAbrirBorradores(false)} onElegir={retomar} />}
      {elegirRecorte && (
        <ElegirRecorte
          onCerrar={() => setElegirRecorte(false)}
          onElegir={(r) => {
            cambiar((x) => (x.video = videoDeRecorte(r)));
            setElegirRecorte(false);
            avisar("El recorte quedó en el bloque «Un recorte para ver».");
          }}
        />
      )}
      {confirmarReinicio && (
        <Modal titulo="¿Empezar de nuevo?" onCerrar={() => setConfirmarReinicio(false)} peligro>
          <p className="suave">Se vacía el editor. Lo que no guardaste como borrador se pierde.</p>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="boton" onClick={() => setConfirmarReinicio(false)}>
              Cancelar
            </button>
            <button type="button" className="boton peligro" onClick={reiniciar}>
              <Icono nombre="tacho" /> Sí, vaciar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------------- Editores por plantilla (los mismos campos que newsletter_ui) ----------------

function EditorMensual({ d, cambiar }: { d: Datos; cambiar: (f: (x: Datos) => void) => void }) {
  const en = d.encuentro!;
  const rc = d.recursos!;
  const agenda = d.agenda ?? [];
  return (
    <>
      <Bloque titulo="Cabecera y reflexión del mes" icono="sobre" abierto>
        <div className="nl-dos">
          <Campo etiqueta="Mes" valor={d.mes ?? ""} onChange={(v) => cambiar((x) => (x.mes = v))} placeholder="Noviembre" />
          <Campo etiqueta="Asunto del email" valor={d.asunto} onChange={(v) => cambiar((x) => (x.asunto = v))} placeholder="Noviembre: una invitación a…" />
        </div>
        <Campo etiqueta="Imagen de cabecera (URL del banco, 600×160)" valor={d.cabecera_url ?? ""} onChange={(v) => cambiar((x) => (x.cabecera_url = v))} placeholder="https://viviragradecidos.org/wp-content/uploads/…" />
        <Campo etiqueta="Reflexión del mes" ayuda="2 párrafos; el segundo arranca con «Brother David nos enseña que…»" valor={d.reflexion ?? ""} onChange={(v) => cambiar((x) => (x.reflexion = v))} filas={7} />
        <label>Preguntas para la reflexión personal</label>
        {[0, 1, 2].map((i) => (
          <input key={i} className="nl-pregunta" value={d.preguntas?.[i] ?? ""} onChange={(e) => cambiar((x) => ((x.preguntas = [...(x.preguntas ?? ["", "", ""])])[i] = e.target.value))} placeholder={`Pregunta ${i + 1}`} aria-label={`Pregunta ${i + 1}`} />
        ))}
      </Bloque>
      <Bloque titulo="Encuentro destacado" icono="usuarios" abierto={!!en.frase}>
        <Campo etiqueta="Título" valor={en.titulo} onChange={(v) => cambiar((x) => (x.encuentro!.titulo = v))} />
        <Campo etiqueta="Frase (con los verbos en mayúsculas)" valor={en.frase} onChange={(v) => cambiar((x) => (x.encuentro!.frase = v))} />
        <Campo etiqueta="Imagen (URL del banco)" valor={en.imagen_url} onChange={(v) => cambiar((x) => (x.encuentro!.imagen_url = v))} />
        <Campo etiqueta="Texto" valor={en.texto} onChange={(v) => cambiar((x) => (x.encuentro!.texto = v))} filas={3} />
        <div className="nl-dos">
          <Campo etiqueta="Texto del botón" valor={en.boton_texto} onChange={(v) => cambiar((x) => (x.encuentro!.boton_texto = v))} />
          <Campo etiqueta="Link del botón" valor={en.boton_url} onChange={(v) => cambiar((x) => (x.encuentro!.boton_url = v))} />
        </div>
      </Bloque>
      <Bloque titulo={`Agenda del mes (${agenda.filter((a) => a.titulo).length} con título)`} icono="calendario" abierto={agenda.some((a) => a.titulo)}>
        {agenda.map((a, i) => (
          <fieldset key={i} className="nl-actividad">
            <legend>
              Actividad {i + 1}
              <button type="button" className="boton chico sutil" onClick={() => cambiar((x) => x.agenda!.splice(i, 1))} aria-label={`Sacar la actividad ${i + 1}`}>
                <Icono nombre="cruz" tam={13} /> Sacar
              </button>
            </legend>
            <div className="nl-dos">
              <Campo etiqueta="Fecha en chico" valor={a.fecha_corta} onChange={(v) => cambiar((x) => (x.agenda![i].fecha_corta = v))} placeholder="Sábado 8 de noviembre" />
              <Campo etiqueta="Título" valor={a.titulo} onChange={(v) => cambiar((x) => (x.agenda![i].titulo = v))} />
            </div>
            <Campo etiqueta="Descripción (una línea)" valor={a.descripcion} onChange={(v) => cambiar((x) => (x.agenda![i].descripcion = v))} />
            <div className="nl-cuatro">
              <Campo etiqueta="📅 Fecha" valor={a.fecha} onChange={(v) => cambiar((x) => (x.agenda![i].fecha = v))} />
              <Campo etiqueta="🕙 Horario" valor={a.horario} onChange={(v) => cambiar((x) => (x.agenda![i].horario = v))} />
              <Campo etiqueta="💻 Modalidad" valor={a.modalidad} onChange={(v) => cambiar((x) => (x.agenda![i].modalidad = v))} />
              <Campo etiqueta="🌿 Facilitan" valor={a.facilitan} onChange={(v) => cambiar((x) => (x.agenda![i].facilitan = v))} />
            </div>
            <div className="nl-tres">
              <Campo etiqueta="Botón" valor={a.boton_texto} onChange={(v) => cambiar((x) => (x.agenda![i].boton_texto = v))} />
              <Campo etiqueta="Link" valor={a.boton_url} onChange={(v) => cambiar((x) => (x.agenda![i].boton_url = v))} />
              <Campo etiqueta="Imagen (URL)" valor={a.imagen_url} onChange={(v) => cambiar((x) => (x.agenda![i].imagen_url = v))} />
            </div>
          </fieldset>
        ))}
        {agenda.length < 6 && (
          <button type="button" className="boton chico" onClick={() => cambiar((x) => (x.agenda = [...(x.agenda ?? []), actividadVacia()]))}>
            <Icono nombre="mas" tam={14} /> Agregar una actividad
          </button>
        )}
      </Bloque>
      <Bloque titulo="Recursos para profundizar" icono="info" abierto={!!rc.lectura.titulo}>
        <Campo etiqueta="Imagen del bloque (URL)" valor={rc.imagen_url} onChange={(v) => cambiar((x) => (x.recursos!.imagen_url = v))} />
        {(
          [
            ["lectura", "📖 Lectura", "de"],
            ["ecos", "🎧 Ecos (podcast)", "con"],
            ["meditacion", "🧘 Meditación guiada", "con"],
          ] as const
        ).map(([k, rot, lab]) => (
          <div className="nl-tres" key={k}>
            <Campo etiqueta={`${rot}: título`} valor={rc[k].titulo} onChange={(v) => cambiar((x) => (x.recursos![k].titulo = v))} />
            <Campo etiqueta="Link" valor={rc[k].url} onChange={(v) => cambiar((x) => (x.recursos![k].url = v))} />
            <Campo etiqueta={lab} valor={rc[k][lab] ?? ""} onChange={(v) => cambiar((x) => (x.recursos![k][lab] = v))} />
          </div>
        ))}
      </Bloque>
      <Bloque titulo="Cierre y firma" icono="check" abierto={false}>
        <Campo etiqueta="Cierre (frase de deseo para el mes)" valor={d.cierre} onChange={(v) => cambiar((x) => (x.cierre = v))} />
        <Campo etiqueta="Firma" valor={d.firma} onChange={(v) => cambiar((x) => (x.firma = v))} filas={2} />
      </Bloque>
    </>
  );
}

function EditorRevivi({ d, cambiar }: { d: Datos; cambiar: (f: (x: Datos) => void) => void }) {
  const eps = d.episodios ?? [];
  return (
    <>
      <Bloque titulo="Asunto y encuadre" icono="sobre" abierto>
        <Campo etiqueta="Asunto del email" valor={d.asunto} onChange={(v) => cambiar((x) => (x.asunto = v))} placeholder="Reviví: …" />
        <Campo etiqueta="Encuadre del tema (2 oraciones)" valor={d.encuadre ?? ""} onChange={(v) => cambiar((x) => (x.encuadre = v))} filas={3} />
        <Campo etiqueta="Frase de introducción" valor={d.intro ?? ""} onChange={(v) => cambiar((x) => (x.intro = v))} />
      </Bloque>
      {eps.map((ep, i) => (
        <Bloque key={i} titulo={`Episodio ${i + 1}${ep.titulo ? " · " + ep.titulo.slice(0, 40) : ""}`} icono="megafono" abierto={!ep.titulo}>
          <Campo etiqueta="Título (en mayúsculas)" valor={ep.titulo} onChange={(v) => cambiar((x) => (x.episodios![i].titulo = v))} />
          <Campo etiqueta="Presentación (2-3 oraciones, con el nombre del invitado)" valor={ep.texto} onChange={(v) => cambiar((x) => (x.episodios![i].texto = v))} filas={3} />
          <div className="nl-dos">
            <Campo etiqueta="Link al episodio" valor={ep.url} onChange={(v) => cambiar((x) => (x.episodios![i].url = v))} />
            <Campo etiqueta="Foto del invitado (URL del banco)" valor={ep.imagen_url} onChange={(v) => cambiar((x) => (x.episodios![i].imagen_url = v))} />
          </div>
        </Bloque>
      ))}
      <Bloque titulo="Cierre y firma" icono="check" abierto={false}>
        <Campo etiqueta="Frase destacada de cierre (va en mayúsculas)" valor={d.cierre_destacado ?? ""} onChange={(v) => cambiar((x) => (x.cierre_destacado = v))} />
        <Campo etiqueta="Cierre" valor={d.cierre} onChange={(v) => cambiar((x) => (x.cierre = v))} filas={3} />
        <Campo etiqueta="Firma" valor={d.firma} onChange={(v) => cambiar((x) => (x.firma = v))} filas={2} />
      </Bloque>
    </>
  );
}

// ---------------- Piezas chicas ----------------

function Bloque({ titulo, icono, abierto, children }: { titulo: string; icono: string; abierto: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(abierto);
  useEffect(() => {
    if (abierto) setOpen(true);
  }, [abierto]);
  return (
    <details className="nl-bloque tarjeta" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre={icono} tam={17} /> <span>{titulo}</span>
      </summary>
      <div className="nl-bloque-cuerpo">{children}</div>
    </details>
  );
}

function Campo({ etiqueta, ayuda, valor, onChange, filas, placeholder }: { etiqueta: string; ayuda?: string; valor: string; onChange: (v: string) => void; filas?: number; placeholder?: string }) {
  return (
    <label className="nl-campo">
      <span>
        {etiqueta} {ayuda && <span className="suave chico">({ayuda})</span>}
      </span>
      {filas ? <textarea value={valor} onChange={(e) => onChange(e.target.value)} rows={filas} placeholder={placeholder} /> : <input value={valor} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />}
    </label>
  );
}

/** Fotos del banco de WordPress (GET /banco): buscar, elegir dónde va y usar (newsletter_ui._selector_fotos). */
function Fotos({ destinos, onUsar }: { destinos: Destino[]; onUsar: (destino: Destino, url: string) => void }) {
  const [q, setQ] = useState("");
  const [fotos, setFotos] = useState<FotoBanco[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [destino, setDestino] = useState(destinos[0]?.clave ?? "");
  const [abierto, setAbierto] = useState(false);
  const elegido = destinos.find((x) => x.clave === destino) ?? destinos[0];

  async function buscar() {
    setBuscando(true);
    try {
      setFotos(await apiChat.banco(q.trim(), null));
    } catch {
      setFotos([]);
    } finally {
      setBuscando(false);
    }
  }

  return (
    <details className="nl-bloque tarjeta nl-fotos" open={abierto} onToggle={(e) => setAbierto((e.target as HTMLDetailsElement).open)}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre="imagen" tam={17} /> <span>Fotos del banco de WordPress</span>
      </summary>
      <div className="nl-bloque-cuerpo">
        <div className="nl-dos">
          <label>
            Buscar en el banco
            <div className="campo-con-boton">
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ej. amanecer montaña · brother · círculo" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscar())} />
              <button type="button" className="boton" onClick={buscar} disabled={buscando}>
                <Icono nombre="buscar" tam={16} /> {buscando ? "Buscando…" : "Buscar"}
              </button>
            </div>
          </label>
          <label>
            Poner en
            <select value={elegido?.clave ?? ""} onChange={(e) => setDestino(e.target.value)}>
              {destinos.map((x) => (
                <option key={x.clave} value={x.clave}>
                  {x.nombre}
                </option>
              ))}
            </select>
          </label>
        </div>
        {fotos && fotos.length === 0 && !buscando && <p className="suave chico">Nada con esas palabras (o la API no tiene acceso a WordPress). Probá otras, o pegá la URL en el campo del bloque.</p>}
        {fotos && fotos.length > 0 && (
          <div className="pieza-fotos nl-banco">
            {fotos.map((f) => (
              <button key={f.id} type="button" className="pieza-foto" onClick={() => elegido && onUsar(elegido, f.url)} title={`Usar en: ${elegido?.nombre ?? ""}`}>
                <img src={f.miniatura} alt={f.titulo || ""} loading="lazy" />
                <span className="chico">{(f.titulo || `#${f.id}`).slice(0, 28)}</span>
                <span className="chico nl-usar">Usar →</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}

function Borradores({ onCerrar, onElegir }: { onCerrar: () => void; onElegir: (b: BorradorResumen) => void }) {
  const [lista, setLista] = useState<BorradorResumen[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    apiNewsletter
      .borradores()
      .then(setLista)
      .catch((e) => {
        setError(e instanceof ErrorApi ? e.message : "No pude leer los borradores.");
        setLista([]);
      });
  }, []);
  return (
    <Modal titulo="Retomar un borrador de newsletter" onCerrar={onCerrar} ancho={520}>
      {error && <div className="aviso error">{error}</div>}
      {lista === null && <p className="suave">Buscando tus borradores…</p>}
      {lista && lista.length === 0 && !error && <p className="suave">No tenés borradores de newsletter. Los demás borradores están en Mis publicaciones.</p>}
      <ul className="nl-lista-borradores">
        {lista?.map((b) => (
          <li key={b.id}>
            <button type="button" className="nl-borrador" onClick={() => onElegir(b)}>
              <strong>{b.titulo}</strong>
              <span className="suave chico">
                {NOMBRE[b.plantilla] ?? b.plantilla} · guardado {fecha(b.guardado_en || b.creado)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  );
}

function ElegirRecorte({ onCerrar, onElegir }: { onCerrar: () => void; onElegir: (r: Recorte) => void }) {
  const [lista, setLista] = useState<Recorte[] | null>(null);
  useEffect(() => {
    api
      .recortes("mios")
      .then((rs) => setLista(rs.filter((r) => r.estado === "listo" && r.url)))
      .catch(() => setLista([]));
  }, []);
  return (
    <Modal titulo="Elegir un recorte para el newsletter" onCerrar={onCerrar} ancho={560}>
      {lista === null && <p className="suave">Buscando tus recortes…</p>}
      {lista && lista.length === 0 && (
        <p className="suave">
          No tenés recortes listos. Se piden desde el chat y aparecen en <Link to="/recortes">Mis recortes</Link>; desde ahí también está «Llevar al newsletter».
        </p>
      )}
      <ul className="nl-lista-borradores">
        {lista?.map((r) => (
          <li key={r.id}>
            <button type="button" className="nl-borrador nl-recorte" onClick={() => onElegir(r)}>
              {r.miniatura ? <img src={r.miniatura} alt="" /> : <span className="mini-vacia" />}
              <span>
                <strong>{(r.titulo || r.video_id).slice(0, 80)}</strong>
                <span className="suave chico">
                  {r.formato} · {(r.duracion_ms / 1000).toFixed(0)} s
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  );
}

// ---------------- Helpers ----------------

function clonar<T>(x: T): T {
  return JSON.parse(JSON.stringify(x)) as T;
}

function actividadVacia(): Actividad {
  return { fecha_corta: "", titulo: "", descripcion: "", fecha: "", horario: "", modalidad: "", facilitan: "", boton_texto: "INSCRIBITE", boton_url: "", imagen_url: "" };
}

/** Como el botón «Llevar al newsletter» de Streamlit: título del recorte, link al mp4 en WordPress y la miniatura de YouTube. */
function videoDeRecorte(r: Recorte) {
  return { titulo: r.titulo || "", texto: "", imagen_url: r.miniatura || "", url: r.url || "" };
}

/** Dónde puede ir una foto según la plantilla (newsletter_ui._destinos). */
function destinosDe(plantilla: Plantilla, d: Datos): Destino[] {
  if (plantilla === "revivi") {
    return [
      ...(d.episodios ?? []).map((ep, i) => ({ clave: `ep${i}`, nombre: `Episodio ${i + 1}${ep.titulo ? " · " + ep.titulo.slice(0, 25) : ""}`, poner: (x: Datos, u: string) => void (x.episodios![i].imagen_url = u) })),
      { clave: "video", nombre: "Video (recorte)", poner: (x, u) => void (x.video.imagen_url = u) },
    ];
  }
  return [
    { clave: "cab", nombre: "Cabecera", poner: (x, u) => void (x.cabecera_url = u) },
    { clave: "enc", nombre: "Encuentro destacado", poner: (x, u) => void (x.encuentro!.imagen_url = u) },
    ...(d.agenda ?? []).map((a, i) => ({ clave: `ag${i}`, nombre: `Actividad ${i + 1}${a.titulo ? " · " + a.titulo.slice(0, 25) : ""}`, poner: (x: Datos, u: string) => void (x.agenda![i].imagen_url = u) })),
    { clave: "rec", nombre: "Recursos", poner: (x, u) => void (x.recursos!.imagen_url = u) },
    { clave: "video", nombre: "Video (recorte)", poner: (x, u) => void (x.video.imagen_url = u) },
  ];
}

function fecha(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" }) + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}
