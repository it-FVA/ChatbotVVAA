// Publicar (22/10, fase 3): el formulario de tres pasos, con un paso visible a la vez y el resumen de los
// anteriores, la vista previa en vivo (la foto con la frase se compone en la API: POST /publicar/componer) y UN botón principal según
// el rol: «Enviar a aprobación» (creadores) o «Publicar en <canal>» (quien publica directo); secundarios «Ver simulado» y «Guardar
// borrador». Entra desde «Nueva pieza», desde el chat (la pieza propuesta llega en location.state), desde un recorte (?recorte=<id>)
// y desde un borrador (?borrador=<id>). Las reglas de negocio están en la API (api/publicar_rutas.py); acá solo se repiten para
// deshabilitar botones a tiempo.
import { fechaCreacion, fechaIsoDe, fechaLegible, manana } from "../util/fechas";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import type { Recorte } from "../tipos";
import { apiChat } from "../apiChat";
import { apiPublicar } from "../apiPublicar";
import type { FotoBanco, Pieza } from "../tiposChat";
import type { OpcionesPublicar, PiezaForm, RespuestaAprobacion, RespuestaEnvio } from "../tiposPublicar";
import { aviso as textoAviso, desdeGuardada, desdePropuesta, desdeRecorte, formularioVacio } from "../util/publicar";
import VistaPrevia, { type DatosPrevia } from "../componentes/VistaPrevia";
import { Icono } from "../componentes/Iconos";
import { Hueso } from "../componentes/Comunes";
import SubirVideo from "../componentes/SubirVideo";
import { useToast } from "../componentes/Toasts";
import "../publicar.css";

// (2/11) qué se diseña en cada canal, en una línea (Alberto: cada canal con su particularidad)
const AYUDA_CANAL: Record<string, string> = {
  instagram: "Una foto con la frase encima, un reel o una historia. El caption va debajo. Lo publica quien aprueba.",
  facebook: "Un posteo en la página: foto con la frase y el texto. Lo publica quien aprueba, y se puede programar.",
  wordpress: "Una entrada del blog en viviragradecidos.org: título, texto (puede ser largo) y foto destacada. La publica quien aprueba, o la programa para un día.",
  youtube: "Un recorte de video de Mis recortes, con título y descripción. Sube como privado y se revisa en YouTube Studio.",
};

/** (4/11) El rechazo de la pieza que se está corrigiendo, para mostrarlo arriba del formulario. */
type Rechazo = { por: string; en: string | null; nota: string | null };

type Resultado = { tipo: "aprobacion"; r: RespuestaAprobacion } | { tipo: "envio"; r: RespuestaEnvio; modo: "real" | "simulado" } | { tipo: "borrador"; id: string; mensaje: string };

export default function Publicar() {
  const [params] = useSearchParams();
  const loc = useLocation();
  const { avisar } = useToast();
  const [op, setOp] = useState<OpcionesPublicar | null>(null);
  const [form, setForm] = useState<PiezaForm | null>(null);
  const [origen, setOrigen] = useState<"chat" | "recorte" | "borrador" | "copia" | "nueva">("nueva");
  const [copiaDe, setCopiaDe] = useState<string | null>(null); // (4/11) de quién es la pieza que se usa como base
  const [duenaDe, setDuenaDe] = useState<string | null>(null); // (4/11) de quién es el borrador ajeno que se edita en colaboración
  const [rechazo, setRechazo] = useState<Rechazo | null>(null); // (4/11) la pieza que se corrige fue rechazada: quién y con qué nota
  const [error, setError] = useState<string | null>(null);

  // 1) opciones; 2) el formulario según de dónde se entra
  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const o = await apiPublicar.opciones();
        if (!vivo) return;
        setOp(o);
        // (4/11) ?base=<id>: «Usar como base» desde una pieza (propia o compartida): el formulario arranca con una copia y al
        // guardar se crea una pieza nueva de quien la usa; la original no cambia
        const base = params.get("base");
        const borrador = params.get("borrador") || base;
        const recorte = params.get("recorte");
        const pieza = (loc.state as { pieza?: Pieza } | null)?.pieza;
        if (borrador) {
          const p = await apiPublicar.una(borrador);
          if (!vivo) return;
          // (4/11) una pieza ajena con permiso «editar» (por una carpeta compartida) se retoma igual que una propia: es la misma
          const colabora = !base && p.propia === false && p.permiso === "editar";
          setDuenaDe(colabora ? p.usuario || "otra persona" : null);
          // (4/11) una rechazada se corrige en el mismo lugar: la nota del rechazo queda a la vista mientras se corrige
          setRechazo(!base && (p.propia !== false || colabora) && p.rechazada_por && (p.estado === "rechazada" || p.estado === "borrador") ? { por: p.rechazada_por, en: p.rechazada_en, nota: p.nota } : null);
          if (base || (p.propia === false && !colabora)) {
            setCopiaDe(p.propia === false ? p.propuesta_por || p.usuario || "otra persona" : null);
            setForm({ ...desdeGuardada(p.pieza || {}, o), borrador_id: null });
            setOrigen("copia");
          } else if ((p.estado !== "borrador" && p.estado !== "rechazada") || !p.pieza) {
            setError(p.estado === "prueba" ? "Esto fue una prueba (Ver simulado), no un borrador: se abre el formulario con sus datos; si lo guardás, queda como borrador nuevo." : "Esa pieza ya no es un borrador: se abre el formulario con sus datos, pero al guardar se crea una pieza nueva.");
            setForm({ ...desdeGuardada(p.pieza || {}, o), borrador_id: null });
          } else setForm(desdeGuardada(p.pieza, o));
          if (!(base || (p.propia === false && !colabora))) setOrigen("borrador");
        } else if (recorte) {
          const r = await api.recorte(recorte);
          if (!vivo) return;
          if (r.estado !== "listo" || !r.url) setError("Ese recorte todavía no está listo: se puede publicar cuando aparezca el video.");
          setForm(desdeRecorte(r, o));
          setOrigen("recorte");
        } else if (pieza) {
          setForm(desdePropuesta(pieza, o));
          setOrigen("chat");
        } else {
          // (2/11) desde el menú «Canales · Diseñar» se entra con el canal ya elegido
          const canalMenu = params.get("canal");
          setForm({ ...formularioVacio(o), canal: canalMenu && o.canales[canalMenu] ? canalMenu : "" });
          setOrigen("nueva");
        }
      } catch (e) {
        if (vivo) {
          setError(e instanceof ErrorApi ? e.message : "No pude conectarme con la API.");
          setForm((f) => f || formularioVacio(null));
        }
      }
    })();
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("borrador"), params.get("base"), params.get("recorte")]);

  if (!form || !op) {
    if (error)
      return (
        <div className="pagina publicar">
          <header className="pagina-cabecera">
            <h1>Diseñar</h1>
          </header>
          <div className="aviso error" role="alert">
            <Icono nombre="alerta" tam={16} /> <span>{error}</span>
          </div>
          <div className="acciones">
            <button type="button" className="boton" onClick={() => window.location.reload()}>
              Reintentar
            </button>
            <Link className="boton sutil" to="/login">
              Volver a entrar
            </Link>
          </div>
        </div>
      );
    return (
      <div className="pagina publicar" aria-busy="true">
        <header className="pagina-cabecera">
          <h1>Diseñar</h1>
        </header>
        <div className="pub-grilla">
          <div>
            <Hueso ancho="100%" alto={120} radio={12} />
            <Hueso ancho="100%" alto={60} radio={12} style={{ marginTop: 12 }} />
            <Hueso ancho="100%" alto={60} radio={12} style={{ marginTop: 12 }} />
          </div>
          <Hueso ancho="100%" alto={420} radio={12} />
        </div>
      </div>
    );
  }
  return <Formulario key={form.borrador_id || origen} inicial={form} op={op} origen={origen} copiaDe={copiaDe} duenaDe={duenaDe} rechazo={rechazo} avisoInicial={error} avisar={avisar} />;
}

// ---------------------------------------------------------------------------------------------------------------------
function Formulario({ inicial, op, origen, copiaDe = null, duenaDe = null, rechazo = null, avisoInicial, avisar }: { inicial: PiezaForm; op: OpcionesPublicar; origen: string; copiaDe?: string | null; duenaDe?: string | null; rechazo?: Rechazo | null; avisoInicial: string | null; avisar: (t: string, tipo?: "ok" | "error" | "info") => void }) {
  // (2/11, reunión: Alberto) desde «Canales · Diseñar» se entra con el canal ya elegido: la pantalla se centra en ese canal
  // (título, texto de ayuda, el canal fijo en una línea: para otro canal se vuelve al menú)
  const [paramsMenu] = useSearchParams();
  const desdeMenu = !!paramsMenu.get("canal") && origen === "nueva";
  const nav = useNavigate();
  const [f, setF] = useState<PiezaForm>(inicial);
  const [paso, setPaso] = useState<1 | 2 | 3>(inicial.canal && inicial.texto ? (inicial.video_url ? 2 : 2) : 1);
  const [fotos, setFotos] = useState<FotoBanco[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [avisoSubida, setAvisoSubida] = useState<string | null>(null);
  const [urlManual, setUrlManual] = useState(inicial.imagen_url && !inicial.imagen_busqueda ? inicial.imagen_url : "");
  const [compuesta, setCompuesta] = useState<string | null>(null);
  const [componiendo, setComponiendo] = useState(false);
  const [errorCompuesta, setErrorCompuesta] = useState<string | null>(null);
  const [confirmo, setConfirmo] = useState(false);
  const [enviando, setEnviando] = useState<"aprobar" | "real" | "simulado" | "borrador" | null>(null);
  const [error, setError] = useState<string | null>(avisoInicial);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const archivoRef = useRef<HTMLInputElement>(null);

  const set = useCallback(<K extends keyof PiezaForm>(k: K, v: PiezaForm[K]) => setF((x) => ({ ...x, [k]: v })), []);
  // (2/11, Franco) pasar de Facebook a YouTube en el menú cambia el canal de la pieza y conserva título, texto e imagen
  const canalMenu = paramsMenu.get("canal");
  useEffect(() => {
    if (canalMenu && op.canales[canalMenu]) setF((x) => (x.canal === canalMenu ? x : { ...x, canal: canalMenu }));
  }, [canalMenu, op.canales]);
  const canal = f.canal;
  const info = canal ? op.canales[canal] : null;
  const modo = info?.modo ?? "apagado";
  const esRed = canal === "instagram" || canal === "facebook";
  const conVideo = !!f.video_url;
  const conFrase = !!f.texto_imagen.trim();
  const conLogo = f.logo !== "Sin logo";
  const seCompone = esRed && !conVideo && !!f.imagen_url && (conFrase || conLogo) && f.usar_compuesta;
  const fechaIso = fechaIsoDe(f);
  const faltaTexto = !f.texto.trim();
  const faltaTitulo = (canal === "wordpress" || canal === "youtube") && !f.titulo.trim();
  const faltaVideoYT = canal === "youtube" && !conVideo;

  // Banco: busca sola al entrar si hay una sugerencia del bot o el canal es de redes
  const buscarFotos = useCallback(
    async (q: string, elegirPrimera = false) => {
      setBuscando(true);
      try {
        const res = await apiChat.banco(q, canal ? op.formato_por_canal[canal] : null);
        setFotos(res);
        if (elegirPrimera && res.length) set("imagen_url", res[0].url);
      } catch {
        setFotos([]);
      } finally {
        setBuscando(false);
      }
    },
    [canal, op.formato_por_canal, set],
  );
  useEffect(() => {
    if (conVideo || canal === "youtube") return;
    if (fotos === null && (f.imagen_busqueda || esRed)) buscarFotos(f.imagen_busqueda, !!f.imagen_busqueda && !f.imagen_url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canal]);

  // Al cambiar el canal, el formato de la foto arranca en el del canal si no se tocó
  useEffect(() => {
    if (!canal || conVideo) return;
    const sugerido = op.formato_por_canal[canal];
    if (sugerido && origen !== "borrador" && origen !== "copia") set("formato", sugerido);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canal]);

  // La foto compuesta, en vivo: se pide a la API con un pequeño retardo cada vez que cambia algo del diseño
  useEffect(() => {
    if (!seCompone) {
      setCompuesta((u) => {
        if (u) URL.revokeObjectURL(u);
        return null;
      });
      setComponiendo(false);
      return;
    }
    const ctl = new AbortController();
    const t = window.setTimeout(async () => {
      setComponiendo(true);
      setErrorCompuesta(null);
      try {
        const url = await apiPublicar.componer(
          { imagen_url: f.imagen_url, texto_imagen: f.texto_imagen.trim(), firma: f.firma, formato: f.formato, tipografia: f.tipografia, peso: f.peso, posicion: f.posicion, alineacion: f.alineacion, logo: conLogo ? f.logo : null, posicion_logo: f.posicion_logo },
          ctl.signal,
        );
        setCompuesta((u) => {
          if (u) URL.revokeObjectURL(u);
          return url;
        });
      } catch (e) {
        if (!ctl.signal.aborted) setErrorCompuesta(e instanceof ErrorApi ? e.message : "No pude armar la foto con la frase.");
      } finally {
        if (!ctl.signal.aborted) setComponiendo(false);
      }
    }, 450);
    return () => {
      window.clearTimeout(t);
      ctl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seCompone, f.imagen_url, f.texto_imagen, f.firma, f.formato, f.tipografia, f.peso, f.posicion, f.alineacion, f.logo, f.posicion_logo]);

  async function subirArchivo(archivo: File) {
    setSubiendo(true);
    setAvisoSubida(null);
    try {
      const r = await apiPublicar.subirAlBanco(archivo, f.titulo || archivo.name);
      if (r.url) {
        set("imagen_url", r.url);
        setUrlManual("");
        avisar(r.aviso || "Imagen subida al banco.");
      } else setAvisoSubida((r.aviso || "No se pudo subir la imagen.") + " Para Instagram y Facebook la imagen tiene que estar en internet: elegí una del banco o pegá una URL.");
    } catch (e) {
      setAvisoSubida(e instanceof ErrorApi ? e.message : "No pude subir la imagen.");
    } finally {
      setSubiendo(false);
      if (archivoRef.current) archivoRef.current.value = "";
    }
  }

  const previa: DatosPrevia = useMemo(
    () => ({
      canal,
      titulo: f.titulo,
      texto: f.texto,
      imagenSrc: conVideo ? null : seCompone && compuesta ? compuesta : f.imagen_url,
      videoUrl: f.video_url,
      formato: conVideo ? f.vfmt : esRed ? f.formato : null,
      videoFormato: f.video_formato,
      textoImagen: f.texto_imagen,
      fechaIso,
      componiendo: seCompone && componiendo && !compuesta,
    }),
    [canal, f, conVideo, seCompone, compuesta, esRed, fechaIso, componiendo],
  );

  // ---- botones
  const puedeProponer = !!info?.a_aprobar && !op.publica;
  const motivoNoProponer = !canal ? "Elegí el canal." : info && !info.acepta_aprobacion ? `${info.texto_canal} no pasa por aprobación.` : info && !info.a_aprobar ? `${info.texto_canal} está en modo ${info.modo_real}: no hay a dónde mandarla cuando la aprueben. Guardala como borrador.` : null;
  const faltas = [faltaTexto && "falta el texto", faltaTitulo && "falta el título", faltaVideoYT && "falta el video (un recorte)"].filter(Boolean) as string[];
  const etiquetaPrincipal = !canal
    ? "Elegí el canal"
    : op.publica
      ? modo === "real"
        ? `Publicar en ${info!.texto_canal}`
        : modo === "borrador"
          ? "Crear el borrador en WordPress"
          : modo === "privado"
            ? "Subir a YouTube (privado)"
            : `Enviar a ${info!.texto_canal} (simulado)`
      : "Enviar a aprobación";

  async function mandar(que: "aprobar" | "real" | "simulado" | "borrador") {
    setError(null);
    setEnviando(que);
    try {
      if (que === "borrador") {
        const r = await apiPublicar.borrador(f);
        set("borrador_id", r.id);
        avisar("Borrador guardado.");
        setResultado({ tipo: "borrador", id: r.id, mensaje: r.mensaje });
      } else if (que === "aprobar") {
        const r = await apiPublicar.aAprobar(f);
        avisar("Pieza enviada a aprobación.");
        setResultado({ tipo: "aprobacion", r });
      } else {
        const r = await apiPublicar.enviar(f, que);
        if (r.ok) avisar(que === "simulado" ? "Pieza simulada: así quedaría." : r.encolada ? "Quedó en la cola." : "Enviada.");
        else avisar(r.aviso || "No se pudo.", "error");
        setResultado({ tipo: "envio", r, modo: que });
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(null);
    }
  }

  const resumen1 = canal ? [info!.texto_canal, f.titulo ? `«${f.titulo.slice(0, 40)}${f.titulo.length > 40 ? "…" : ""}»` : null, `${f.texto.trim().length} caracteres`].filter(Boolean).join(" · ") : "Sin canal todavía";
  const resumen2 = conVideo
    ? `Recorte ${f.video_formato || ""}${canal === "instagram" ? ` · ${f.vfmt}` : ""}`
    : f.imagen_url
      ? [esRed ? f.formato : null, conFrase && f.usar_compuesta ? "con la frase encima" : "foto sola", conLogo && f.usar_compuesta ? `logo ${f.logo.toLowerCase()}` : null].filter(Boolean).join(" · ")
      : canal === "youtube"
        ? "Sin video"
        : "Sin imagen";
  const resumen3 = fechaIso ? `Programada: ${fechaLegible(fechaIso)}` : "Cuanto antes";

  if (resultado) return <ResultadoPanel resultado={resultado} previa={previa} canal={canal} info={info} ajena={!!duenaDe} onVolver={() => setResultado(null)} onNueva={() => nav("/publicar", { replace: true, state: null })} />;

  return (
    <div className="pagina publicar">
      <header className="pagina-cabecera">
        <div>
          <h1>
            Diseñar{desdeMenu && canal ? <span className="pub-titulo-canal"> · {info?.texto_canal || canal}</span> : null}
          </h1>
          <p className="suave">
            {desdeMenu && canal && (AYUDA_CANAL[canal] ?? "Acá se diseña la pieza: foto, frase, texto y fecha. Publicarla es el paso siguiente, desde Aprobación.")}
            {!desdeMenu && origen === "chat" && "La pieza que propuso el bot, lista para ajustar y mandar."}
            {origen === "recorte" && "Un recorte listo para publicar: elegí el canal y escribí el texto."}
            {origen === "copia" && (copiaDe ? `Una copia de una pieza de ${copiaDe}: ajustala y guardala como tuya. La original no cambia.` : "Una copia de la pieza: al guardar se crea una nueva y la original no cambia.")}
            {origen === "borrador" && rechazo && `Corrigiendo una pieza rechazada${duenaDe ? ` de ${duenaDe}` : ""}. Al guardar queda como borrador en el mismo lugar, con el rechazo en su historial. Al mandarla a aprobación vuelve a la cola${duenaDe ? ` a nombre de ${duenaDe}` : ""}, en la misma carpeta.`}
            {origen === "borrador" && !rechazo && !duenaDe && "Retomando un borrador: al guardar se actualiza el mismo. Al mandarlo a aprobación pasa a la cola en el mismo lugar; al enviarlo directo, el borrador se elimina."}
            {origen === "borrador" && !rechazo && duenaDe && `Editando un borrador de ${duenaDe}, compartido con vos para editar. Al guardar se actualiza el mismo y sigue siendo de ${duenaDe}. Si lo mandás a aprobación, va a su nombre y queda en la misma carpeta.`}
            {!desdeMenu && origen === "nueva" && "Acá se diseña la pieza: foto, frase, texto y fecha. Publicarla es el paso siguiente, desde Aprobación. También se puede diseñar desde el chat, debajo de la respuesta del bot."}
          </p>
        </div>
        <Link to="/publicaciones" className="boton sutil">
          <Icono nombre="lista" tam={16} /> Mis publicaciones
        </Link>
      </header>
      {rechazo && (
        <div className="aviso rechazo-nota" role="note">
          <Icono nombre="cruz" tam={16} />{" "}
          <span>
            <strong>La rechazó {rechazo.por}</strong>
            {rechazo.en ? ` (${fechaCreacion(rechazo.en)})` : ""}
            {rechazo.nota ? <>: «{rechazo.nota}»</> : ". No dejó nota."}
          </span>
        </div>
      )}
      {error && (
        <div className="aviso error" role="alert">
          <Icono nombre="alerta" tam={16} /> <span>{error}</span>
        </div>
      )}

      <div className="pub-grilla">
        <div className="pub-pasos">
          {/* ---------- Paso 1: qué se publica ---------- */}
          <Paso n={1} titulo="Qué se publica" resumen={resumen1} abierto={paso === 1} hecho={!!canal && !faltaTexto && !faltaTitulo} onAbrir={() => setPaso(1)}>
            {conVideo && (
              <div className="pub-video-chip">
                <Icono nombre="pelicula" tam={16} /> Recorte exacto{f.video_formato ? ` · ${f.video_formato}` : ""}. Se publica tal cual está.
              </div>
            )}
            {desdeMenu && canal ? (
              <div className="pub-canal-fijo">
                <span>
                  <strong>{info?.texto_canal || canal}</strong> <span className="suave chico">{info?.detalle}</span>
                  {op.canales[canal] && <span className={"pub-modo chico " + op.canales[canal].modo}> {op.canales[canal].modo}</span>}
                </span>
              </div>
            ) : (
            <fieldset className="pub-canales">
              <legend>Canal</legend>
              {Object.entries(op.canales).map(([clave, i]) => (
                <label key={clave} className={"pub-canal" + (canal === clave ? " activo" : "") + (i.modo === "apagado" ? " apagado" : "")}>
                  <input type="radio" name="canal" value={clave} checked={canal === clave} onChange={() => set("canal", clave)} />
                  <span className="pub-canal-nombre">{i.texto_canal}</span>
                  <span className="pub-canal-detalle chico">{i.detalle}</span>
                  <span className={"pub-modo chico " + i.modo}>{i.modo}</span>
                </label>
              ))}
            </fieldset>
            )}
            {info && (
              <p className={"suave chico pub-modo-texto"}>
                {info.texto_canal} en modo <strong>{info.modo}</strong>: {info.texto.split(":").slice(1).join(":").trim()}
                {!op.publica && info.modo_real !== info.modo && <> (el canal real está en {info.modo_real}: lo que mandes a aprobación sale con ese modo).</>}
              </p>
            )}
            {!desdeMenu && <p className="suave chico">Para el email a la comunidad usá «Email» (o «Newsletter») en el menú: tiene sus plantillas y su vista previa.</p>}
            <label>
              Título <span className="suave">{canal === "wordpress" || canal === "youtube" ? "(obligatorio)" : "(opcional, para el registro)"}</span>
              <input value={f.titulo} onChange={(e) => set("titulo", e.target.value)} maxLength={150} />
            </label>
            <label>
              Texto de la pieza <span className="suave">{esRed ? "(el caption)" : canal === "youtube" ? "(la descripción del video)" : canal === "wordpress" ? "(el cuerpo; se puede usar HTML simple o markdown)" : ""}</span>
              <textarea value={f.texto} onChange={(e) => set("texto", e.target.value)} rows={9} placeholder="Escribí la pieza o pedísela al bot en el chat." />
              <span className="suave chico pub-contador">
                {f.texto.length} caracteres{esRed && f.texto.length > 2200 ? " · Instagram corta el caption en 2200" : ""}
              </span>
            </label>
            <div className="acciones">
              <button type="button" className="boton primario" onClick={() => setPaso(2)} disabled={!canal}>
                Siguiente: {conVideo ? "formato del video" : canal === "youtube" ? "el video" : "foto y diseño"} <Icono nombre="chevron" tam={16} />
              </button>
            </div>
          </Paso>

          {/* ---------- Paso 2: foto y diseño / formato del video ---------- */}
          <Paso n={2} titulo={conVideo ? "Formato del video" : canal === "youtube" ? "Video" : "Foto y diseño"} resumen={resumen2} abierto={paso === 2} hecho={paso > 2} onAbrir={() => canal && setPaso(2)} deshabilitado={!canal}>
            {conVideo ? (
              <>
                {canal === "instagram" && (
                  <fieldset className="opciones">
                    <legend>Formato en Instagram</legend>
                    <label className="radio">
                      <input type="radio" name="vfmt" checked={f.vfmt === "reel"} onChange={() => set("vfmt", "reel")} />
                      <span>
                        <strong>Reel</strong> <span className="suave">sale en el feed y en Reels, con caption</span>
                      </span>
                    </label>
                    <label className="radio">
                      <input type="radio" name="vfmt" checked={f.vfmt === "historia"} onChange={() => set("vfmt", "historia")} />
                      <span>
                        <strong>Historia</strong> <span className="suave">dura 24 h y no lleva caption (Instagram no lo permite por API)</span>
                      </span>
                    </label>
                    {f.video_formato === "horizontal" && <p className="suave chico">Este recorte es horizontal. En Instagram se ve mejor el vertical (pedilo desde la misma tarjeta del chat).</p>}
                  </fieldset>
                )}
                {canal === "youtube" && <p className="suave">Va al canal como video{f.video_formato === "vertical" ? " corto (short)" : ""}. Título obligatorio.</p>}
                {canal === "wordpress" && <p className="suave">Blogpost: el recorte va al principio de la entrada y el texto es el cuerpo. Título obligatorio.</p>}
                {canal === "facebook" && <p className="suave">Va como video en la página de Facebook, con el texto como descripción.</p>}
              </>
            ) : (
              <>
                {canal === "youtube" ? (
                  // (2/11, Franco) el video se elige acá mismo: los recortes listos, con link al editor
                  <ElegirRecorte
                    onElegir={(r) => setF((x) => ({ ...x, titulo: x.titulo || (r.titulo || "").slice(0, 100), video_url: r.url, video_formato: r.formato, vfmt: "reel" }))}
                  />
                ) : (
                  <>
                    {esRed && (
                      <label>
                        Texto sobre la imagen <span className="suave">(la frase que va encima de la foto; no se publica como caption)</span>
                        <input value={f.texto_imagen} onChange={(e) => set("texto_imagen", e.target.value)} maxLength={400} placeholder="ej. La gratitud es la llave de la alegría" />
                      </label>
                    )}
                    <div className="pub-banco">
                      <label htmlFor="pub-busq">Imagen {canal === "wordpress" ? "(la destacada de la entrada)" : ""}</label>
                      <div className="pieza-banco-buscar">
                        <input id="pub-busq" value={f.imagen_busqueda} onChange={(e) => set("imagen_busqueda", e.target.value)} placeholder="Buscar en el banco de WordPress: ej. amanecer montaña calma" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscarFotos(f.imagen_busqueda))} />
                        <button type="button" className="boton" onClick={() => buscarFotos(f.imagen_busqueda)} disabled={buscando}>
                          <Icono nombre="buscar" tam={16} /> {buscando ? "Buscando…" : "Buscar"}
                        </button>
                      </div>
                      <div className="pieza-fotos" role="radiogroup" aria-label="Elegí una foto">
                        <button type="button" className={"pieza-foto sin" + (f.imagen_url === null ? " elegida" : "")} onClick={() => (set("imagen_url", null), setUrlManual(""))} role="radio" aria-checked={f.imagen_url === null}>
                          Sin imagen
                        </button>
                        {f.imagen_url && !fotos?.some((x) => x.url === f.imagen_url) && (
                          <button type="button" className="pieza-foto elegida" role="radio" aria-checked="true" title={f.imagen_url}>
                            <img src={f.imagen_url} alt="" loading="lazy" />
                            <span className="chico">la elegida</span>
                          </button>
                        )}
                        {fotos?.map((x) => (
                          <button key={x.id} type="button" className={"pieza-foto" + (f.imagen_url === x.url ? " elegida" : "")} onClick={() => (set("imagen_url", x.url), setUrlManual(""))} role="radio" aria-checked={f.imagen_url === x.url} title={x.titulo || `#${x.id}`}>
                            <img src={x.miniatura} alt={x.titulo || ""} loading="lazy" />
                            <span className="chico">{(x.titulo || `#${x.id}`).slice(0, 28)}</span>
                          </button>
                        ))}
                        {buscando && fotos === null && [1, 2, 3].map((i) => <Hueso key={i} ancho={112} alto={132} radio={10} />)}
                      </div>
                      {fotos && fotos.length === 0 && !buscando && <p className="suave chico">El banco no tiene nada para esa búsqueda (o la API no tiene acceso a WordPress). Probá otras palabras, o cargá una excepción abajo.</p>}
                      <details className="pub-otra">
                        <summary>Otra imagen (URL o archivo): excepción</summary>
                        <label>
                          URL de una imagen que ya está en internet
                          <input value={urlManual} onChange={(e) => setUrlManual(e.target.value)} onBlur={() => urlManual.trim() && set("imagen_url", urlManual.trim())} placeholder="https://…" inputMode="url" />
                        </label>
                        <label>
                          …o subí un archivo <span className="suave">(va al banco de WordPress)</span>
                          <input ref={archivoRef} type="file" accept="image/jpeg,image/png,image/webp" disabled={subiendo} onChange={(e) => e.target.files?.[0] && subirArchivo(e.target.files[0])} />
                        </label>
                        {subiendo && <p className="suave chico">Subiendo a la biblioteca de WordPress…</p>}
                        {avisoSubida && <div className="aviso chico">{avisoSubida}</div>}
                      </details>
                    </div>

                    {esRed && f.imagen_url && (
                      <div className="pub-diseno">
                        <h3>{conFrase ? "Con la frase encima" : "Formato y logo"}</h3>
                        <div className="pub-fila">
                          <label>
                            Formato
                            <select value={f.formato} onChange={(e) => set("formato", e.target.value)}>
                              {Object.entries(op.formatos).map(([k, [w, h]]) => (
                                <option key={k} value={k}>
                                  {k} ({w}×{h})
                                </option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Logo
                            <select value={f.logo} onChange={(e) => set("logo", e.target.value)}>
                              {op.logos.map((l) => (
                                <option key={l}>{l}</option>
                              ))}
                            </select>
                          </label>
                          <label>
                            Posición del logo
                            <select value={f.posicion_logo} onChange={(e) => set("posicion_logo", e.target.value)} disabled={!conLogo}>
                              {op.posiciones_logo.map((l) => (
                                <option key={l}>{l}</option>
                              ))}
                            </select>
                          </label>
                        </div>
                        {conFrase && (
                          <div className="pub-fila">
                            <label>
                              Firma
                              <input value={f.firma} onChange={(e) => set("firma", e.target.value)} maxLength={60} />
                            </label>
                            <label>
                              Tipografía
                              <select value={f.tipografia} onChange={(e) => set("tipografia", e.target.value)}>
                                {op.tipografias.map((l) => (
                                  <option key={l}>{l}</option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Peso
                              <select value={f.peso} onChange={(e) => set("peso", e.target.value)}>
                                {op.pesos.map((l) => (
                                  <option key={l}>{l}</option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Posición del texto
                              <select value={f.posicion} onChange={(e) => set("posicion", e.target.value)}>
                                {op.posiciones.map((l) => (
                                  <option key={l}>{l}</option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Alineación
                              <select value={f.alineacion} onChange={(e) => set("alineacion", e.target.value)}>
                                {op.alineaciones.map((l) => (
                                  <option key={l}>{l}</option>
                                ))}
                              </select>
                            </label>
                          </div>
                        )}
                        {(conFrase || conLogo) && (
                          <label className="casilla">
                            <input type="checkbox" checked={f.usar_compuesta} onChange={(e) => set("usar_compuesta", e.target.checked)} /> Publicar así (la foto con {conFrase ? "la frase" : "el logo"} encima). Si lo destildás, se publica la foto sola y el texto queda solo en el registro.
                          </label>
                        )}
                        {canal === "instagram" && f.formato === "historia" && <p className="suave chico">Historia de Instagram: dura 24 h y no lleva caption. El texto de la pieza queda solo en el registro.{!(conFrase || conLogo) || !f.usar_compuesta ? " La foto sale tal cual; si no es vertical 9:16, Instagram la recorta." : ""}</p>}
                        {errorCompuesta && <div className="aviso error chico">{errorCompuesta}</div>}
                      </div>
                    )}
                  </>
                )}
              </>
            )}
            <div className="acciones">
              <button type="button" className="boton" onClick={() => setPaso(1)}>
                Volver
              </button>
              <button type="button" className="boton primario" onClick={() => setPaso(3)}>
                Siguiente: cuándo y enviar <Icono nombre="chevron" tam={16} />
              </button>
            </div>
          </Paso>

          {/* ---------- Paso 3: cuándo y enviar ---------- */}
          <Paso n={3} titulo="Cuándo y enviar" resumen={resumen3} abierto={paso === 3} hecho={false} onAbrir={() => canal && setPaso(3)} deshabilitado={!canal}>
            <Programar f={f} set={set} />
            {canal && info && (
              <div className={"pub-aviso " + modo}>
                <Icono nombre={modo === "real" ? "alerta" : "info"} tam={16} />
                <span>{textoAviso(info, fechaIso)}</span>
              </div>
            )}
            {op.publica && modo === "real" && (
              <label className="casilla">
                <input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Entiendo que esto publica de verdad.
              </label>
            )}
            {!op.publica && <p className="suave chico">Creador de contenido: lo mandás a aprobación y lo revisa {op.aprobadores.join(", ") || "un aprobador"}. «Ver simulado» solo muestra cómo quedaría.</p>}
            {faltas.length > 0 && canal && (
              <p className="suave chico">
                <Icono nombre="alerta" tam={14} /> Antes de enviar: {faltas.join(", ")}.
              </p>
            )}
            <div className="acciones pub-enviar">
              {op.publica ? (
                <button type="button" className="boton primario grande" onClick={() => mandar("real")} disabled={enviando !== null || !canal || modo === "apagado" || faltas.length > 0 || (modo === "real" && !confirmo)} title={modo === "real" && !confirmo ? "Marcá «Entiendo que esto publica de verdad»." : undefined}>
                  <Icono nombre="enviar" /> {enviando === "real" ? "Enviando…" : etiquetaPrincipal}
                </button>
              ) : (
                <button type="button" className="boton primario grande" onClick={() => mandar("aprobar")} disabled={enviando !== null || !puedeProponer || faltas.length > 0} title={motivoNoProponer || undefined}>
                  <Icono nombre="check" /> {enviando === "aprobar" ? "Enviando…" : etiquetaPrincipal}
                </button>
              )}
              <button type="button" className="boton" onClick={() => mandar("simulado")} disabled={enviando !== null || !canal || modo === "apagado" || faltaTexto || faltaTitulo} title="Arma la pieza tal cual saldría y la muestra. No manda nada; queda como prueba en el registro.">
                <Icono nombre="ojo" /> {enviando === "simulado" ? "Armando…" : "Ver simulado"}
              </button>
              <button type="button" className="boton" onClick={() => mandar("borrador")} disabled={enviando !== null || !canal} title="Guarda todo sin mandar nada; se retoma desde Mis publicaciones.">
                <Icono nombre="lapiz" /> {enviando === "borrador" ? "Guardando…" : f.borrador_id ? "Actualizar el borrador" : "Guardar borrador"}
              </button>
            </div>
            {!op.publica && motivoNoProponer && canal && <p className="suave chico">{motivoNoProponer}</p>}
          </Paso>
        </div>

        <aside className="pub-previa">
          <div className="pub-previa-cabecera">
            <h2>
              <Icono nombre="ojo" tam={16} /> Así se vería
            </h2>
            {info && <span className={"pub-modo " + modo}>{info.texto_canal} · {modo}</span>}
          </div>
          <VistaPrevia d={previa} />
          {seCompone && !f.usar_compuesta && <p className="suave chico">Se publica la foto sola.</p>}
        </aside>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
function Paso({ n, titulo, resumen, abierto, hecho, deshabilitado = false, onAbrir, children }: { n: number; titulo: string; resumen: string; abierto: boolean; hecho: boolean; deshabilitado?: boolean; onAbrir: () => void; children: React.ReactNode }) {
  return (
    <section className={"pub-paso" + (abierto ? " abierto" : "") + (deshabilitado ? " deshabilitado" : "")} aria-labelledby={`paso-${n}`}>
      <button type="button" className="pub-paso-cabecera" onClick={onAbrir} disabled={deshabilitado || abierto} aria-expanded={abierto}>
        <span className={"pub-paso-num" + (hecho && !abierto ? " hecho" : "")}>{hecho && !abierto ? <Icono nombre="check" tam={14} /> : n}</span>
        <span className="pub-paso-textos">
          <span id={`paso-${n}`} className="pub-paso-titulo">
            {titulo}
          </span>
          {!abierto && <span className="pub-paso-resumen suave chico">{resumen}</span>}
        </span>
        {!abierto && !deshabilitado && (
          <span className="pub-paso-editar chico">
            <Icono nombre="lapiz" tam={14} /> Editar
          </span>
        )}
      </button>
      {abierto && <div className="pub-paso-cuerpo">{children}</div>}
    </section>
  );
}

/** (2/11, Franco) Elegir un recorte listo sin salir de Diseñar: los míos y los del equipo, con miniatura y link al editor. */
function ElegirRecorte({ onElegir }: { onElegir: (r: Recorte) => void }) {
  const [lista, setLista] = useState<Recorte[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState(false); // (5/11) «o subí un video»
  useEffect(() => {
    let vivo = true;
    Promise.all([api.recortes("mios"), api.recortes("equipo").catch(() => [] as Recorte[])])
      .then(([mios, equipo]) => {
        if (!vivo) return;
        const vistos = new Set<string>();
        const todos = [...mios, ...equipo].filter((r) => r.estado === "listo" && r.url && !vistos.has(r.id) && vistos.add(r.id));
        setLista(todos);
      })
      .catch((e) => vivo && setError(e instanceof ErrorApi ? e.message : "No pude traer los recortes."));
    return () => {
      vivo = false;
    };
  }, []);
  return (
    <div className="pub-recortes">
      <p className="suave chico">
        El video es un recorte ya listo. Elegí uno; para ajustarlo (tramo, subtítulos, pausas) abrilo en el editor desde <Link to="/recortes">Mis recortes</Link>.{" "}
        <button type="button" className="boton sutil chico" onClick={() => setSubiendo(true)}>o subí un video</button>
      </p>
      {subiendo && (
        <SubirVideo
          onCerrar={() => setSubiendo(false)}
          onSubido={async (id) => {
            setSubiendo(false);
            const r = id ? await api.recorte(id).catch(() => null) : null;
            if (r) onElegir(r);
          }}
        />
      )}
      {error && <div className="aviso error">{error}</div>}
      {lista === null && !error && (
        <div className="pieza-fotos">
          {[1, 2, 3].map((i) => (
            <Hueso key={i} ancho={160} alto={120} radio={10} />
          ))}
        </div>
      )}
      {lista && lista.length === 0 && (
        <p className="suave chico">
          No hay recortes listos. Pedí uno desde el chat (el bot propone recortes de los videos) o desde <Link to="/recortes">Mis recortes</Link>; tardan unos 15 minutos.
        </p>
      )}
      {lista && lista.length > 0 && (
        <div className="pieza-fotos pub-recortes-lista" role="list">
          {lista.map((r) => (
            <div key={r.id} className="pieza-foto pub-recorte" role="listitem">
              {r.miniatura ? <img src={r.miniatura} alt="" loading="lazy" /> : r.subido && r.url ? <video src={r.url} preload="metadata" muted playsInline /> : <div className="pub-recorte-sin" />}
              <span className="chico pub-recorte-titulo" title={r.titulo || ""}>{(r.titulo || "(sin título)").slice(0, 48)}</span>
              <span className="suave chico">
                {r.formato} · {Math.round((r.fin_ms - r.inicio_ms) / 1000)} s{r.propio ? "" : " · del equipo"}
              </span>
              <span className="pub-recorte-acciones">
                <button type="button" className="boton primario chico" onClick={() => onElegir(r)}>
                  Usar este
                </button>
                {!r.subido && (
                  <Link to={`/recortes/${r.id}`} className="boton sutil chico" title="Abrir en el editor de recortes">
                    Editar
                  </Link>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Programar({ f, set }: { f: PiezaForm; set: <K extends keyof PiezaForm>(k: K, v: PiezaForm[K]) => void }) {
  const programar = !!f.fecha;
  const hoy = new Date();
  const enDias = (n: number, h = "09:00") => {
    const d = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate() + n);
    set("fecha", `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`);
    set("hora", h);
  };
  const proximoLunes = ((8 - hoy.getDay()) % 7) || 7;
  return (
    <div className="pub-programar">
      <div className="pub-cuando" role="radiogroup" aria-label="Cuándo sale">
        <label className={"pub-cuando-op" + (!programar ? " activo" : "")}>
          <input type="radio" name="cuando" checked={!programar} onChange={() => set("fecha", null)} />
          <Icono nombre="enviar" tam={16} /> Cuanto antes
        </label>
        <label className={"pub-cuando-op" + (programar ? " activo" : "")}>
          <input type="radio" name="cuando" checked={programar} onChange={() => (set("fecha", manana()), set("hora", f.hora || "09:00"))} />
          <Icono nombre="calendario" tam={16} /> Programar para una fecha
        </label>
      </div>
      {programar && (
        <div className="pub-fecha">
          <label>
            Día
            <input type="date" value={f.fecha || ""} min={`${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-${String(hoy.getDate()).padStart(2, "0")}`} onChange={(e) => set("fecha", e.target.value || null)} />
          </label>
          <label>
            Hora <span className="suave">(Argentina)</span>
            <input type="time" value={f.hora || "09:00"} onChange={(e) => set("hora", e.target.value)} step={300} />
          </label>
          <div className="pub-atajos-fecha">
            <button type="button" className="boton chico" onClick={() => enDias(1)}>
              Mañana 9:00
            </button>
            <button type="button" className="boton chico" onClick={() => enDias(1, "18:00")}>
              Mañana 18:00
            </button>
            <button type="button" className="boton chico" onClick={() => enDias(proximoLunes)}>
              Lunes 9:00
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
function ResultadoPanel({ resultado, previa, canal, info, ajena = false, onVolver, onNueva }: { resultado: Resultado; previa: DatosPrevia; canal: string; info: { texto_canal: string } | null; ajena?: boolean; onVolver: () => void; onNueva: () => void }) {
  // (4/11) la pieza de otra persona editada en colaboración no está en «Mis publicaciones» de quien la editó: se abre la pieza
  const idPieza = resultado.tipo === "borrador" ? resultado.id : (resultado.r as { id?: string | null }).id;
  const nombre = info?.texto_canal || canal;
  let ok = true;
  let titulo = "";
  let detalle: string | undefined;
  let avisos: string[] = [];
  const links: { texto: string; url: string }[] = [];
  let mostrarPrevia = false;
  let imagenFinal: string | null = null;
  if (resultado.tipo === "borrador") {
    titulo = "Borrador guardado";
    detalle = resultado.mensaje;
  } else if (resultado.tipo === "aprobacion") {
    titulo = "Enviada a aprobación";
    detalle = resultado.r.mensaje;
    avisos = resultado.r.avisos;
    imagenFinal = resultado.r.imagen_url;
    mostrarPrevia = true;
  } else {
    const r = resultado.r;
    ok = r.ok;
    titulo = !r.ok ? "No se pudo" : r.encolada ? "Quedó en la cola" : r.simulado ? `Así quedaría en ${nombre}` : r.modo === "borrador" ? "Borrador creado en WordPress" : `Enviada a ${nombre}`;
    detalle = r.aviso;
    avisos = r.avisos;
    imagenFinal = r.imagen_url;
    mostrarPrevia = r.simulado || !!r.pieza;
    if (r.link_editar) links.push({ texto: "Abrir el borrador en WordPress", url: r.link_editar });
    if (r.link && canal === "youtube") links.push({ texto: "Ver el video en YouTube", url: r.link });
    if (r.link && canal === "wordpress" && !r.link_editar) links.push({ texto: "Ver la entrada", url: r.link });
    if (r.permalink) links.push({ texto: "Ver la publicación", url: r.permalink });
  }
  return (
    <div className="pagina publicar">
      <header className="pagina-cabecera">
        <h1>Diseñar</h1>
      </header>
      <div className={"pub-resultado" + (ok ? "" : " error")} role="status">
        <div className="pub-resultado-cabecera">
          <Icono nombre={ok ? "check" : "alerta"} tam={22} />
          <h2>{titulo}</h2>
        </div>
        {detalle && <p>{detalle}</p>}
        {avisos.map((a, i) => (
          <div key={i} className="aviso chico">
            <Icono nombre="alerta" tam={14} /> {a}
          </div>
        ))}
        {links.length > 0 && (
          <div className="acciones">
            {links.map((l) => (
              <a key={l.url} className="boton" href={l.url} target="_blank" rel="noreferrer">
                <Icono nombre="externo" tam={16} /> {l.texto}
              </a>
            ))}
          </div>
        )}
        <div className="acciones">
          {ajena ? (
            <Link className="boton primario" to={idPieza ? `/publicaciones/${encodeURIComponent(idPieza)}` : "/compartidos"}>
              <Icono nombre="lista" tam={16} /> {idPieza ? "Ver la pieza" : "Volver a Compartidos conmigo"}
            </Link>
          ) : (
            <Link className="boton primario" to="/publicaciones">
              <Icono nombre="lista" tam={16} /> Ver en Mis publicaciones
            </Link>
          )}
          {resultado.tipo === "borrador" || !ok ? (
            <button type="button" className="boton" onClick={onVolver}>
              <Icono nombre="lapiz" tam={16} /> Seguir editando
            </button>
          ) : (
            <button type="button" className="boton" onClick={onVolver}>
              <Icono nombre="deshacer" tam={16} /> Volver al formulario
            </button>
          )}
          <button type="button" className="boton sutil" onClick={onNueva}>
            <Icono nombre="mas" tam={16} /> Nueva pieza
          </button>
        </div>
      </div>
      {mostrarPrevia && (
        <div className="pub-resultado-previa">
          <h3 className="suave">Así quedaría en {nombre}</h3>
          <VistaPrevia d={{ ...previa, imagenSrc: previa.imagenSrc || imagenFinal }} compacta />
        </div>
      )}
    </div>
  );
}
