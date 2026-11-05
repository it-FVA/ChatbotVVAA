// Publicar (22/10, fase 3): el formulario de tres pasos, con un paso visible a la vez y el resumen de los
// anteriores, la vista previa en vivo (la foto con la frase se compone en la API: POST /publicar/componer) y UN botón principal según
// el rol: «Enviar a aprobación» para todos los roles (desde el 5/11 nadie publica directo, ni aprobadores ni admins); secundarios «Ver simulado» y «Guardar
// borrador». Entra desde «Nueva pieza», desde el chat (la pieza propuesta llega en location.state), desde un recorte (?recorte=<id>)
// y desde un borrador (?borrador=<id>). Las reglas de negocio están en la API (api/publicar_rutas.py); acá solo se repiten para
// deshabilitar botones a tiempo.
import Cabecera from "../componentes/Cabecera";
import { definirAyuda } from "../ayuda/registro";
import { fechaCreacion, fechaIsoDe, fechaLegible, manana } from "../util/fechas";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, ErrorApi } from "../api";
import type { Recorte } from "../tipos";
import { apiChat } from "../apiChat";
import { apiPublicar } from "../apiPublicar";
import type { FotoBanco, Pieza } from "../tiposChat";
import { NOMBRE_TIPO_INSTAGRAM, tipoInstagram, tipoInstagramValido, type OpcionesPublicar, type PiezaForm, type RespuestaAprobacion, type RespuestaEnvio, type TipoInstagram } from "../tiposPublicar";
import { aviso as textoAviso, desdeGuardada, desdePropuesta, desdeRecorte, formularioVacio } from "../util/publicar";
import VistaPrevia, { type DatosPrevia } from "../componentes/VistaPrevia";
import { Icono } from "../componentes/Iconos";
import { AvisoBanco, Hueso } from "../componentes/Comunes";
import SubirVideo from "../componentes/SubirVideo";
import { useToast } from "../componentes/Toasts";
import Presencia from "../componentes/Presencia";
import ConflictoGuardado, { esConflictoDeVersion } from "../componentes/ConflictoGuardado";
import { usePresencia } from "../util/usePresencia";
import "../publicar.css";

// (2/11) qué se diseña en cada canal, en una línea (Alberto: cada canal con su particularidad)
const AYUDA_CANAL: Record<string, string> = {
  facebook: "Un posteo en la página: foto con la frase y el texto. Lo publica quien aprueba, y se puede programar.",
  wordpress: "Una entrada del blog en viviragradecidos.org: título, texto (puede ser largo) y foto destacada. La publica quien aprueba, o la programa para un día.",
  youtube: "Un recorte de video de Mis recortes, con título y descripción. Sube como privado y se revisa en YouTube Studio.",
};

// (5/11, Franco) Instagram son tres entradas del menú, cada una con su formulario acotado
const AYUDA_INSTAGRAM: Record<TipoInstagram, string> = {
  posteo: "Una foto cuadrada o vertical con la frase encima, y su caption. Lo publica quien aprueba, y se puede programar.",
  reel: "Un video (un recorte de Mis recortes o uno que subas) con su caption. Sale como reel. Lo publica quien aprueba.",
  historia: "Una foto vertical con la frase encima, o un video vertical. No lleva caption y dura 24 horas. Lo publica quien aprueba.",
};

/** El `?tipo=` del menú se traduce a lo que ya existe en la pieza (formato, vfmt y si hay video): `tipo` no es un campo nuevo. */
function aplicarTipo(x: PiezaForm, t: TipoInstagram): PiezaForm {
  if (t === "posteo") return { ...x, video_url: null, video_formato: null, vfmt: "reel", formato: x.formato === "vertical" ? "vertical" : "cuadrado" };
  if (t === "reel") return { ...x, formato: "vertical", vfmt: "reel" };
  return x.video_url ? { ...x, vfmt: "historia", formato: "historia" } : { ...x, formato: "historia", vfmt: "reel" };
}

/** (4/11) El rechazo de la pieza que se está corrigiendo, para mostrarlo arriba del formulario. */
type Rechazo = { por: string; en: string | null; nota: string | null };

type Resultado = { tipo: "aprobacion"; r: RespuestaAprobacion } | { tipo: "envio"; r: RespuestaEnvio; modo: "real" | "simulado" } | { tipo: "borrador"; id: string; mensaje: string; cambios?: boolean };

// (5/11, Franco) Ayuda de esta pantalla: de acá sale la guía interactiva («¿Cómo se usa?»). Cada id es un data-ayuda="disenar.<id>" en el JSX.
definirAyuda("disenar", {
  titulo: "Diseñar",
  que: "Armás la pieza de un canal. Diseñar no publica: toda pieza va a aprobación. Por canal:",
  lista: [
    "Instagram · Posteo: foto con la frase y caption.",
    "Instagram · Reel: un video, con caption.",
    "Instagram · Historia: foto o video, sin texto, 24 horas.",
    "Facebook: foto con la frase y el texto.",
    "Blogpost: título, texto largo y foto destacada.",
    "YouTube: un recorte, con título. Sube privado.",
    "Email: es el Newsletter.",
  ],
  pasos: [
    { id: "canal", texto: "El canal se elige en la barra.", titulo: "Canal" },
    { id: "presencia", texto: "Acá ves si otra persona mira o edita esta pieza.", titulo: "Quién más está acá" },
    { id: "texto", texto: "Cargá título y texto." },
    { id: "foto", texto: "Elegí foto (banco, compu o link), varias fotos (carrusel) o video (recorte o propio)." },
    { id: "cuando", texto: "Elegí cuándo sale y «Enviar a aprobación», o «Guardar borrador» para seguir luego." },
    { id: "previa", texto: "Mirá la vista previa." },
  ],
});

/** Qué pasa con la pieza cuando el canal no está en real (modo_real del registro de canales). */
// (5/11, Franco) el paso 2 se llama siempre igual; antes cambiaba según lo elegido
const TITULO_PASO_2 = "Qué va en la pieza";
type Camino = "elegir" | "foto" | "varias" | "video";
const MAX_FOTOS = 10; // (5/11, Franco) un carrusel lleva de 2 a 10 fotos
const MIN_FOTOS = 2;

const TEXTO_NO_REAL: Record<string, string> = {
  simulado: "Este canal está en modo de prueba: la pieza se arma pero no sale de verdad.",
  apagado: "Este canal está apagado: la pieza se arma y queda guardada, pero no sale.",
  borrador: "La entrada queda como borrador en WordPress: no se publica sola.",
  privado: "El video sube a YouTube como privado: lo publica quien administra el canal.",
};

export default function Publicar() {
  const [params] = useSearchParams();
  const loc = useLocation();
  const { avisar } = useToast();
  const navParent = useNavigate();
  const [versionBorrador, setVersionBorrador] = useState<string | null>(null); // (5/11) resultado.guardado_en del borrador que se retomó
  const [recarga, setRecarga] = useState(0); // (5/11) «Recargar y ver sus cambios»: vuelve a pedir el borrador y arma el formulario de nuevo
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
            setError(p.estado === "prueba" ? "Esto fue una prueba, no un borrador: se abre el formulario con sus datos; si lo guardás, queda como borrador nuevo." : "Esa pieza ya no es un borrador: se abre el formulario con sus datos, pero al guardar se crea una pieza nueva.");
            setForm({ ...desdeGuardada(p.pieza || {}, o), borrador_id: null });
          } else {
            setForm(desdeGuardada(p.pieza, o));
            setVersionBorrador(p.version ?? null);
          }
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
  }, [params.get("borrador"), params.get("base"), params.get("recorte"), recarga]);

  if (!form || !op) {
    if (error)
      return (
        <div className="pagina publicar">
          <Cabecera titulo="Diseñar" />
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
        <Cabecera titulo="Diseñar" />
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
  const recargar = (id: string) => {
    navParent(`/publicar?borrador=${encodeURIComponent(id)}`, { replace: true });
    setRecarga((n) => n + 1);
  };
  return <Formulario key={`${form.borrador_id || origen}:${recarga}`} inicial={form} op={op} origen={origen} copiaDe={copiaDe} duenaDe={duenaDe} rechazo={rechazo} avisoInicial={error} avisar={avisar} versionInicial={versionBorrador} recargar={recargar} />;
}

// ---------------------------------------------------------------------------------------------------------------------
function Formulario({ inicial, op, origen, copiaDe = null, duenaDe = null, rechazo = null, avisoInicial, avisar, versionInicial = null, recargar }: { inicial: PiezaForm; op: OpcionesPublicar; origen: string; copiaDe?: string | null; duenaDe?: string | null; rechazo?: Rechazo | null; avisoInicial: string | null; avisar: (t: string, tipo?: "ok" | "error" | "info") => void; versionInicial?: string | null; recargar: (id: string) => void }) {
  // (2/11, reunión: Alberto) desde «Canales · Diseñar» se entra con el canal ya elegido: la pantalla se centra en ese canal
  // (título, texto de ayuda, el canal fijo en una línea: para otro canal se vuelve al menú)
  const [paramsMenu] = useSearchParams();
  const desdeMenu = !!paramsMenu.get("canal") && origen === "nueva";
  const nav = useNavigate();
  const [f, setF] = useState<PiezaForm>(inicial);
  // (5/11) presencia y aviso de conflicto: la versión que cargó esta pantalla se manda al guardar; si otra persona guardó antes, la API contesta 409
  const [version, setVersion] = useState<string | null>(versionInicial);
  const [conflicto, setConflicto] = useState<string | null>(null);
  const presentes = usePresencia("pieza", f.borrador_id, "edita");
  const [paso, setPaso] = useState<1 | 2 | 3>(inicial.canal && inicial.texto ? 2 : 1);
  const [fotos, setFotos] = useState<FotoBanco[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [avisoSubida, setAvisoSubida] = useState<string | null>(null);
  const [urlManual, setUrlManual] = useState(inicial.imagen_url && !inicial.imagen_busqueda && !inicial.imagenes?.length ? inicial.imagen_url : "");
  const [compuesta, setCompuesta] = useState<string | null>(null);
  const [componiendo, setComponiendo] = useState(false);
  const [errorCompuesta, setErrorCompuesta] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<"aprobar" | "simulado" | "borrador" | null>(null);
  const [error, setError] = useState<string | null>(avisoInicial);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  // (5/11, Franco) paso 2 con dos caminos: si la pieza ya trae video, imagen o una búsqueda del bot, abre directo en el que corresponde
  // (5/11, Franco) una pieza con `imagenes` (carrusel) abre directo en «Varias fotos» con la lista cargada
  const [camino, setCamino] = useState<Camino>(inicial.video_url ? "video" : inicial.imagenes?.length ? "varias" : inicial.imagen_url || inicial.imagen_busqueda ? "foto" : "elegir");
  const unaFoto = !!inicial.imagen_url && !inicial.imagen_busqueda && !inicial.imagenes?.length;
  const [fuente, setFuente] = useState<"banco" | "archivo" | "url">(unaFoto ? "url" : "banco");
  const [fuenteV, setFuenteV] = useState<"recortes" | "subir">("recortes");
  const [fuenteFoto, setFuenteFoto] = useState<"banco" | "subida" | "link">(unaFoto ? "link" : "banco");
  const [nombreSubida, setNombreSubida] = useState("");
  const [nombreVideo, setNombreVideo] = useState("");
  const [videoParaSubir, setVideoParaSubir] = useState<File | null>(null);

  const set = useCallback(<K extends keyof PiezaForm>(k: K, v: PiezaForm[K]) => setF((x) => ({ ...x, [k]: v })), []);
  // (2/11, Franco) pasar de Facebook a YouTube en el menú cambia el canal de la pieza y conserva título, texto e imagen
  const canalMenu = paramsMenu.get("canal");
  useEffect(() => {
    if (canalMenu && op.canales[canalMenu]) setF((x) => (x.canal === canalMenu ? x : { ...x, canal: canalMenu }));
  }, [canalMenu, op.canales]);
  const canal = f.canal;
  // (5/11) tipo de Instagram: el del menú (?tipo=; sin tipo, Posteo) o, al retomar un borrador o venir del chat, el que se deduce de la pieza
  const tipoUrl = desdeMenu && canalMenu === "instagram" ? tipoInstagramValido(paramsMenu.get("tipo")) ?? "posteo" : null;
  const [tipoElegido, setTipoElegido] = useState<TipoInstagram | null>(tipoUrl);
  const tipoIG: TipoInstagram | null = canal === "instagram" ? tipoElegido ?? tipoInstagram(f) : null;
  const esReel = tipoIG === "reel";
  const esHistoria = tipoIG === "historia";
  // al cambiar de tipo en el menú se conserva el texto escrito (el formulario es el mismo): solo se ajusta formato y video
  useEffect(() => {
    if (!tipoUrl) return;
    setTipoElegido(tipoUrl);
    setF((x) => aplicarTipo(x, tipoUrl));
  }, [tipoUrl]);
  const info = canal ? op.canales[canal] : null;
  const modo = info?.modo ?? "apagado";
  const esRed = canal === "instagram" || canal === "facebook";
  const conVideo = !!f.video_url;
  // (5/11, Franco) carrusel: solo en posteo de Instagram y en Facebook. Mientras se arma, `imagenes` es la lista y `imagen_url` la portada.
  const permiteCarrusel = canal === "facebook" || tipoIG === "posteo";
  const soloVideo = canal === "youtube" || tipoUrl === "reel" || tipoElegido === "reel";
  const caminoEf: Camino = soloVideo ? "video" : camino === "varias" && !permiteCarrusel ? "elegir" : camino;
  const enVarias = caminoEf === "varias";
  const lista = enVarias ? f.imagenes ?? [] : [];
  const nFotos = lista.length;
  const completo = nFotos >= MAX_FOTOS;
  const conFrase = !!f.texto_imagen.trim();
  const conLogo = f.logo !== "Sin logo";
  const seCompone = esRed && !conVideo && !enVarias && !!f.imagen_url && (conFrase || conLogo) && f.usar_compuesta;
  const fechaIso = fechaIsoDe(f);
  const faltaTexto = !f.texto.trim() && !esHistoria; // la historia no lleva caption

  const faltaTitulo = (canal === "wordpress" || canal === "youtube") && !f.titulo.trim();
  const faltaVideoYT = (canal === "youtube" || esReel) && !conVideo;
  const faltaFotoIG = (tipoIG === "posteo" || esHistoria) && !conVideo && !enVarias && !f.imagen_url;
  const faltanFotos = enVarias && nFotos < MIN_FOTOS;
  // (5/11, Franco) el paso 3 espera a que haya foto o video; YouTube y el reel solo llevan video (no hay elección)
  const hayPieza = conVideo || (enVarias ? nFotos > 0 : !!f.imagen_url);

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
    if (caminoEf !== "foto" && caminoEf !== "varias") return;
    if (fotos === null && (f.imagen_busqueda || esRed)) buscarFotos(f.imagen_busqueda, caminoEf === "foto" && !!f.imagen_busqueda && !f.imagen_url);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canal, caminoEf]);

  // Al cambiar el canal, el formato de la foto arranca en el del canal si no se tocó
  useEffect(() => {
    if (!canal || conVideo || tipoUrl) return; // en Instagram el formato lo manda el tipo del menú
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

  // ---- carrusel (5/11, Franco): cada foto elegida se agrega a la lista; la primera es la portada y viaja también como imagen_url
  const conLista = (x: PiezaForm, l: string[]): PiezaForm => ({ ...x, imagenes: l, imagen_url: l[0] ?? null });
  function agregarFoto(url: string) {
    if (nFotos >= MAX_FOTOS) return;
    if (lista.includes(url)) {
      avisar("Esa foto ya está en el carrusel.", "info");
      return;
    }
    setF((x) => ((x.imagenes ?? []).length >= MAX_FOTOS ? x : conLista(x, [...(x.imagenes ?? []), url])));
  }
  const quitarFoto = (k: number) => setF((x) => conLista(x, (x.imagenes ?? []).filter((_, j) => j !== k)));
  const moverFoto = (k: number, d: -1 | 1) =>
    setF((x) => {
      const l = [...(x.imagenes ?? [])];
      const j = k + d;
      if (j < 0 || j >= l.length) return x;
      [l[k], l[j]] = [l[j], l[k]];
      return conLista(x, l);
    });

  function sumarLink() {
    const u = urlManual.trim();
    if (!/^https:\/\/\S+$/i.test(u)) return;
    agregarFoto(u);
    setUrlManual("");
  }

  async function subirArchivo(archivo: File) {
    setSubiendo(true);
    setAvisoSubida(null);
    try {
      const r = await apiPublicar.subirAlBanco(archivo, f.titulo || archivo.name);
      if (r.url) {
        if (enVarias) agregarFoto(r.url);
        else set("imagen_url", r.url);
        setUrlManual("");
        setFuenteFoto("subida");
        setNombreSubida(archivo.name);
        avisar(r.aviso || "Imagen subida al banco.");
      } else setAvisoSubida((r.aviso || "No se pudo subir la imagen.") + " Para Instagram y Facebook la imagen tiene que estar en internet: elegí una del banco o pegá un link.");
    } catch (e) {
      setAvisoSubida(e instanceof ErrorApi ? e.message : "No pude subir la imagen.");
    } finally {
      setSubiendo(false);
    }
  }

  const previa: DatosPrevia = useMemo(
    () => ({
      canal,
      titulo: f.titulo,
      texto: f.texto,
      imagenSrc: conVideo ? null : enVarias ? lista[0] ?? null : seCompone && compuesta ? compuesta : f.imagen_url,
      videoUrl: f.video_url,
      imagenes: enVarias && nFotos >= MIN_FOTOS ? lista : null,
      formato: conVideo ? f.vfmt : esRed ? f.formato : null,
      videoFormato: f.video_formato,
      textoImagen: f.texto_imagen,
      fechaIso,
      componiendo: seCompone && componiendo && !compuesta,
    }),
    [canal, f, conVideo, seCompone, compuesta, esRed, fechaIso, componiendo, enVarias, lista, nFotos],
  );

  // ---- botones
  const puedeProponer = !!info?.a_aprobar;
  const motivoNoProponer = !canal ? "Elegí el canal." : info && !info.acepta_aprobacion ? `${info.texto_canal} no pasa por aprobación.` : info && !info.a_aprobar ? `${info.texto_canal} todavía no está habilitado: guardala como borrador.` : null;
  const faltas = [faltaTexto && "falta el texto", faltaTitulo && "falta el título", faltaVideoYT && "falta el video (un recorte)", faltaFotoIG && "falta la foto", faltanFotos && "faltan fotos para el carrusel", !hayPieza && !enVarias && !faltaVideoYT && !faltaFotoIG && "falta la foto o el video"].filter(Boolean) as string[];
  const etiquetaPrincipal = !canal ? "Elegí el canal" : "Enviar a aprobación"; // (5/11) nadie publica directo: todo pasa por aprobación

  async function mandar(que: "aprobar" | "simulado" | "borrador", pisar = false) {
    setError(null);
    setEnviando(que);
    // (5/11) lo que viaja es la pieza de siempre: el tipo se traduce a formato y vfmt. La historia no lleva caption, pero la API pide
    // texto: si no hay, va la frase (o el título) y la API igual la manda sin texto.
    let pz: PiezaForm = f;
    // (5/11, Franco) un carrusel no lleva frase, logo ni formato; con menos de 2 fotos (un borrador a medias) viaja como una foto sola
    if (enVarias) pz = { ...pz, imagenes: nFotos >= MIN_FOTOS ? lista : null, imagen_url: lista[0] ?? null, video_url: null, video_formato: null, texto_imagen: "", usar_compuesta: false };
    if (esReel) pz = { ...pz, formato: "vertical", vfmt: "reel" };
    if (esHistoria) pz = pz.video_url ? { ...pz, vfmt: "historia", formato: "historia" } : { ...pz, formato: "historia" };
    if (esHistoria && que !== "borrador" && !pz.texto.trim()) pz = { ...pz, texto: pz.texto_imagen.trim() || pz.titulo.trim() || "Historia de Instagram" };
    try {
      if (que === "borrador") {
        const r = await apiPublicar.borrador(pz, pisar ? null : version);
        const yaEstaba = !!f.borrador_id; // (4/11) sobre un borrador que ya existía: «Cambios guardados»
        setVersion(r.version ?? null);
        set("borrador_id", r.id);
        avisar(yaEstaba ? "Cambios guardados." : "Borrador guardado.");
        setResultado({ tipo: "borrador", id: r.id, mensaje: r.mensaje, cambios: yaEstaba });
      } else if (que === "aprobar") {
        const r = await apiPublicar.aAprobar(pz);
        avisar("Pieza enviada a aprobación.");
        setResultado({ tipo: "aprobacion", r });
      } else {
        const r = await apiPublicar.enviar(pz, que);
        if (r.ok) avisar(que === "simulado" ? "Así quedaría la pieza." : r.encolada ? "Quedó programada: sale en su fecha." : "Enviada.");
        else avisar(r.aviso || "No se pudo.", "error");
        setResultado({ tipo: "envio", r, modo: que });
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      if (que === "borrador" && esConflictoDeVersion(e)) setConflicto(e.message); // (5/11) otra persona guardó antes: se pregunta qué hacer
      else setError(e instanceof ErrorApi ? e.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(null);
    }
  }

  const resumen1 = canal ? [info!.texto_canal, f.titulo ? `«${f.titulo.slice(0, 40)}${f.titulo.length > 40 ? "…" : ""}»` : null, `${f.texto.trim().length} caracteres`].filter(Boolean).join(" · ") : "Sin canal todavía";
  // (5/11, Franco) el resumen dice qué se eligió; el nombre sale del banco o del recorte, si se sabe
  const fotoBanco = f.imagen_url ? fotos?.find((x) => x.url === f.imagen_url) : undefined;
  const queFoto = !f.imagen_url ? "" : fuenteFoto === "subida" ? "Foto subida de tu compu" : fuenteFoto === "link" && !fotoBanco ? "Foto de un link" : fotoBanco?.titulo ? `Foto del banco «${fotoBanco.titulo}»` : "Foto del banco";
  const conQue = [conFrase && f.usar_compuesta ? "la frase" : null, conLogo && f.usar_compuesta ? "el logo" : null].filter(Boolean).join(" y ");
  const nombreDelVideo = nombreVideo || (origen === "recorte" ? f.titulo : "");
  const resumen2 = enVarias
    ? nFotos === 0 ? "Todavía no elegiste" : `Carrusel de ${nFotos} foto${nFotos === 1 ? "" : "s"}`
    : conVideo
    ? `Video${nombreDelVideo ? ` «${nombreDelVideo.slice(0, 40)}»` : ""}, ${f.video_formato === "horizontal" ? "horizontal" : "vertical"}`
    : f.imagen_url
      ? `${queFoto}${esRed ? (conQue ? `, con ${conQue}` : ", sola") : canal === "wordpress" ? ", destacada" : ""}`
      : "Todavía no elegiste";
  const avisoVideo =
    esHistoria ? "La historia es vertical y dura 24 h."
    : canal === "wordpress" ? "El video va al principio de la entrada. Título obligatorio."
    : canal === "youtube" ? `Va al canal como video${f.video_formato === "vertical" ? " corto (short)" : ""}. Título obligatorio.`
    : canal === "facebook" ? "Va como video en la página de Facebook, con el texto como descripción."
    : esReel ? "El reel sale con el caption que escribiste en el paso 1."
    : f.video_formato === "horizontal" ? "Este video es horizontal. En Instagram se ve mejor el vertical (pedilo desde la misma tarjeta del chat)."
    : "En Instagram se ve mejor el vertical.";
  // el video elegido (un recorte o uno subido): en Instagram lo manda el tipo (reel o historia); en YouTube sigue como antes
  const elegirVideo = (r: Recorte) => {
    setNombreVideo(r.titulo || "");
    setF((x) => ({ ...x, titulo: x.titulo || (r.titulo || "").slice(0, 100), video_url: r.url, video_formato: r.formato, vfmt: esHistoria ? "historia" : "reel", formato: esHistoria ? "historia" : esReel ? "vertical" : x.formato }));
  };
  // (5/11, Franco) cambiar de camino conserva el texto del paso 1 y la fecha del paso 3, pero limpia lo elegido del camino anterior
  // A Foto desde el carrusel conserva la portada; a Varias fotos desde Foto arranca la lista con esa foto; a Video vacía todo.
  const irA = (c: "foto" | "video" | "varias") => {
    const desde = caminoEf;
    setCamino(c);
    setNombreVideo("");
    setUrlManual("");
    setFuente("banco");
    setFuenteV("recortes");
    setFuenteFoto("banco");
    setF((x) => {
      const limpio = { ...x, video_url: null, video_formato: null };
      if (c === "foto") return { ...limpio, imagenes: null, imagen_url: desde === "varias" ? x.imagenes?.[0] ?? null : null };
      if (c === "varias") return conLista(limpio, desde === "foto" && x.imagen_url ? [x.imagen_url] : []);
      return { ...limpio, imagenes: null, imagen_url: null };
    });
  };
  const resumen3 = fechaIso ? `Programada: ${fechaLegible(fechaIso)}` : "Cuanto antes";

  if (resultado) return <ResultadoPanel resultado={resultado} previa={previa} canal={canal} info={info && tipoIG ? { ...info, texto_canal: `${info.texto_canal} · ${NOMBRE_TIPO_INSTAGRAM[tipoIG]}` } : info} ajena={!!duenaDe} onVolver={() => setResultado(null)} onNueva={() => nav("/publicar", { replace: true, state: null })} />;

  return (
    <div className="pagina publicar">
      <Cabecera
        titulo={
          <>
            Diseñar{desdeMenu && canal ? <span className="pub-titulo-canal"> · {info?.texto_canal || canal}{tipoIG ? ` · ${NOMBRE_TIPO_INSTAGRAM[tipoIG]}` : ""}</span> : null}
          </>
        }
        ayuda="disenar"
        acciones={
          <Link to="/publicaciones" className="boton sutil">
            <Icono nombre="lista" tam={16} /> Mis publicaciones
          </Link>
        }
        subtitulo={
          <>
            {desdeMenu && canal && (tipoIG ? AYUDA_INSTAGRAM[tipoIG] : AYUDA_CANAL[canal] ?? "Acá se diseña la pieza: foto, frase, texto y fecha. Publicarla es el paso siguiente, desde Aprobación.")}
            {desdeMenu && canal === "youtube" && (
              /* (5/11) Lo exige la política de desarrolladores de YouTube (III.A.1 y III.A.2): el cliente de la API muestra el link a los
                 Términos de YouTube y a la Política de privacidad de Google, y la nuestra cuenta cómo se usan los datos. */
              <>
                {" "}
                Usa los servicios de la API de YouTube: al publicar aceptás los{" "}
                <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">Términos del servicio de YouTube</a>. Ver la{" "}
                <a href="https://www.google.com/policies/privacy" target="_blank" rel="noreferrer">Política de privacidad de Google</a> y la{" "}
                <a href="https://viviragradecidos.org/politica-de-privacidad/" target="_blank" rel="noreferrer">de la Fundación</a>.
              </>
            )}
            {!desdeMenu && origen === "chat" && "La pieza que propuso el bot, lista para ajustar y mandar."}
            {origen === "recorte" && "Un recorte listo para publicar: elegí el canal y escribí el texto."}
            {origen === "copia" && (copiaDe ? `Una copia de una pieza de ${copiaDe}: ajustala y guardala como tuya. La original no cambia.` : "Una copia de la pieza: al guardar se crea una nueva y la original no cambia.")}
            {origen === "borrador" && rechazo && `Corrigiendo una pieza rechazada${duenaDe ? ` de ${duenaDe}` : ""}. Al guardar queda como borrador en el mismo lugar, con el rechazo en su historial. Al mandarla a aprobación vuelve a revisarse${duenaDe ? ` a nombre de ${duenaDe}` : ""}, en la misma carpeta.`}
            {origen === "borrador" && !rechazo && !duenaDe && "Retomando un borrador: al guardar se actualiza el mismo. Al mandarlo a aprobación queda en el mismo lugar."}
            {origen === "borrador" && !rechazo && duenaDe && `Editando un borrador de ${duenaDe}, compartido con vos para editar. Al guardar se actualiza el mismo y sigue siendo de ${duenaDe}. Si lo mandás a aprobación, va a su nombre y queda en la misma carpeta.`}
            {!desdeMenu && origen === "nueva" && "Acá se diseña la pieza: foto, frase, texto y fecha. Publicarla es el paso siguiente, desde Aprobación. También se puede diseñar desde el chat, debajo de la respuesta del bot."}
          </>
        }
      >
        <div data-ayuda="disenar.presencia">
          <Presencia presentes={presentes} vacio={f.borrador_id ? "Nadie más está en esta pieza ahora." : "Cuando la guardes como borrador, acá ves si otra persona la mira o la edita."} />
        </div>
      </Cabecera>
      {conflicto && f.borrador_id && (
        <ConflictoGuardado
          mensaje={conflicto}
          ocupado={enviando !== null}
          onCerrar={() => setConflicto(null)}
          onRecargar={() => {
            setConflicto(null);
            recargar(f.borrador_id!);
          }}
          onPisar={() => {
            setConflicto(null);
            void mandar("borrador", true);
          }}
        />
      )}
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

      {/* (5/11, QA visual) Una sola línea, en llano, cuando el canal no está en real: quien diseña sabe si su pieza va a salir. */}
      {info && info.modo_real !== "real" && (
        <p className="suave chico pub-aviso-modo">
          <Icono nombre="info" tam={14} /> {TEXTO_NO_REAL[info.modo_real] ?? "Este canal todavía no publica de verdad: la pieza se arma y queda guardada."}
        </p>
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
              <div className="pub-canal-fijo" data-ayuda="disenar.canal">
                <span>
                  <strong>{info?.texto_canal || canal}</strong> <span className="suave chico">{info?.detalle}</span>
                </span>
              </div>
            ) : (
            <fieldset className="pub-canales" data-ayuda="disenar.canal">
              <legend>Canal</legend>
              {Object.entries(op.canales).map(([clave, i]) => (
                <label key={clave} className={"pub-canal" + (canal === clave ? " activo" : "") + (i.modo === "apagado" ? " apagado" : "")}>
                  <input type="radio" name="canal" value={clave} checked={canal === clave} onChange={() => set("canal", clave)} />
                  <span className="pub-canal-nombre">{i.texto_canal}</span>
                  <span className="pub-canal-detalle chico">{i.detalle}</span>
                </label>
              ))}
            </fieldset>
            )}
            {!desdeMenu && <p className="suave chico">Para el email a la comunidad usá «Email» (o «Newsletter») en el menú: tiene sus plantillas y su vista previa.</p>}
            <label>
              Título <span className="suave">{canal === "wordpress" || canal === "youtube" ? "(obligatorio)" : "(opcional, para el registro)"}</span>
              <input value={f.titulo} onChange={(e) => set("titulo", e.target.value)} maxLength={150} />
            </label>
            {esHistoria ? (
              <div className="aviso" role="note" data-ayuda="disenar.texto">
                <Icono nombre="info" tam={16} /> <span>La historia dura 24 horas y no lleva caption: la frase va escrita en la foto. No hace falta escribir el texto de la pieza.</span>
              </div>
            ) : (
            <label data-ayuda="disenar.texto">
              Texto de la pieza <span className="suave">{esRed ? "(el caption)" : canal === "youtube" ? "(la descripción del video)" : canal === "wordpress" ? "(el cuerpo; se puede usar HTML simple o markdown)" : ""}</span>
              <textarea value={f.texto} onChange={(e) => set("texto", e.target.value)} rows={9} placeholder="Escribí la pieza o pedísela al bot en el chat." />
              <span className="suave chico pub-contador">
                {f.texto.length} caracteres{esRed && f.texto.length > 2200 ? " · Instagram corta el caption en 2200" : ""}
              </span>
            </label>
            )}
            <div className="acciones">
              <button type="button" className="boton primario" onClick={() => setPaso(2)} disabled={!canal}>
                Siguiente: {TITULO_PASO_2.toLowerCase()} <Icono nombre="chevron" tam={16} />
              </button>
            </div>
          </Paso>

          {/* ---------- Paso 2: qué va en la pieza (foto o video) ---------- */}
          {/* (5/11, Franco) El paso se llama siempre igual y arranca con la elección: una pieza lleva una foto o un video. Diseño de web/maquetas/disenar-paso-2.html. */}
          <Paso data-ayuda="disenar.foto" n={2} titulo={TITULO_PASO_2} resumen={resumen2} abierto={paso === 2} hecho={paso > 2} onAbrir={() => canal && setPaso(2)} deshabilitado={!canal}>
            {caminoEf === "elegir" && (
              <div>
                <p className="suave pub-caminos-intro">Una pieza lleva una foto o un video. Elegí por dónde vas.</p>
                <div className="pub-caminos">
                  <button type="button" className="pub-camino" onClick={() => irA("foto")}>
                    <b>
                      <span className="pub-camino-ico"><Icono nombre="imagen" tam={18} /></span> Foto
                    </b>
                    <span className="suave chico">Del banco, de tu compu o de un link. Después le ponés la frase y el logo.</span>
                  </button>
                  <button type="button" className="pub-camino" onClick={() => irA("video")}>
                    <b>
                      <span className="pub-camino-ico"><Icono nombre="pelicula" tam={18} /></span> Video
                    </b>
                    <span className="suave chico">Un recorte listo o un video tuyo. Después elegís el formato.</span>
                  </button>
                  {permiteCarrusel && (
                    <button type="button" className="pub-camino" onClick={() => irA("varias")}>
                      <b>
                        <span className="pub-camino-ico"><Icono nombre="imagen" tam={18} /></span> Varias fotos
                      </b>
                      <span className="suave chico">Carrusel: de 2 a 10 fotos, en el orden que elijas.</span>
                    </button>
                  )}
                </div>
              </div>
            )}

            {(caminoEf === "foto" || enVarias) && (
              <>
                <div className="pub-elegido">
                  <Icono nombre="imagen" tam={16} /> {enVarias ? "Varias fotos" : "Foto"}
                  {enVarias && <button type="button" onClick={() => irA("foto")}>Cambiar a foto</button>}
                  {!enVarias && permiteCarrusel && <button type="button" onClick={() => irA("varias")}>Cambiar a varias fotos</button>}
                  <button type="button" onClick={() => irA("video")}>Cambiar a video</button>
                </div>

                {enVarias && (
                  <div className="pub-carrusel">
                    <h3 id="pub-carrusel-titulo">Fotos del carrusel ({nFotos} de {MAX_FOTOS})</h3>
                    {nFotos === 0 ? (
                      <p className="suave chico">Elegí fotos abajo: cada una se suma a la lista, y desde acá las ordenás.</p>
                    ) : (
                      <ol className="pub-carrusel-tira" aria-labelledby="pub-carrusel-titulo">
                        {lista.map((url, k) => (
                          <li key={url} className="pub-carrusel-foto">
                            <div className="pub-carrusel-img">
                              <img src={url} alt={`Foto ${k + 1}`} loading="lazy" />
                              <span className="pub-carrusel-num">{k + 1}</span>
                              {k === 0 && <span className="pub-carrusel-portada">Portada</span>}
                            </div>
                            <div className="pub-carrusel-botones">
                              <button type="button" className="boton chico" aria-label={`Mover la foto ${k + 1} a la izquierda`} disabled={k === 0} onClick={() => moverFoto(k, -1)}>
                                ←
                              </button>
                              <button type="button" className="boton chico" aria-label={`Mover la foto ${k + 1} a la derecha`} disabled={k === nFotos - 1} onClick={() => moverFoto(k, 1)}>
                                →
                              </button>
                              <button type="button" className="boton sutil chico" aria-label={`Quitar la foto ${k + 1}`} onClick={() => quitarFoto(k)}>
                                Quitar
                              </button>
                            </div>
                          </li>
                        ))}
                      </ol>
                    )}
                    {nFotos < MIN_FOTOS && (
                      <p className="aviso chico" role="status">
                        <Icono nombre="info" tam={14} /> Faltan fotos: un carrusel lleva al menos 2.
                      </p>
                    )}
                  </div>
                )}

                <div className="pub-fuentes" role="tablist" aria-label="De dónde sale la foto">
                  {([["banco", "Banco de la Fundación"], ["archivo", "Subir de mi compu"], ["url", "Pegar un link"]] as const).map(([k, t]) => (
                    <button key={k} type="button" role="tab" aria-selected={fuente === k} className={fuente === k ? "on" : ""} onClick={() => setFuente(k)}>
                      {t}
                    </button>
                  ))}
                </div>

                {enVarias && completo && (
                  <p className="aviso chico" role="status">
                    <Icono nombre="info" tam={14} /> El carrusel ya está completo: {MAX_FOTOS} fotos. Quitá alguna para sumar otra.
                  </p>
                )}

                {fuente === "banco" && !(enVarias && completo) && (
                  <div className="pub-banco">
                    <label htmlFor="pub-busq">Imagen {canal === "wordpress" ? "(la destacada de la entrada)" : ""}</label>
                    <div className="pieza-banco-buscar">
                      <input id="pub-busq" value={f.imagen_busqueda} onChange={(e) => set("imagen_busqueda", e.target.value)} placeholder="Buscar en el banco de la Fundación: ej. amanecer montaña calma" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscarFotos(f.imagen_busqueda))} />
                      <button type="button" className="boton" onClick={() => buscarFotos(f.imagen_busqueda)} disabled={buscando}>
                        <Icono nombre="buscar" tam={16} /> {buscando ? "Buscando…" : "Buscar"}
                      </button>
                    </div>
                    <AvisoBanco fotos={fotos} />
                    {enVarias ? (
                      <div className="pieza-fotos" role="group" aria-label="Elegí las fotos para sumar al carrusel">
                        {fotos?.map((x) => (
                          <button key={x.id} type="button" className={"pieza-foto" + (lista.includes(x.url) ? " elegida" : "")} onClick={() => agregarFoto(x.url)} aria-label={`Sumar ${x.titulo || "#" + x.id}`} title={x.titulo || `#${x.id}`}>
                            <img src={x.miniatura} alt="" loading="lazy" />
                            <span className="chico">{lista.includes(x.url) ? "en el carrusel" : (x.titulo || `#${x.id}`).slice(0, 28)}</span>
                          </button>
                        ))}
                        {buscando && fotos === null && [1, 2, 3].map((i) => <Hueso key={i} ancho={112} alto={132} radio={10} />)}
                      </div>
                    ) : (
                    <div className="pieza-fotos" role="radiogroup" aria-label="Elegí una foto">
                      {f.imagen_url && !fotos?.some((x) => x.url === f.imagen_url) && (
                        <button type="button" className="pieza-foto elegida" role="radio" aria-checked="true" title={f.imagen_url}>
                          <img src={f.imagen_url} alt="" loading="lazy" />
                          <span className="chico">la elegida</span>
                        </button>
                      )}
                      {fotos?.map((x) => (
                        <button key={x.id} type="button" className={"pieza-foto" + (f.imagen_url === x.url ? " elegida" : "")} onClick={() => (set("imagen_url", x.url), setUrlManual(""), setFuenteFoto("banco"))} role="radio" aria-checked={f.imagen_url === x.url} title={x.titulo || `#${x.id}`}>
                          <img src={x.miniatura} alt={x.titulo || ""} loading="lazy" />
                          <span className="chico">{(x.titulo || `#${x.id}`).slice(0, 28)}</span>
                        </button>
                      ))}
                      {buscando && fotos === null && [1, 2, 3].map((i) => <Hueso key={i} ancho={112} alto={132} radio={10} />)}
                    </div>
                    )}
                    {fotos && fotos.length === 0 && !buscando && <p className="suave chico">El banco no tiene nada para esa búsqueda. Probá otras palabras, o subí una foto de tu compu o pegá un link.</p>}
                  </div>
                )}

                {fuente === "archivo" && !(enVarias && completo) && (
                  <div className="pub-banco">
                    <ZonaArchivo titulo="Arrastrá una imagen o elegila" detalle="JPG, PNG o WebP. Se guarda en el banco de la Fundación para que la pueda usar el equipo." accept="image/jpeg,image/png,image/webp" etiqueta="Archivo de imagen" ocupado={subiendo} onArchivo={subirArchivo} />
                    {subiendo && <p className="suave chico" role="status">Subiendo al banco de la Fundación…</p>}
                    {avisoSubida && <div className="aviso chico">{avisoSubida}</div>}
                    {!enVarias && f.imagen_url && fuenteFoto === "subida" && <p className="suave chico">Quedó elegida: {nombreSubida || "tu imagen"}.</p>}
                  </div>
                )}

                {fuente === "url" && !(enVarias && completo) && (
                  <div className="pub-banco">
                    <label>
                      Link de una imagen que ya está en internet
                      <input
                        type="url"
                        value={urlManual}
                        onChange={(e) => {
                          setUrlManual(e.target.value);
                          if (!enVarias && /^https?:\/\/\S+$/i.test(e.target.value.trim())) (set("imagen_url", e.target.value.trim()), setFuenteFoto("link"));
                        }}
                        onKeyDown={(e) => {
                          if (enVarias && e.key === "Enter") (e.preventDefault(), sumarLink());
                        }}
                        placeholder="https://…"
                        inputMode="url"
                      />
                    </label>
                    {enVarias && (
                      <button type="button" className="boton" onClick={sumarLink} disabled={!/^https:\/\/\S+$/i.test(urlManual.trim())}>
                        Sumar al carrusel
                      </button>
                    )}
                    <span className="suave chico">Tiene que ser un link directo a la imagen (termina en .jpg o .png){enVarias ? " y empezar con https" : ""}.</span>
                  </div>
                )}

                {esRed && !enVarias && (
                  <div className="pub-diseno">
                    <h3>{conFrase ? "Con la frase encima" : "Frase, formato y logo"}</h3>
                    <label>
                      Texto sobre la imagen <span className="suave chico">(va encima de la foto, no es el caption)</span>
                      <input value={f.texto_imagen} onChange={(e) => set("texto_imagen", e.target.value)} maxLength={400} placeholder="ej. La gratitud es la llave de la alegría" />
                    </label>
                    {f.imagen_url && (
                      <>
                        <div className="pub-fila">
                          {!esHistoria && (
                          <label>
                            Formato
                            <select value={f.formato} onChange={(e) => set("formato", e.target.value)}>
                              {Object.entries(op.formatos).filter(([k]) => canal !== "instagram" || k === "cuadrado" || k === "vertical").map(([k, [w, h]]) => (
                                <option key={k} value={k}>
                                  {k} ({w}×{h})
                                </option>
                              ))}
                            </select>
                          </label>
                          )}
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
                        {esHistoria && <p className="suave chico">Historia de Instagram: dura 24 h y no lleva caption. El texto de la pieza queda solo en el registro.{!(conFrase || conLogo) || !f.usar_compuesta ? " La foto sale tal cual; si no es vertical 9:16, Instagram la recorta." : ""}</p>}
                        {errorCompuesta && <div className="aviso error chico">{errorCompuesta}</div>}
                      </>
                    )}
                  </div>
                )}
              </>
            )}

            {caminoEf === "video" && (
              <>
                <div className="pub-elegido">
                  <Icono nombre="pelicula" tam={16} /> Video
                  {!soloVideo && (
                    <button type="button" onClick={() => irA("foto")}>Cambiar a foto</button>
                  )}
                </div>

                <div className="pub-fuentes" role="tablist" aria-label="De dónde sale el video">
                  {([["recortes", "Recortes listos"], ["subir", "Subir un video mío"]] as const).map(([k, t]) => (
                    <button key={k} type="button" role="tab" aria-selected={fuenteV === k} className={fuenteV === k ? "on" : ""} onClick={() => setFuenteV(k)}>
                      {t}
                    </button>
                  ))}
                </div>

                {fuenteV === "recortes" && <ElegirRecorte onElegir={elegirVideo} elegido={f.video_url} />}
                {fuenteV === "subir" && (
                  <div className="pub-banco">
                    <ZonaArchivo titulo="Arrastrá un video o elegilo" detalle="MP4 o MOV, hasta 200 MB. Queda en Mis recortes como «subido»." accept="video/mp4,video/quicktime,.mp4,.mov" etiqueta="Archivo de video" onArchivo={(a) => setVideoParaSubir(a)} />
                  </div>
                )}
                {videoParaSubir && (
                  <SubirVideo
                    archivoInicial={videoParaSubir}
                    onCerrar={() => setVideoParaSubir(null)}
                    onSubido={async (id) => {
                      setVideoParaSubir(null);
                      const r = id ? await api.recorte(id).catch(() => null) : null;
                      if (r && r.estado === "listo" && r.url) {
                        elegirVideo(r);
                        avisar("Video subido: ya está elegido para la pieza.");
                      } else {
                        avisar("Video subido. Cuando esté listo aparece en «Recortes listos».");
                        setFuenteV("recortes");
                      }
                    }}
                  />
                )}

                <div className="pub-diseno">
                  <h3>Formato</h3>
                  <div className="pub-fila-formato">
                    <span className="pub-chip-formato">{conVideo ? (f.video_formato === "horizontal" ? "Horizontal" : "Vertical") : "Lo define el video que elijas"}</span>
                    <span className="suave chico">{avisoVideo}</span>
                  </div>
                </div>
              </>
            )}

            <div className="acciones">
              <button type="button" className="boton" onClick={() => setPaso(1)}>
                Volver
              </button>
              {/* (5/11, coordinador) se puede seguir sin foto ni video: el paso 3 avisa qué falta y deja «Guardar borrador» (Julián, 2/11: diseñó a medias y no podía retomar) */}
              <button type="button" className="boton primario" onClick={() => setPaso(3)}>
                Siguiente: cuándo y enviar <Icono nombre="chevron" tam={16} />
              </button>
            </div>
          </Paso>

          {/* ---------- Paso 3: cuándo y enviar ---------- */}
          <Paso data-ayuda="disenar.cuando" n={3} titulo="Cuándo y enviar" resumen={resumen3} abierto={paso === 3} hecho={false} onAbrir={() => canal && setPaso(3)} deshabilitado={!canal}>
            <Programar f={f} set={set} />
            {canal && info && (
              <div className={"pub-aviso " + modo}>
                <Icono nombre={modo === "real" ? "alerta" : "info"} tam={16} />
                <span>{textoAviso(info, fechaIso)}</span>
              </div>
            )}
            <p className="suave chico">
              Lo revisa {op.aprobadores.join(", ") || "un aprobador"}. «Ver cómo quedaría» arma la pieza sin mandarla.
              {op.aprueba && " Vos también lo aprobás desde Aprobación."}
            </p>
            {faltas.length > 0 && canal && (
              <p className="suave chico">
                <Icono nombre="alerta" tam={14} /> Antes de enviar: {faltas.join(", ")}.
              </p>
            )}
            <div className="acciones pub-enviar">
              <button type="button" className="boton primario grande" onClick={() => mandar("aprobar")} disabled={enviando !== null || !puedeProponer || faltas.length > 0} title={motivoNoProponer || undefined}>
                <Icono nombre="check" /> {enviando === "aprobar" ? "Enviando…" : etiquetaPrincipal}
              </button>
              <button type="button" className="boton" onClick={() => mandar("simulado")} disabled={enviando !== null || !canal || modo === "apagado" || faltaTexto || faltaTitulo || (esReel && !conVideo) || faltaFotoIG || faltanFotos || !hayPieza} title="Arma la pieza tal cual saldría y la muestra. No manda nada; queda como prueba en Mis publicaciones.">
                <Icono nombre="ojo" /> {enviando === "simulado" ? "Armando…" : "Ver cómo quedaría"}
              </button>
              <button type="button" className="boton" onClick={() => mandar("borrador")} disabled={enviando !== null || !canal} title="Guarda todo sin mandar nada; se retoma desde Mis publicaciones.">
                <Icono nombre="lapiz" /> {enviando === "borrador" ? "Guardando…" : f.borrador_id ? "Guardar cambios" : "Guardar borrador"}
              </button>
            </div>
            {motivoNoProponer && canal && <p className="suave chico">{motivoNoProponer}</p>}
          </Paso>
        </div>

        <aside className="pub-previa" data-ayuda="disenar.previa">
          <div className="pub-previa-cabecera">
            <h2>
              <Icono nombre="ojo" tam={16} /> Así se vería
            </h2>
            {info && <span className="chip suave">{info.texto_canal}</span>}
          </div>
          <VistaPrevia d={previa} />
          {seCompone && !f.usar_compuesta && <p className="suave chico">Se publica la foto sola.</p>}
        </aside>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
function Paso({ "data-ayuda": ayuda, n, titulo, resumen, abierto, hecho, deshabilitado = false, onAbrir, children }: { "data-ayuda"?: string; n: number; titulo: string; resumen: string; abierto: boolean; hecho: boolean; deshabilitado?: boolean; onAbrir: () => void; children: React.ReactNode }) {
  return (
    <section {...(ayuda ? { "data-ayuda": ayuda } : {})} className={"pub-paso" + (abierto ? " abierto" : "") + (deshabilitado ? " deshabilitado" : "")} aria-labelledby={`paso-${n}`}>
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
function ElegirRecorte({ onElegir, elegido = null }: { onElegir: (r: Recorte) => void; elegido?: string | null }) {
  const [lista, setLista] = useState<Recorte[] | null>(null);
  const [error, setError] = useState<string | null>(null);
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
        Los que ya están listos en Mis recortes. Si falta alguno, pedilo desde la tarjeta del chat; para ajustarlo (tramo, subtítulos, pausas) abrilo en el editor desde <Link to="/recortes">Mis recortes</Link>.
      </p>
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
            <div key={r.id} className={"pieza-foto pub-recorte" + (elegido && r.url === elegido ? " elegida" : "")} role="listitem">
              {r.miniatura ? <img src={r.miniatura} alt="" loading="lazy" /> : r.subido && r.url ? <video src={r.url} preload="metadata" muted playsInline /> : <div className="pub-recorte-sin" />}
              <span className="chico pub-recorte-titulo" title={r.titulo || ""}>{(r.titulo || "(sin título)").slice(0, 48)}</span>
              <span className="suave chico">
                {r.formato} · {Math.round((r.fin_ms - r.inicio_ms) / 1000)} s{r.propio ? "" : " · del equipo"}
              </span>
              <span className="pub-recorte-acciones">
                <button type="button" className="boton primario chico" onClick={() => onElegir(r)}>
                  {elegido && r.url === elegido ? "Elegido" : "Usar este"}
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

/** (5/11, Franco) Zona para arrastrar un archivo o elegirlo (foto de la compu o video propio). */
function ZonaArchivo({ titulo, detalle, accept, etiqueta, ocupado = false, onArchivo }: { titulo: string; detalle: string; accept: string; etiqueta: string; ocupado?: boolean; onArchivo: (a: File) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const [encima, setEncima] = useState(false);
  const recibir = (a: File | undefined) => {
    if (a) onArchivo(a);
    if (ref.current) ref.current.value = "";
  };
  return (
    <div
      className={"pub-zona" + (encima ? " encima" : "")}
      onDragOver={(e) => (e.preventDefault(), setEncima(true))}
      onDragLeave={() => setEncima(false)}
      onDrop={(e) => (e.preventDefault(), setEncima(false), !ocupado && recibir(e.dataTransfer.files?.[0]))}
    >
      <b>{titulo}</b>
      <span className="chico suave">{detalle}</span>
      <input ref={ref} type="file" accept={accept} aria-label={etiqueta} hidden disabled={ocupado} onChange={(e) => recibir(e.target.files?.[0])} />
      <button type="button" className="boton" onClick={() => ref.current?.click()} disabled={ocupado}>
        Elegir archivo
      </button>
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
  let imagenesFinal: string[] | null = null;
  if (resultado.tipo === "borrador") {
    titulo = resultado.cambios ? "Cambios guardados" : "Borrador guardado";
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
    titulo = !r.ok ? "No se pudo" : r.encolada ? "Quedó programada" : r.simulado ? `Así quedaría en ${nombre}` : r.modo === "borrador" ? "Borrador creado en WordPress" : `Enviada a ${nombre}`;
    detalle = r.aviso;
    avisos = r.avisos;
    imagenFinal = r.imagen_url;
    imagenesFinal = r.imagenes ?? null;
    mostrarPrevia = r.simulado || !!r.pieza;
    if (r.link_editar) links.push({ texto: "Abrir el borrador en WordPress", url: r.link_editar });
    if (r.link && canal === "youtube") links.push({ texto: "Ver el video en YouTube", url: r.link });
    if (r.link && canal === "wordpress" && !r.link_editar) links.push({ texto: "Ver la entrada", url: r.link });
    if (r.permalink) links.push({ texto: "Ver la publicación", url: r.permalink });
  }
  return (
    <div className="pagina publicar">
      <Cabecera titulo="Diseñar" />
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
          <VistaPrevia d={{ ...previa, imagenSrc: previa.imagenSrc || imagenFinal, imagenes: previa.imagenes ?? imagenesFinal }} compacta />
        </div>
      )}
    </div>
  );
}
