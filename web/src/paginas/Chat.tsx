// La pantalla de chat (fase 2 de la interfaz propia, 22/10): paridad con el chat de Streamlit (app.py) y mejor UX.
// Izquierda: ListaConversaciones (en celular, un cajón). Derecha: los mensajes con markdown, la respuesta en streaming (SSE),
// las fuentes plegables con los botones de recorte, el recuadro de la pieza propuesta, las descargas Word/Excel y el cuadro de
// escribir. Atajos: / enfoca el cuadro, Esc cierra el cajón. Antes de mandar, si la API dormía (Render free), avisa y espera.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorApi } from "../api";
import { apiChat, enviarMensaje, esperarApi, type EventoChat } from "../apiChat";
import { useSesion } from "../App";
import type { Clip, Conversacion, ConversacionResumen, MensajeChat, Tarjeta } from "../tiposChat";
import { textos } from "../textos";
import type { Idioma } from "../util/fechas";
import ListaConversaciones from "../componentes/ListaConversaciones";
import Mensaje from "../componentes/Mensaje";
import Entrada, { type EntradaRef } from "../componentes/Entrada";
import { Icono } from "../componentes/Iconos";
import { Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import "../chat.css";

const VACIA = (): Conversacion => ({ id: "", titulo: null, mensajes: [] });

function normalizar(s: string) {
  return s.split(/\s+/).join(" ").trim();
}

export default function Chat() {
  const { yo } = useSesion();
  const idioma = ((["es", "en", "de"].includes(yo?.idioma || "") ? yo?.idioma : "es") || "es") as Idioma;
  const t = textos(idioma);
  const { id } = useParams();
  const nav = useNavigate();
  const { avisar } = useToast();

  const [lista, setLista] = useState<ConversacionResumen[] | null>(null);
  const [errorLista, setErrorLista] = useState<string | null>(null);
  const [conv, setConv] = useState<Conversacion>(VACIA);
  const [cargando, setCargando] = useState(false);
  const [errorConv, setErrorConv] = useState<string | null>(null);
  const [generando, setGenerando] = useState(false);
  const [cajon, setCajon] = useState(false);
  const [abajo, setAbajo] = useState(true);
  const abortar = useRef<AbortController | null>(null);
  const saltarCarga = useRef<string | null>(null); // el id al que navegamos nosotros al terminar una respuesta: ya está en pantalla
  const entrada = useRef<EntradaRef>(null);
  const panel = useRef<HTMLDivElement>(null);

  // ---------- lista ----------
  const cargarLista = useCallback(async () => {
    try {
      setLista(await apiChat.conversaciones());
      setErrorLista(null);
    } catch (e) {
      setErrorLista(e instanceof ErrorApi ? e.message : t("noLista"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    cargarLista();
  }, [cargarLista]);

  // ---------- abrir una conversación (o la vacía) ----------
  useEffect(() => {
    if (id && saltarCarga.current === id) {
      saltarCarga.current = null;
      return;
    }
    abortar.current?.abort();
    setGenerando(false);
    setErrorConv(null);
    if (!id) {
      setConv(VACIA());
      setCargando(false);
      return;
    }
    let vivo = true;
    setCargando(true);
    apiChat
      .conversacion(id)
      .then((c) => {
        if (!vivo) return;
        setConv({ id: c.id, titulo: c.titulo, mensajes: c.mensajes.map((m) => ({ role: m.role, content: m.content, tarjetas: m.tarjetas || [], pieza: m.pieza || null })) });
        setAbajo(true);
      })
      .catch((e) => vivo && setErrorConv(e instanceof ErrorApi ? e.message : t("noCargo")))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ---------- autoscroll que no molesta ----------
  useEffect(() => {
    const el = panel.current;
    if (!el || !abajo) return;
    el.scrollTop = el.scrollHeight;
  }, [conv.mensajes, abajo, cargando]);

  function alScroll() {
    const el = panel.current;
    if (!el) return;
    setAbajo(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  }

  // ---------- en celular, la barra de arriba mide distinto según el ancho: el alto del chat la descuenta ----------
  const raiz = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const barra = document.querySelector<HTMLElement>(".barra");
    if (!barra || typeof ResizeObserver === "undefined") return;
    const medir = () => raiz.current?.style.setProperty("--barra-alto", `${barra.getBoundingClientRect().height}px`);
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(barra);
    return () => ro.disconnect();
  }, []);

  // ---------- atajos ----------
  useEffect(() => {
    function tecla(e: KeyboardEvent) {
      const obj = e.target as HTMLElement | null;
      const escribiendo = !!obj && (obj.tagName === "INPUT" || obj.tagName === "TEXTAREA" || obj.isContentEditable);
      if (e.key === "/" && !escribiendo && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        entrada.current?.enfocar();
      } else if (e.key === "Escape") {
        setCajon(false);
      }
    }
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, []);

  // ---------- mandar un mensaje ----------
  const actualizarUltimo = useCallback((f: (m: MensajeChat) => MensajeChat) => {
    setConv((c) => {
      const ms = c.mensajes.slice();
      const i = ms.length - 1;
      if (i < 0 || ms[i].role !== "assistant") return c;
      ms[i] = f(ms[i]);
      return { ...c, mensajes: ms };
    });
  }, []);

  async function enviar(texto: string) {
    if (generando) return;
    const convId = conv.id || null;
    setConv((c) => {
      const ms = c.mensajes.slice();
      const ult = ms[ms.length - 1];
      if (!(ult && ult.role === "user" && normalizar(ult.content) === normalizar(texto))) ms.push({ role: "user", content: texto });
      ms.push({ role: "assistant", content: "", tarjetas: [], pieza: null, estado: t("pensando") });
      return { ...c, mensajes: ms };
    });
    setAbajo(true);
    setGenerando(true);
    const ctl = new AbortController();
    abortar.current = ctl;
    try {
      const despierta = await esperarApi(() => actualizarUltimo((m) => ({ ...m, estado: t("despertando") })), ctl.signal);
      if (ctl.signal.aborted) throw new DOMException("detenido", "AbortError");
      if (!despierta) {
        actualizarUltimo((m) => ({ ...m, estado: null, error: t("noDesperto") }));
        return;
      }
      actualizarUltimo((m) => ({ ...m, estado: t("pensando") }));
      await enviarMensaje(convId, texto, (e) => alEvento(e, convId), ctl.signal);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        actualizarUltimo((m) => ({ ...m, estado: null, error: t("detenido") }));
      } else {
        actualizarUltimo((m) => ({ ...m, estado: null, error: e instanceof ErrorApi ? e.message : t("cortado") }));
      }
    } finally {
      if (abortar.current === ctl) abortar.current = null;
      setGenerando(false);
    }
  }

  function alEvento(e: EventoChat, convId: string | null) {
    switch (e.nombre) {
      case "estado": {
        const txt = e.datos.texto === "buscando" ? t("buscando") : e.datos.texto === "trabajando" ? t("trabajando") : t("pensando");
        actualizarUltimo((m) => ({ ...m, estado: txt }));
        break;
      }
      case "fuentes":
        actualizarUltimo((m) => ({ ...m, tarjetas: e.datos.tarjetas }));
        break;
      case "pieza":
        actualizarUltimo((m) => ({ ...m, pieza: e.datos }));
        break;
      case "texto":
        actualizarUltimo((m) => ({ ...m, estado: null, content: m.content + e.datos.delta }));
        break;
      case "fin": {
        const d = e.datos;
        actualizarUltimo(() => ({ role: "assistant", content: d.texto, tarjetas: d.tarjetas || [], pieza: d.pieza || null }));
        const nuevoId = d.conversacion_id;
        if (nuevoId) {
          setConv((c) => ({ ...c, id: nuevoId, titulo: d.titulo ?? c.titulo }));
          const ahora = new Date().toISOString();
          setLista((l) => {
            const resto = (l || []).filter((x) => x.id !== nuevoId);
            const prev = (l || []).find((x) => x.id === nuevoId);
            return [{ id: nuevoId, titulo: d.titulo ?? prev?.titulo ?? null, actualizado: ahora }, ...resto];
          });
          if (!convId) {
            saltarCarga.current = nuevoId;
            nav(`/chat/${nuevoId}`, { replace: true });
          }
        }
        break;
      }
      case "error":
        actualizarUltimo((m) => ({ ...m, estado: null, error: e.datos.detalle || t("cortado") }));
        break;
      default:
        break;
    }
  }

  function detener() {
    abortar.current?.abort();
  }

  // ---------- lista: acciones ----------
  function nueva() {
    setCajon(false);
    if (generando) detener();
    nav("/chat");
    window.setTimeout(() => entrada.current?.enfocar(), 0);
  }
  function abrir(cid: string) {
    setCajon(false);
    nav(`/chat/${cid}`);
  }
  async function renombrar(cid: string, titulo: string) {
    try {
      const r = await apiChat.renombrar(cid, titulo);
      setLista((l) => (l || []).map((c) => (c.id === cid ? { ...c, titulo: r.titulo } : c)));
      if (conv.id === cid) setConv((c) => ({ ...c, titulo: r.titulo }));
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude renombrar.", "error");
      throw e;
    }
  }
  async function borrar(cid: string) {
    try {
      await apiChat.borrar(cid);
      setLista((l) => (l || []).filter((c) => c.id !== cid));
      if (conv.id === cid) nav("/chat");
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude borrar.", "error");
      throw e;
    }
  }
  async function restaurar(cid: string) {
    try {
      await apiChat.restaurar(cid);
      avisar(t("restaurada"));
      cargarLista();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude recuperarla.", "error");
      throw e;
    }
  }

  // ---------- recortes desde las tarjetas ----------
  const aplicarClips = useCallback((clips: Clip[]) => {
    const por = new Map(clips.map((c) => [`${c.video_id}|${c.inicio_ms}|${c.fin_ms}|${c.formato}`, c]));
    setConv((c) => ({
      ...c,
      mensajes: c.mensajes.map((m) =>
        !m.tarjetas?.length
          ? m
          : {
              ...m,
              tarjetas: m.tarjetas.map((x) => {
                if (!x.recortes || x.inicio_ms === null) return x;
                const rec = { ...x.recortes };
                for (const f of ["horizontal", "vertical"] as const) {
                  const k = por.get(`${x.doc}|${x.inicio_ms}|${x.fin_ms}|${f}`);
                  if (k) rec[f] = { id: k.id, estado: k.estado, url: k.url, error: k.error };
                }
                return { ...x, recortes: rec };
              }),
            },
      ),
    }));
  }, []);

  async function pedirRecorte(x: Tarjeta, formato: "horizontal" | "vertical") {
    if (!x.doc || x.inicio_ms === null || !x.fin_ms) return;
    try {
      const r = await apiChat.pedirRecorte({ video_id: x.doc, inicio_ms: x.inicio_ms, fin_ms: x.fin_ms, formato, titulo: x.titulo });
      if (r.id) aplicarClips([{ id: r.id, video_id: x.doc, inicio_ms: x.inicio_ms, fin_ms: x.fin_ms, formato, estado: r.estado, url: r.url, error: null }]);
      avisar(r.mensaje, r.ya ? "info" : "ok");
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude registrar el pedido.", "error");
    }
  }

  const hayEnProceso = useMemo(() => conv.mensajes.some((m) => m.tarjetas?.some((x) => x.recortes && Object.values(x.recortes).some((r) => r?.estado === "pedido"))), [conv.mensajes]);
  useEffect(() => {
    if (!hayEnProceso || !conv.id) return;
    const cid = conv.id;
    const tmr = window.setInterval(() => apiChat.recortesDe(cid).then(aplicarClips).catch(() => {}), 60000);
    return () => window.clearInterval(tmr);
  }, [hayEnProceso, conv.id, aplicarClips]);

  // ---------- render ----------
  const titulo = conv.titulo || (conv.id ? t("conversacion") : t("titulo"));
  return (
    <div className={"chat" + (cajon ? " con-cajon" : "")} ref={raiz}>
      <aside className="chat-lateral" aria-hidden={!cajon && window.matchMedia("(max-width: 760px)").matches ? true : undefined}>
        <ListaConversaciones items={lista} error={errorLista} actualId={conv.id || null} idioma={idioma} onNueva={nueva} onAbrir={abrir} onRenombrar={renombrar} onBorrar={borrar} onRestaurar={restaurar} onReintentar={cargarLista} onCerrar={() => setCajon(false)} />
      </aside>
      {cajon && <div className="chat-velo" onClick={() => setCajon(false)} aria-hidden="true" />}

      <section className="chat-panel" aria-label={t("titulo")}>
        <header className="chat-cabecera">
          <button type="button" className="boton sutil chico chat-abrir-lista" onClick={() => setCajon(true)} aria-expanded={cajon} aria-controls="lista-conversaciones">
            <Icono nombre="menu" tam={18} /> <span>{t("abrirLista")}</span>
          </button>
          <h1 className="chat-titulo" title={titulo}>
            {titulo}
          </h1>
        </header>

        <div className="chat-mensajes" ref={panel} onScroll={alScroll} role="log" aria-live="polite" aria-busy={generando || cargando}>
          {cargando && (
            <div className="chat-esqueleto" aria-label="Cargando la conversación">
              <Hueso ancho="40%" alto={40} radio={14} style={{ marginLeft: "auto" }} />
              <Hueso ancho="85%" alto={16} style={{ marginTop: 22 }} />
              <Hueso ancho="92%" alto={16} style={{ marginTop: 8 }} />
              <Hueso ancho="60%" alto={16} style={{ marginTop: 8 }} />
              <Hueso ancho="35%" alto={40} radio={14} style={{ marginLeft: "auto", marginTop: 26 }} />
              <Hueso ancho="78%" alto={16} style={{ marginTop: 22 }} />
              <Hueso ancho="88%" alto={16} style={{ marginTop: 8 }} />
            </div>
          )}
          {errorConv && (
            <div className="aviso error" style={{ maxWidth: 760, margin: "20px auto" }}>
              <Icono nombre="alerta" tam={16} /> {errorConv}{" "}
              <button type="button" className="boton chico" onClick={() => nav("/chat")}>
                {t("nueva")}
              </button>
            </div>
          )}
          {!cargando && !errorConv && conv.mensajes.length === 0 && (
            <div className="chat-vacio">
              <img src="/logo.png" alt="" />
              <h2>{t("vacioTitulo")}</h2>
              <p className="suave">{t("vacioTexto")}</p>
              <div className="chat-ejemplos">
                {t("ejemplos").map((ej) => (
                  <button key={ej} type="button" className="boton" onClick={() => entrada.current?.poner(ej)}>
                    {ej}
                  </button>
                ))}
              </div>
              <p className="suave chico">{t("sub")}</p>
            </div>
          )}
          {!cargando && conv.mensajes.map((m, i) => <Mensaje key={i} m={m} n={i} convId={conv.id || null} idioma={idioma} ultimo={i === conv.mensajes.length - 1} generando={generando && i === conv.mensajes.length - 1} onPedirRecorte={pedirRecorte} />)}
        </div>

        {!abajo && conv.mensajes.length > 0 && (
          <button
            type="button"
            className="boton chico chat-bajar"
            onClick={() => {
              setAbajo(true);
              const el = panel.current;
              if (el) el.scrollTop = el.scrollHeight;
            }}
            aria-label={t("bajar")}
            title={t("bajar")}
          >
            <Icono nombre="chevron" tam={16} style={{ transform: "rotate(90deg)" }} />
          </button>
        )}

        <Entrada ref={entrada} placeholder={t("placeholder")} ayuda={t("ayudaEntrada")} enviando={generando} textoEnviar={t("enviar")} textoDetener={t("detener")} onEnviar={enviar} onDetener={detener} />
      </section>
    </div>
  );
}
