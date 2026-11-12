import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { BASE, ErrorApi } from "../../api";
import { apiProyectos } from "../../apiProyectos";
import { definirAyuda } from "../../ayuda/registro";
import ChipEstado from "../../componentes/ChipEstado";
import { EstadoVacio } from "../../componentes/Comunes";
import { Icono, type NombreIcono } from "../../componentes/Iconos";
import { fechaCompleta, hace } from "../../util/fechas";
import { aHtml } from "../../util/markdown";
import { mesesRecientes } from "./Dashboard";
import type { Proyecto } from "../../tiposProyectos";
import { adminApi, type PiezaCanal, type SerieCanal, type Campana, type Apertura, type Campanas, type CanalMetricas, type CanalesMetricas, type DatosMetricas, type GrupoEstado, type MensajeAsesor, type PiezaCampana, type ResultadoActualizar, type ResumenCampana } from "./adminApi";
import { AvisoError, Cargando, EstadoChip, IconoAdmin, Metrica, Plegable, diaCorto, miles } from "./comun";
import { Linea } from "./Graficos";

// (8/11, Franco) Administración → Métricas: la app como centro de métricas de campañas (pedido de Beto). Dos preguntas: «¿Cuánto llegó?»
// (una tarjeta por canal: números desde la plataforma donde se puede, enlace y números anotados a mano donde no) y «¿Cuánto hicimos?»
// (una tarjeta por campaña, con el botón «¿Cómo le fue?» que resume con IA). Contrato con la API: web/maquetas/metricas-contrato.md.
// Vive en Gestión (Aprobación), para quienes aprueban y admins (8/11, Franco). El ítem del menú está oculto (MOSTRAR_METRICAS en Aprobacion.tsx); la ruta /aprobacion/metricas funciona igual.
definirAyuda("metricas", {
  titulo: "Métricas",
  que: "Cuánto llegó cada canal y cuánto hicimos en cada campaña.",
  pasos: [
    { id: "asesor", texto: "Preguntale al asesor cómo vienen las campañas: te nombra las piezas y de dónde salen los números." },
    { id: "actualizar", texto: "Trae los números de Instagram, Facebook y YouTube al momento." },
    { id: "canal", texto: "Cada canal muestra sus números contra los 28 días anteriores, su tendencia y lo último que salió." },
    { id: "anotar", texto: "Lo que la plataforma no deja leer, cargalo a mano con el período." },
    { id: "campana", texto: "Cada campaña muestra sus piezas por estado y canal. Las sueltas se mueven a una campaña." },
    { id: "resumen", texto: "«¿Cómo le fue?» arma un resumen con los números que hay y avisa qué faltó." },
  ],
});

type Periodo = { dias?: number; mes?: string };

/** Un mensaje de la conversación con el asesor (vive en el estado de la pantalla). */
interface Turno extends MensajeAsesor {
  fuentes?: string[];
  falto?: string[];
  capturado?: string | null;
}

const ICONO_CANAL: Record<string, NombreIcono> = { instagram: "imagen", facebook: "usuarios", youtube: "pelicula", mail: "sobre", sitio: "casa", whatsapp: "celular" };

const ETIQUETA: Record<string, string> = {
  alcance: "alcance",
  vistas: "vistas",
  interacciones: "interacciones",
  me_gusta: "me gusta",
  comentarios: "comentarios",
  guardados: "guardados",
  compartidos: "compartidos",
  clics: "clics",
  seguidores: "seguidores",
  seguidores_nuevos: "seguidores nuevos",
  visitas: "visitas",
  visitantes: "visitantes",
  enviados: "enviados",
  aperturas: "aperturas",
  respuestas: "respuestas",
  // (12/11, Franco) claves nuevas
  enviados_frase: "mails de la Frase del día",
  lista_contactos: "contactos en la lista",
  minutos_vistos: "minutos vistos",
};
// (12/11, Franco) cómo se lee cada número en la línea «vs. período anterior» y en las tarjetas (ETIQUETA va en minúscula; esto es lo que se ve grande)
const ETIQUETA_GRANDE: Record<string, string> = {
  enviados_frase: "Frase del día: mails enviados",
  lista_contactos: "Lista: contactos",
  minutos_vistos: "Minutos vistos",
  seguidores_nuevos: "Suscriptores nuevos",
};

/** Las claves que se pueden anotar según el canal. */
function clavesDe(canal: string): string[] {
  if (canal === "mail") return ["enviados", "aperturas", "clics"];
  if (canal === "sitio") return ["visitas", "visitantes"];
  if (canal === "whatsapp") return ["alcance", "clics", "respuestas"];
  return ["alcance", "vistas", "me_gusta", "comentarios", "compartidos", "seguidores"];
}

const API_CHIP: Record<CanalMetricas["api"], { estado: string; texto: string }> = {
  disponible: { estado: "ok", texto: "conectado" },
  sin_permiso: { estado: "aviso", texto: "falta un permiso" },
  pendiente: { estado: "sin_dato", texto: "sin datos todavía" },
  no_hay: { estado: "sin_dato", texto: "se mira en la plataforma" },
  error: { estado: "error", texto: "no pude leer" },
};

/** Hasta 3 números grandes según el canal; los que falten no se inventan.
 *  (12/11, Franco) Mail: sin campañas de Perfit (enviados 0) se muestran los mails de la Frase del día y los contactos de la lista, sin los ceros de las campañas.
 *  YouTube: minutos vistos y suscriptores nuevos entran entre los grandes. */
function grandes(d: DatosMetricas, canal = ""): [string, number][] {
  const out: [string, number][] = [];
  const v = (k: string) => (typeof d[k] === "number" ? (d[k] as number) : null);
  let claves = ["alcance", "vistas", "seguidores", "interacciones", "me_gusta", "visitas", "visitantes", "enviados", "aperturas", "clics"];
  if (canal === "youtube") claves = ["vistas", "minutos_vistos", "seguidores_nuevos", "seguidores", "me_gusta", "comentarios"];
  if (canal === "mail") {
    const hayCampanas = (v("enviados") ?? 0) > 0;
    const hayFrase = v("enviados_frase") !== null || v("lista_contactos") !== null;
    claves = hayCampanas ? ["enviados", "aperturas", "clics", "enviados_frase", "lista_contactos"] : hayFrase ? ["enviados_frase", "lista_contactos"] : ["enviados", "aperturas", "clics"];
  }
  if (canal === "sitio") claves = ["visitas", "visitantes", "comentarios", "me_gusta"];
  // (12/11, Franco) un cero grande no dice nada («0 me gusta» en el sitio): va primero lo que tiene valor; los ceros solo si no hay otra cosa
  const ceros: [string, number][] = [];
  for (const k of claves) {
    const n = v(k);
    if (n === null) continue;
    (n === 0 ? ceros : out).push([k, n]);
    if (out.length === 3) break;
  }
  return out.length ? out : ceros.slice(0, 3);
}

/** (12/11, Franco) El número principal de cada canal, el que se dibuja en la tendencia: alcance en Instagram y Facebook, vistas en YouTube,
 *  visitas en el sitio, mails de la Frase del día (o enviados) en el mail. */
function clavePrincipal(canal: string, d?: DatosMetricas | null): string | null {
  if (canal === "instagram" || canal === "facebook") return "alcance";
  if (canal === "youtube") return "vistas";
  if (canal === "sitio") return "visitas";
  if (canal === "mail") return d && typeof d.enviados_frase === "number" ? "enviados_frase" : d && typeof d.enviados === "number" && d.enviados > 0 ? "enviados" : "enviados_frase";
  return null;
}

type Variacion = { tipo: "sube" | "baja" | "igual" | "sin"; texto: string; detalle: string };

/** (12/11, Franco) Cuánto cambió un número contra el período anterior: flecha y texto corto. Los chicos (seguidores, lista) o con anterior en 0 van en cantidad;
 *  el resto, en porcentaje. Sin anterior (o sin esa clave en el anterior): «sin comparación todavía». */
function variacion(k: string, ahora: number, anterior?: Record<string, number> | null): Variacion {
  const antes = anterior?.[k];
  if (typeof antes !== "number") return { tipo: "sin", texto: "sin comparación todavía", detalle: "Todavía no hay una lectura de hace unos 28 días para comparar" };
  const dif = ahora - antes;
  const cantidad = k.startsWith("seguidores") || k === "lista_contactos" || antes === 0;
  const pct = cantidad ? 0 : Math.round((Math.abs(dif) / antes) * 100);
  if (dif === 0 || (!cantidad && pct === 0)) return { tipo: "igual", texto: "= igual que antes", detalle: "Casi igual que en los 28 días anteriores" };
  const sube = dif > 0;
  const cuanto = cantidad ? miles(Math.abs(dif)) : `${pct} %`;
  return { tipo: sube ? "sube" : "baja", texto: `${sube ? "↑ +" : "↓ -"}${cuanto}`, detalle: `${sube ? "Subió" : "Bajó"} ${cuanto} respecto de los 28 días anteriores (antes: ${miles(antes)})` };
}

/** (12/11, Franco) Cuántos días cubren los números del canal (por defecto 28). */
function diasDelPeriodo(desde?: string | null, hasta?: string | null): number {
  if (desde && hasta) {
    const n = Math.round((Date.parse(hasta.slice(0, 10)) - Date.parse(desde.slice(0, 10))) / 86400000);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return 28;
}

/** (12/11, Franco) «Últimos 28 días (15/10 al 12/11) · vs. los 28 anteriores» */
function subtituloPeriodo(canal: CanalMetricas): string | null {
  const u = canal.ultima;
  if (!u) return null;
  const dias = diasDelPeriodo(u.periodo_desde, u.periodo_hasta);
  const r = rango(u.periodo_desde, u.periodo_hasta);
  return `Últimos ${dias} días${u.periodo_desde && u.periodo_hasta && r ? ` (${r})` : ""}${canal.anterior ? ` · vs. los ${dias} anteriores` : ""}`;
}

/** (12/11, Franco) Los números de una pieza en una línea: «alcance 955 · vistas 1.173», o null si no tiene ninguno de esos. */
function numerosPieza(m: Record<string, unknown> | null | undefined, claves = ["alcance", "vistas", "enviados", "aperturas", "me_gusta", "comentarios", "compartidos", "clics"], tope = 3): string | null {
  if (!m) return null;
  const partes = claves.filter((k) => typeof m[k] === "number").slice(0, tope).map((k) => `${ETIQUETA[k]} ${miles(m[k] as number)}`);
  return partes.length ? partes.join(" · ") : null;
}

/** (12/11, Franco) La tasa principal del canal, en una frase corta; null si no se pudo calcular. */
function tasaPrincipal(canal: CanalMetricas): string | null {
  const t = (canal.tasas ?? {}) as Record<string, number | null>;
  const pct = (x: number) => `${Math.round(x * 1000) / 10} %`.replace(".", ",");
  if (t.alcance_sobre_seguidores != null) return `alcance = ${pct(t.alcance_sobre_seguidores)} de los seguidores`;
  if (t.aperturas_sobre_enviados != null) return `aperturas = ${pct(t.aperturas_sobre_enviados)} de los enviados`;
  if (t.visitas_por_dia != null) return `${miles(Math.round(t.visitas_por_dia))} visitas por día`;
  return null;
}

function rango(desde?: string | null, hasta?: string | null) {
  if (desde && hasta) return `${diaCorto(desde)} al ${diaCorto(hasta)}`;
  return desde ? `desde el ${diaCorto(desde)}` : hasta ? `hasta el ${diaCorto(hasta)}` : "";
}

const GRUPOS: { clave: GrupoEstado; estado: string; texto: string; columna: string }[] = [
  { clave: "publicada", estado: "publicada", texto: "publicadas", columna: "Publicadas" },
  { clave: "saliendo", estado: "enviando", texto: "saliendo", columna: "Saliendo" },
  { clave: "programada", estado: "programada", texto: "programadas", columna: "Programadas" },
  { clave: "en_aprobacion", estado: "a_aprobar", texto: "en aprobación", columna: "En aprobación" },
  { clave: "borrador", estado: "borrador", texto: "borradores", columna: "Borradores" },
  { clave: "prueba", estado: "prueba", texto: "de prueba", columna: "De prueba" },
  { clave: "cancelada", estado: "cancelada", texto: "canceladas", columna: "Canceladas" },
  { clave: "no_salio", estado: "error", texto: "no salieron", columna: "No salieron" },
];

function textoActualizar(nombre: string, r: { ok: boolean; piezas: number; error?: string | null }) {
  if (r.ok) return `${nombre}: ${r.piezas} ${r.piezas === 1 ? "pieza leída" : "piezas leídas"}`;
  const motivo = /conectar/i.test(r.error ?? "") ? "falta conectar con WordPress.com" : /permiso|autorizar/i.test(r.error ?? "") ? "falta un permiso en la conexión" : "no pude leer los números";
  return `${nombre}: ${motivo}`;
}

const mensaje = (e: unknown, defecto: string) => (e instanceof ErrorApi || e instanceof Error ? e.message : defecto);

export default function Metricas() {
  const [periodo, setPeriodo] = useState<Periodo>({ dias: 90 });
  const meses = useMemo(() => mesesRecientes(6), []);
  const [canales, setCanales] = useState<CanalesMetricas | null>(null);
  const [errorCanales, setErrorCanales] = useState<string | null>(null);
  const [campanas, setCampanas] = useState<Campanas | null>(null);
  const [errorCampanas, setErrorCampanas] = useState<string | null>(null);
  const [recarga, setRecarga] = useState(0); // sube al mover una pieza a otra campaña: vuelve a pedir las campañas
  const [actualizando, setActualizando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoActualizar | null>(null);
  const [errorActualizar, setErrorActualizar] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ ok: boolean; texto: string } | null>(null); // (8/11) lo que dejó volver de WordPress.com (?wordpress=ok|error&motivo=)
  const [busqueda, setBusqueda] = useSearchParams();
  const [charla, setCharla] = useState<Turno[]>([]);
  const agregarCharla = useCallback((...t: Turno[]) => setCharla((c) => [...c, ...t]), []);

  const cargarCanales = useCallback(async () => {
    try {
      setCanales(await adminApi.canalesMetricas());
      setErrorCanales(null);
    } catch (e) {
      setErrorCanales(mensaje(e, "No pude leer los canales."));
    }
  }, []);

  useEffect(() => {
    cargarCanales();
  }, [cargarCanales]);

  // (8/11, Franco) Al volver de WordPress.com la API redirige acá con ?wordpress=ok o ?wordpress=error&motivo=…: se avisa y se limpia la dirección.
  useEffect(() => {
    const w = busqueda.get("wordpress");
    if (!w) return;
    setAviso(w === "ok" ? { ok: true, texto: "WordPress.com conectado: tocá Actualizar." } : { ok: false, texto: busqueda.get("motivo") || "No pude conectar con WordPress.com." });
    const resto = new URLSearchParams(busqueda);
    resto.delete("wordpress");
    resto.delete("motivo");
    setBusqueda(resto, { replace: true });
  }, [busqueda, setBusqueda]);

  async function desconectarSitio() {
    if (!window.confirm("¿Desconectar el sitio de WordPress.com? Dejan de leerse sus estadísticas hasta que lo vuelvas a conectar.")) return;
    try {
      await adminApi.desconectarWordpress();
      setAviso({ ok: true, texto: "Sitio desconectado de WordPress.com." });
      await cargarCanales();
    } catch (e) {
      setAviso({ ok: false, texto: mensaje(e, "No pude desconectar el sitio.") });
    }
  }

  useEffect(() => {
    let vivo = true;
    adminApi
      .campanas(periodo.dias, periodo.mes)
      .then((c) => {
        if (!vivo) return;
        setCampanas(c);
        setErrorCampanas(null);
      })
      .catch((e) => vivo && setErrorCampanas(mensaje(e, "No pude leer las campañas.")));
    return () => {
      vivo = false;
    };
  }, [periodo, recarga]);

  async function actualizar() {
    setActualizando(true);
    setErrorActualizar(null);
    try {
      setResultado(await adminApi.actualizarMetricas());
      await cargarCanales();
    } catch (e) {
      setErrorActualizar(mensaje(e, "No pude actualizar."));
    } finally {
      setActualizando(false);
    }
  }

  const dias = campanas?.periodo.dias ?? periodo.dias ?? 90;
  const lista = campanas ? [...campanas.campanas, ...(campanas.sueltas.piezas_total > 0 ? [campanas.sueltas] : [])] : [];
  const t = campanas?.totales;

  return (
    <>
      <Asesor dias={periodo.dias ?? 90} charla={charla} agregar={agregarCharla} />
      <div className="seccion-cabecera">
        <h2>
          <IconoAdmin nombre="grafico" /> ¿Cuánto llegó?
        </h2>
        <div className="acciones">
          <span className="suave chico">Última lectura {canales?.actualizado ? hace(canales.actualizado) : "nunca"}</span>
          <button className="boton chico" onClick={actualizar} disabled={actualizando} data-ayuda="metricas.actualizar">
            <IconoAdmin nombre="regenerar" tam={14} /> {actualizando ? "Leyendo…" : "Actualizar desde las plataformas"}
          </button>
        </div>
      </div>
      {errorActualizar && <AvisoError texto={errorActualizar} />}
      {aviso && (aviso.ok ? (
        <div className="aviso met-resultado" role="status">
          <IconoAdmin nombre="info" tam={18} />
          <span>{aviso.texto}</span>
        </div>
      ) : (
        <AvisoError texto={aviso.texto} />
      ))}
      {resultado && (
        <div className="aviso met-resultado" role="status">
          <IconoAdmin nombre="info" tam={18} />
          <span>
            {textoActualizar("Instagram", resultado.instagram)}. {textoActualizar("Facebook", resultado.facebook)}. {textoActualizar("YouTube", resultado.youtube)}.{resultado.sitio ? ` ${textoActualizar("Sitio web", resultado.sitio)}.` : ""}{resultado.mail ? ` ${textoActualizar("Mail", resultado.mail)}.` : ""}
          </span>
        </div>
      )}
      {errorCanales && <AvisoError texto={errorCanales} />}
      {!canales && !errorCanales ? (
        <Cargando filas={3} />
      ) : (
        canales && (
          <div className="met-canales">
            {canales.canales.map((c) => (
              <TarjetaCanal key={c.clave} canal={c} alGuardar={cargarCanales} alDesconectar={desconectarSitio} />
            ))}
          </div>
        )
      )}

      <div className="seccion-cabecera met-hicimos">
        <h2>
          <IconoAdmin nombre="megafono" /> ¿Cuánto hicimos?
        </h2>
        <div className="acciones periodo" role="group" aria-label="Período">
          {[7, 28, 90].map((d) => (
            <button key={d} className={"boton chico" + (periodo.dias === d ? " activo" : "")} onClick={() => {
                setCampanas(null);
                setPeriodo({ dias: d });
              }} aria-pressed={periodo.dias === d}>
              {d} días
            </button>
          ))}
          <select value={periodo.mes ?? ""} onChange={(e) => {
              setCampanas(null);
              setPeriodo(e.target.value ? { mes: e.target.value } : { dias: 90 });
            }} aria-label="Un mes">
            <option value="">un mes…</option>
            {meses.map((m) => (
              <option key={m.mes} value={m.mes}>
                {m.texto}
              </option>
            ))}
          </select>
        </div>
      </div>
      {errorCampanas && <AvisoError texto={errorCampanas} />}
      {!campanas && !errorCampanas && <Cargando filas={4} />}
      {campanas && t && (
        <>
          <div className="metricas">
            <Metrica etiqueta="Piezas hechas" valor={miles(t.piezas)} detalle={campanas.periodo.texto} />
            <Metrica etiqueta="Publicadas" valor={miles(t.publicada)} />
            <Metrica etiqueta="Programadas" valor={miles(t.programada)} />
            <Metrica etiqueta="En aprobación" valor={miles(t.en_aprobacion)} />
          </div>
          {(t.prueba > 0 || t.borrador > 0) && (
            <p className="suave chico met-aparte-total">
              Aparte: {t.prueba} en prueba, {t.borrador} {t.borrador === 1 ? "borrador" : "borradores"}.
            </p>
          )}
          {lista.length === 0 ? (
            <EstadoVacio icono="carpeta" titulo="No hay campañas con piezas en este período" texto="Probá con un período más largo, o armá piezas desde Diseñar." />
          ) : (
            lista.map((c) => <TarjetaCampana
                key={c.id}
                campana={c}
                dias={dias}
                alMover={() => setRecarga((n) => n + 1)}
                alResumir={(r) => agregarCharla({ rol: "usuario", texto: `¿Cómo le fue a ${c.nombre}?` }, { rol: "asesor", texto: r.texto, fuentes: r.fuentes, falto: r.falto, capturado: r.capturado })}
              />)
          )}
        </>
      )}
    </>
  );
}

const NOTA_CARGA = "Para lo que la plataforma no nos deja leer solo: copiá acá lo que ves en sus estadísticas, con el período.";

function TarjetaCanal({ canal, alGuardar, alDesconectar }: { canal: CanalMetricas; alGuardar: () => Promise<void>; alDesconectar: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const chip = API_CHIP[canal.api] ?? API_CHIP.error;
  const nums = canal.ultima ? grandes(canal.ultima.datos, canal.clave) : [];
  const tasa = tasaPrincipal(canal);
  const subtitulo = subtituloPeriodo(canal);
  const [serie, setSerie] = useState<SerieCanal | null>(null);
  const principal = clavePrincipal(canal.clave, canal.ultima?.datos);
  const capturado = canal.ultima?.capturado;
  useEffect(() => {
    // la tendencia es un extra: si no se puede leer, la tarjeta sale igual sin ella
    if (!principal || !capturado) return;
    let vivo = true;
    adminApi
      .serieMetricas(canal.clave, 28)
      .then((r) => vivo && setSerie(r))
      .catch(() => {});
    return () => {
      vivo = false;
    };
  }, [canal.clave, principal, capturado]);
  const ultimas = canal.ultimas_piezas ?? [];
  const manual = canal.manual;
  const manualNums = manual ? Object.entries(manual.datos).filter(([k, v]) => typeof v === "number" && ETIQUETA[k]) : [];
  const conectado = canal.api === "disponible"; // si la plataforma los lee sola, no se carga a mano
  const boton = (
    <button className="boton chico" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto} data-ayuda="metricas.anotar">
      <IconoAdmin nombre="lapiz" tam={14} /> Cargar números a mano
    </button>
  );
  return (
    <article className="tarjeta met-canal" data-ayuda="metricas.canal" aria-label={canal.texto}>
      <header className="met-canal-cab">
        <h3>
          <Icono nombre={ICONO_CANAL[canal.clave] ?? "megafono"} tam={18} /> {canal.texto}
        </h3>
        {canal.api === "no_hay" && canal.enlace ? (
          <a className="met-enlace-chip" href={canal.enlace} target="_blank" rel="noopener noreferrer">
            {canal.enlace_texto ?? "Abrir"} <IconoAdmin nombre="externo" tam={12} />
          </a>
        ) : (
          <EstadoChip estado={chip.estado} texto={chip.texto} />
        )}
      </header>
      {canal.api !== "disponible" && canal.nota_api && <p className="suave chico met-nota">{canal.nota_api}</p>}
      {canal.ultima && nums.length > 0 && (
        <>
          {subtitulo && <div className="suave chico met-periodo">{subtitulo}</div>}
          <div className="met-numeros">
            {nums.map(([k, n]) => {
              const v = variacion(k, n, canal.anterior?.datos);
              return (
                <div key={k} className="met-numero">
                  <div className="metrica-valor">{miles(n)}</div>
                  <div className="metrica-etiqueta">{ETIQUETA_GRANDE[k] ?? ETIQUETA[k]}</div>
                  <span className={"met-var " + v.tipo} title={v.detalle}>
                    {v.texto}
                  </span>
                </div>
              );
            })}
          </div>
          {principal && <Tendencia serie={serie} clave={principal} dias={diasDelPeriodo(canal.ultima.periodo_desde, canal.ultima.periodo_hasta)} />}
        </>
      )}
      {ultimas.length > 0 && (
        <div className="met-bloque">
          <h4>Lo último que salió</h4>
          <ul className="met-lista-piezas">
            {ultimas.map((p) => (
              <FilaPiezaCanal key={p.id} pieza={p} />
            ))}
          </ul>
        </div>
      )}
      {canal.mejor_pieza && (
        <div className="met-bloque">
          <h4>La que mejor anduvo</h4>
          <ul className="met-lista-piezas">
            <FilaPiezaCanal pieza={canal.mejor_pieza} />
          </ul>
        </div>
      )}
      {manual && manualNums.length > 0 && (
        <div className="met-manual">
          <strong className="chico">Anotado a mano</strong>
          <div className="met-manual-nums">
            {manualNums.map(([k, n]) => (
              <span key={k}>
                {ETIQUETA[k]} <b>{miles(n as number)}</b>
              </span>
            ))}
          </div>
          <div className="suave chico">
            {rango(manual.periodo_desde, manual.periodo_hasta) ? `${rango(manual.periodo_desde, manual.periodo_hasta)} · ` : ""}
            {manual.por ? `por ${manual.por}, ` : ""}
            el {fechaCompleta(manual.capturado, false)}
          </div>
          {manual.nota && <div className="chico">{manual.nota}</div>}
        </div>
      )}
      {canal.ultima && nums.length > 0 && (
        <div className="met-pie">
          {tasa && <div className="suave chico met-tasa">{tasa}</div>}
          {canal.clave === "mail" && (canal.ultima.datos.enviados_frase !== undefined || canal.ultima.datos.lista_contactos !== undefined) && (
            <div className="suave chico met-nota">Las aperturas de la Frase del día no las da Perfit por ahora; las campañas sí.</div>
          )}
          <div className="suave chico">Leído {hace(canal.ultima.capturado)}</div>
        </div>
      )}
      <div className="met-acciones">
        {/* (8/11) Sitio web: «Conectar» es un link normal a la API (redirige a WordPress.com con la cookie de admin), no un fetch */}
        {canal.conectar_url && !canal.conectado && (
          <a className="boton primario chico" href={`${BASE}${canal.conectar_url}`}>
            <IconoAdmin nombre="externo" tam={14} /> Conectar con WordPress.com
          </a>
        )}
        {canal.conectar_url && canal.conectado && canal.api === "error" && (
          <a className="boton chico" href={`${BASE}${canal.conectar_url}`}>
            Volver a conectar con WordPress.com
          </a>
        )}
        {canal.enlace && (
          <a className="boton chico" href={canal.enlace} target="_blank" rel="noopener noreferrer">
            {canal.enlace_texto ?? "Abrir"} <IconoAdmin nombre="externo" tam={14} />
          </a>
        )}
        {!conectado && boton}
      </div>
      {canal.conectado && (
        <button type="button" className="met-desconectar" onClick={alDesconectar}>
          Desconectar
        </button>
      )}
      {!conectado && <p className="suave chico met-nota-carga">{NOTA_CARGA}</p>}
      {/* (8/11, Franco) si la plataforma los lee sola no se ofrece cargarlos a mano: confundía («¿para qué, si es automático?») */}
      {abierto && (
        <FormularioAnotar
          canal={canal}
          alCerrar={() => setAbierto(false)}
          alGuardar={async () => {
            await alGuardar();
            setAbierto(false);
          }}
        />
      )}
    </article>
  );
}

/** (12/11, Franco) La tendencia del número principal: una línea chica, un punto por día. Con menos de 7 puntos se dice que es lo que se mide desde que empezamos. */
function Tendencia({ serie, clave, dias }: { serie: SerieCanal | null; clave: string; dias: number }) {
  const nombre = ETIQUETA_GRANDE[clave] ?? ETIQUETA[clave];
  const puntos = (serie?.puntos ?? [])
    .filter((p) => typeof p.datos[clave] === "number")
    .map((p) => ({ etiqueta: diaCorto(p.dia), valor: p.datos[clave], titulo: `${diaCorto(p.dia)}: ${miles(p.datos[clave])} ${nombre} en los ${dias} días hasta ese día` }));
  if (puntos.length === 0) return null;
  if (puntos.length === 1) return <div className="suave chico met-tendencia">Un solo día medido por ahora: la tendencia aparece con el siguiente.</div>;
  return (
    <div className="met-tendencia">
      <Linea puntos={puntos} titulo={`Tendencia: ${nombre}, un punto por día`} formato={miles} />
      <div className="suave chico">{puntos.length < 7 ? "tendencia desde que empezamos a medir" : `${nombre}: total de ${dias} días, medido cada día`}</div>
    </div>
  );
}

/** (12/11, Franco) Una pieza en «Lo último que salió» / «La que mejor anduvo»: título (con link si lo hay), formato y fecha, y sus números en una línea. */
function FilaPiezaCanal({ pieza }: { pieza: PiezaCanal }) {
  const nums = numerosPieza(pieza.metricas as Record<string, unknown> | null);
  const fecha = pieza.fecha ? diaCorto(pieza.fecha.slice(0, 10)) : null;
  const detalle = [pieza.formato, fecha, pieza.campana].filter(Boolean).join(" · ");
  return (
    <li>
      {pieza.ver_url ? (
        <a href={pieza.ver_url} target="_blank" rel="noopener noreferrer">
          {pieza.titulo || "(sin título)"}
        </a>
      ) : (
        <span className="met-pieza-titulo">{pieza.titulo || "(sin título)"}</span>
      )}
      {detalle && <span className="suave chico"> · {detalle}</span>}
      <div className="met-pieza-nums">{nums ?? "sin números todavía"}</div>
    </li>
  );
}

function FormularioAnotar({ canal, alCerrar, alGuardar }: { canal: CanalMetricas; alCerrar: () => void; alGuardar: () => Promise<void> }) {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [valores, setValores] = useState<Record<string, string>>({});
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    const datos: Record<string, number> = {};
    for (const [k, v] of Object.entries(valores)) {
      if (v.trim() === "") continue;
      const n = Number(v);
      if (!Number.isInteger(n) || n < 0) {
        setError(`«${ETIQUETA[k]}» tiene que ser un número entero, de cero para arriba.`);
        return;
      }
      datos[k] = n;
    }
    if (Object.keys(datos).length === 0) {
      setError("Cargá al menos un número.");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await adminApi.anotarMetrica({ ambito: "canal", ref: canal.clave, canal: canal.clave, periodo_desde: desde || null, periodo_hasta: hasta || null, datos, nota: nota.trim() || null });
      await alGuardar();
    } catch (err) {
      setError(mensaje(err, "No pude guardar los números."));
      setGuardando(false);
    }
  }

  return (
    <form className="met-form" onSubmit={enviar} aria-label={`Cargar números de ${canal.texto}`}>
      <div className="met-form-fechas">
        <label>
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </label>
      </div>
      <div className="met-form-campos">
        {clavesDe(canal.clave).map((k) => (
          <label key={k}>
            {ETIQUETA[k][0].toUpperCase() + ETIQUETA[k].slice(1)}
            <input type="number" min={0} step={1} inputMode="numeric" value={valores[k] ?? ""} onChange={(e) => setValores((v) => ({ ...v, [k]: e.target.value }))} />
          </label>
        ))}
      </div>
      <label>
        Nota
        <input type="text" value={nota} onChange={(e) => setNota(e.target.value)} placeholder="De dónde sacaste los números (opcional)" />
      </label>
      {error && <AvisoError texto={error} />}
      <div className="met-acciones">
        <button type="submit" className="boton chico primario" disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        <button type="button" className="boton chico" onClick={alCerrar} disabled={guardando}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function lineaMetricas(p: PiezaCampana): string | null {
  const m = p.metricas;
  if (!m) return null;
  const partes = ["alcance", "vistas", "me_gusta", "comentarios", "guardados", "compartidos", "clics", "interacciones"].filter((k) => typeof m[k] === "number").map((k) => `${ETIQUETA[k]} ${miles(m[k] as number)}`);
  if (partes.length === 0) return null;
  const fuente = m.fuente === "manual" ? "anotado a mano" : `desde ${p.canal_texto}${m.capturado ? ", " + hace(m.capturado) : ""}`;
  return `${partes.join(" · ")} · ${fuente}`;
}

/** (12/11, Franco) Cuántas piezas de una campaña se ven sin abrir nada; el resto va plegado. */
const PIEZAS_A_LA_VISTA = 5;

/** Las campañas que no son un Proyecto: sus piezas se pueden mover a una campaña de verdad. */
const MOVIBLES = ["sueltas", "frase_del_dia"];

function TarjetaCampana({ campana, dias, alResumir, alMover }: { campana: Campana; dias: number; alResumir: (r: ResumenCampana) => void; alMover: () => void }) {
  const [guardado, setGuardado] = useState<ResumenCampana | null>(null);
  const [cargando, setCargando] = useState(false);
  const [nuevo, setNuevo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    adminApi
      .resumenGuardado(campana.id)
      .then((r) => vivo && setGuardado(r))
      .catch(() => {}); // sin resumen guardado la tarjeta funciona igual
    return () => {
      vivo = false;
    };
  }, [campana.id]);

  async function resumir() {
    setCargando(true);
    setError(null);
    try {
      const r = await adminApi.resumir(campana.id, dias);
      setGuardado(r);
      setNuevo(true);
      alResumir(r);
    } catch (e) {
      setError(mensaje(e, "No pude armar el resumen."));
    } finally {
      setCargando(false);
    }
  }

  // (8/11, Franco) los borradores no son trabajo hecho: van plegados aparte y no entran en los chips ni en la tabla
  const hechas = GRUPOS.filter((g) => g.clave !== "borrador");
  const grupos = hechas.filter((g) => (campana.por_estado[g.clave] ?? 0) > 0);
  // (12/11, Franco) sin nada hecho (ni publicada, ni saliendo, ni programada, ni en aprobación) no se arma tabla: se dice y se cuentan aparte los otros estados
  const piezasHechas = (["publicada", "saliendo", "programada", "en_aprobacion"] as GrupoEstado[]).reduce((n, g) => n + (campana.por_estado[g] ?? 0), 0);
  const nBorradores = campana.por_estado.borrador ?? 0;
  const aparte = [
    [nBorradores, nBorradores === 1 ? "borrador" : "borradores"],
    [campana.por_estado.cancelada ?? 0, (campana.por_estado.cancelada ?? 0) === 1 ? "cancelada" : "canceladas"],
    [campana.por_estado.no_salio ?? 0, (campana.por_estado.no_salio ?? 0) === 1 ? "no salió" : "no salieron"],
    [campana.por_estado.prueba ?? 0, "de prueba"],
  ].filter(([n]) => (n as number) > 0).map(([n, t]) => `${n} ${t}`);
  const filas = Object.entries(campana.por_canal);
  const columnas = hechas.filter((g) => filas.some(([, f]) => (f[g.clave] ?? 0) > 0));
  const borradores = campana.piezas.filter((p) => p.estado_grupo === "borrador");
  const piezas = campana.piezas.filter((p) => p.estado_grupo !== "borrador");
  const movible = MOVIBLES.includes(campana.id);
  const nombresCanal = new Map(campana.piezas.map((p) => [p.canal, p.canal_texto]));

  return (
    <section className="tarjeta met-campana" data-ayuda="metricas.campana" aria-label={campana.nombre ?? undefined}>
      <header className="met-campana-cab">
        <h3 style={campana.color ? { borderLeft: `4px solid ${campana.color}`, paddingLeft: 8 } : undefined}>
          {campana.emoji && <span aria-hidden="true">{campana.emoji} </span>}
          {campana.nombre}
        </h3>
        {campana.dueno && <span className="suave chico">de {campana.dueno}</span>}
      </header>
      {campana.descripcion && <p className="suave chico met-descripcion">{campana.descripcion}</p>}
      {piezasHechas === 0 && campana.piezas_total > 0 ? (
        <div className="met-chips met-vacia">
          <span>Todavía no salió nada de esta campaña</span>
          {aparte.length > 0 && <span className="suave chico">{aparte.join(" · ")}</span>}
        </div>
      ) : (
        <div className="met-chips">
          {grupos.length === 0 ? (
            <span className="suave chico">{`Sin piezas en este período (${campana.piezas_total} en total).`}</span>
          ) : (
            grupos.map((g) => <ChipEstado key={g.clave} estado={g.estado} texto={`${campana.por_estado[g.clave]} ${g.texto}`} />)
          )}
        </div>
      )}
      {piezasHechas > 0 && filas.length > 0 && columnas.length > 0 && (
        <div className="met-tabla-caja">
          <table className="met-tabla">
            <thead>
              <tr>
                <th scope="col">Canal</th>
                {columnas.map((g) => (
                  <th key={g.clave} scope="col" className="num">
                    {g.columna}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map(([canal, f]) => (
                <tr key={canal}>
                  <th scope="row">{nombresCanal.get(canal) ?? canal}</th>
                  {columnas.map((g) => (
                    <td key={g.clave} className="num">
                      {f[g.clave] || "·"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {piezas.length > 0 && (
        <>
          <h4 className="met-piezas-titulo">Piezas ({piezas.length})</h4>
          <ListaPiezas piezas={piezas.slice(0, PIEZAS_A_LA_VISTA)} movible={movible} alMover={alMover} />
          {piezas.length > PIEZAS_A_LA_VISTA && (
            <Plegable titulo={`Ver las ${piezas.length - PIEZAS_A_LA_VISTA} restantes`}>
              <ListaPiezas piezas={piezas.slice(PIEZAS_A_LA_VISTA)} movible={movible} alMover={alMover} />
            </Plegable>
          )}
        </>
      )}
      {borradores.length > 0 && (
        <Plegable titulo={`${borradores.length} ${borradores.length === 1 ? "borrador" : "borradores"}`} resumen="sin contar como hechas">
          <ListaPiezas piezas={borradores} movible={movible} alMover={alMover} />
        </Plegable>
      )}

      <div className="met-resumen">
        <button className="boton chico" onClick={resumir} disabled={cargando} data-ayuda="metricas.resumen">
          <IconoAdmin nombre="info" tam={14} /> {guardado ? "Volver a resumir" : "¿Cómo le fue?"}
        </button>
        {cargando && (
          <p className="suave chico" role="status">
            Leyendo las piezas y sus números…
          </p>
        )}
        {error && <AvisoError texto={error} />}
        {guardado && !cargando && <ResumenVista key={guardado.capturado} r={guardado} abierto={nuevo} />}
      </div>
    </section>
  );
}

function ListaPiezas({ piezas, movible, alMover }: { piezas: PiezaCampana[]; movible: boolean; alMover: () => void }) {
  return (
    <ul className="met-piezas">
      {piezas.map((p) => {
        const linea = lineaMetricas(p);
        const g = GRUPOS.find((x) => x.clave === p.estado_grupo);
        return (
          <li key={p.id}>
            <div className="met-pieza-cab">
              <strong>{p.titulo || "(sin título)"}</strong>
              {numerosPieza(p.metricas, ["alcance", "vistas", "enviados"], 3) && <span className="met-pieza-nums">{numerosPieza(p.metricas, ["alcance", "vistas", "enviados"], 3)}</span>}
              <span className="suave chico">
                {p.canal_texto} · {diaCorto((p.fecha ?? "").slice(0, 10))}
              </span>
              <ChipEstado estado={g?.estado ?? p.estado} texto={g?.texto.replace(/s$/, "") ?? p.estado} icono={false} />
              {p.ver_url && (
                <a href={p.ver_url} target="_blank" rel="noopener noreferrer" className="chico">
                  ver
                </a>
              )}
            </div>
            <div className="suave chico">{linea ?? "sin números"}</div>
            {movible && <MoverACampana pieza={p} alMover={alMover} />}
          </li>
        );
      })}
    </ul>
  );
}

const NUEVA = "__nueva";

/** (8/11, Franco) «Mover a campaña» de una pieza suelta o de la Frase del día: elige un Proyecto de los que puede editar, o crea uno nuevo. */
function MoverACampana({ pieza, alMover }: { pieza: PiezaCampana; alMover: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [proyectos, setProyectos] = useState<Proyecto[] | null>(null);
  const [elegido, setElegido] = useState("");
  const [nombre, setNombre] = useState("");
  const [moviendo, setMoviendo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function abrir() {
    setAbierto((a) => !a);
    if (proyectos) return;
    try {
      const r = await apiProyectos.listar();
      setProyectos(r.proyectos.filter((p) => p.permiso !== "ver").sort((a, b) => a.nombre.localeCompare(b.nombre, "es")));
    } catch (e) {
      setError(mensaje(e, "No pude leer tus campañas."));
    }
  }

  async function mover(e: FormEvent) {
    e.preventDefault();
    if (!elegido || (elegido === NUEVA && !nombre.trim())) return;
    setMoviendo(true);
    setError(null);
    try {
      const id = elegido === NUEVA ? (await apiProyectos.crear({ nombre: nombre.trim() })).id : elegido;
      await apiProyectos.agregarItem(id, "pieza", pieza.id);
      alMover();
    } catch (err) {
      setError(mensaje(err, "No pude mover la pieza a esa campaña."));
      setMoviendo(false);
    }
  }

  return (
    <div className="met-mover">
      <button type="button" className="boton chico sutil" onClick={abrir} aria-expanded={abierto}>
        <IconoAdmin nombre="carpeta" tam={14} /> Mover a campaña
      </button>
      {abierto && (
        <form className="met-mover-form" onSubmit={mover} aria-label={`Mover «${pieza.titulo || "pieza"}» a una campaña`}>
          <select value={elegido} onChange={(e) => setElegido(e.target.value)} aria-label="Campaña de destino" disabled={!proyectos || moviendo}>
            <option value="">{proyectos ? "Elegí una campaña…" : "Cargando…"}</option>
            {(proyectos ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.emoji ? `${p.emoji} ` : ""}
                {p.nombre}
              </option>
            ))}
            <option value={NUEVA}>Nueva campaña…</option>
          </select>
          {elegido === NUEVA && <input type="text" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre de la campaña" aria-label="Nombre de la campaña nueva" maxLength={80} autoFocus />}
          <button type="submit" className="boton chico primario" disabled={moviendo || !elegido || (elegido === NUEVA && !nombre.trim())}>
            {moviendo ? "Moviendo…" : "Mover"}
          </button>
        </form>
      )}
      {error && <AvisoError texto={error} />}
    </div>
  );
}

const SUGERENCIAS = ["¿Cómo nos fue esta semana?", "¿Qué campaña rindió mejor?", "¿Qué canal conviene para la próxima campaña?"];

function Asesor({ dias, charla, agregar }: { dias: number; charla: Turno[]; agregar: (...t: Turno[]) => void }) {
  const [apertura, setApertura] = useState<Apertura | null>(null);
  const [errorApertura, setErrorApertura] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fin = useRef<HTMLDivElement>(null);

  // la apertura se pide al entrar (la API la rehace sola si cambiaron los datos) y con «Volver a mirar» (8/11, Franco)
  const [remirando, setRemirando] = useState(false);
  const pedirApertura = useCallback((forzar = false) => {
    let vivo = true;
    if (forzar) setRemirando(true);
    adminApi
      .asesorApertura(dias, forzar)
      .then((a) => vivo && setApertura(a))
      .catch((e) => vivo && setErrorApertura(mensaje(e, "No pude armar el mensaje de hoy.")))
      .finally(() => vivo && setRemirando(false));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    return pedirApertura(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fin.current?.scrollIntoView?.({ block: "nearest" });
  }, [charla.length, pensando]);

  async function preguntar(q: string) {
    const pregunta = q.trim();
    if (!pregunta || pensando) return;
    const nuevo: Turno = { rol: "usuario", texto: pregunta };
    const previos: MensajeAsesor[] = [...charla, nuevo].map((m) => ({ rol: m.rol, texto: m.texto }));
    agregar(nuevo);
    setTexto("");
    setPensando(true);
    setError(null);
    try {
      const r = await adminApi.preguntarAsesor(previos, dias);
      agregar({ rol: "asesor", texto: r.texto, fuentes: r.fuentes, falto: r.falto });
    } catch (e) {
      setError(mensaje(e, "No pude responder."));
    } finally {
      setPensando(false);
    }
  }

  return (
    <section className="tarjeta met-asesor" data-ayuda="metricas.asesor" aria-label="Tu asesor de campañas">
      <h2 className="met-asesor-titulo">
        <IconoAdmin nombre="info" /> Tu asesor de campañas
      </h2>
      {!apertura && !errorApertura && (
        <p className="suave chico" role="status">
          Mirando las campañas y sus números…
        </p>
      )}
      {errorApertura && <AvisoError texto={errorApertura} />}
      <div className="met-charla" aria-live="polite">
        {apertura && <BurbujaAsesor t={{ rol: "asesor", texto: apertura.texto, fuentes: apertura.fuentes, falto: apertura.falto }} cabecera={apertura.nuevo ? "hoy" : `del ${fechaCompleta(apertura.capturado, false)}`} />}
        {apertura && (
          <p className="suave chico met-remirar">
            Se rehace sola cuando cambian las campañas o los números.{" "}
            <button type="button" className="enlace" onClick={() => pedirApertura(true)} disabled={remirando}>
              {remirando ? "Mirando de nuevo…" : "Volver a mirar ahora"}
            </button>
          </p>
        )}
        {charla.map((m, i) =>
          m.rol === "usuario" ? (
            <div key={i} className="met-burbuja usuario">
              {m.texto}
            </div>
          ) : (
            <BurbujaAsesor key={i} t={m} />
          ),
        )}
        {pensando && (
          <p className="suave chico" role="status">
            Mirando las campañas y sus números…
          </p>
        )}
        <div ref={fin} />
      </div>
      {error && <AvisoError texto={error} />}
      {charla.length === 0 && (
        <div className="met-sugerencias">
          {SUGERENCIAS.map((s) => (
            <button key={s} type="button" className="boton chico" onClick={() => preguntar(s)} disabled={pensando}>
              {s}
            </button>
          ))}
        </div>
      )}
      <form
        className="met-pregunta"
        onSubmit={(e) => {
          e.preventDefault();
          preguntar(texto);
        }}
      >
        <input type="text" value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Preguntale algo sobre las campañas" aria-label="Tu pregunta" disabled={pensando} />
        <button type="submit" className="boton chico primario" disabled={pensando || !texto.trim()}>
          Preguntar
        </button>
      </form>
    </section>
  );
}

function BurbujaAsesor({ t, cabecera }: { t: Turno; cabecera?: string }) {
  return (
    <div className="met-burbuja asesor">
      {cabecera && <div className="suave chico">{cabecera}</div>}
      <div className="msj-md met-texto" dangerouslySetInnerHTML={{ __html: aHtml(t.texto) }} />
      {(t.fuentes?.length ?? 0) > 0 && (
        <details className="met-det">
          <summary>De dónde salen los números</summary>
          <ul className="met-lista">
            {t.fuentes!.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </details>
      )}
      {(t.falto?.length ?? 0) > 0 && (
        <details className="met-det">
          <summary>Lo que faltó</summary>
          <ul className="met-lista">
            {t.falto!.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function ResumenVista({ r, abierto }: { r: ResumenCampana; abierto: boolean }) {
  return (
    <Plegable titulo={`Resumido el ${fechaCompleta(r.capturado, false)}`} abierto={abierto}>
      <div className="msj-md met-texto" dangerouslySetInnerHTML={{ __html: aHtml(r.texto) }} />
      {r.fuentes.length > 0 && (
        <>
          <h4>De dónde salen los números</h4>
          <ul className="met-lista">
            {r.fuentes.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </>
      )}
      {r.falto.length > 0 && (
        <>
          <h4>Lo que faltó</h4>
          <ul className="met-lista">
            {r.falto.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </>
      )}
      {r.comparado_con && <p className="suave chico">Comparado con «{r.comparado_con}».</p>}
    </Plegable>
  );
}
