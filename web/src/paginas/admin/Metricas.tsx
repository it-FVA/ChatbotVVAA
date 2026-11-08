import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ErrorApi } from "../../api";
import { apiProyectos } from "../../apiProyectos";
import { definirAyuda } from "../../ayuda/registro";
import ChipEstado from "../../componentes/ChipEstado";
import { EstadoVacio } from "../../componentes/Comunes";
import { Icono, type NombreIcono } from "../../componentes/Iconos";
import { fechaCompleta, hace } from "../../util/fechas";
import { aHtml } from "../../util/markdown";
import { mesesRecientes } from "./Dashboard";
import type { Proyecto } from "../../tiposProyectos";
import { adminApi, type Campana, type Apertura, type Campanas, type CanalMetricas, type CanalesMetricas, type DatosMetricas, type GrupoEstado, type MensajeAsesor, type PiezaCampana, type ResultadoActualizar, type ResumenCampana } from "./adminApi";
import { AvisoError, Cargando, EstadoChip, IconoAdmin, Metrica, Plegable, diaCorto, miles } from "./comun";

// (8/11, Franco) Administración → Métricas: la app como centro de métricas de campañas (pedido de Beto). Dos preguntas: «¿Cuánto llegó?»
// (una tarjeta por canal: números desde la plataforma donde se puede, enlace y números anotados a mano donde no) y «¿Cuánto hicimos?»
// (una tarjeta por campaña, con el botón «¿Cómo le fue?» que resume con IA). Contrato con la API: web/maquetas/metricas-contrato.md.
// El ítem del menú está oculto (MOSTRAR_METRICAS en Administracion.tsx); la ruta /administracion/metricas funciona igual.
definirAyuda("metricas", {
  titulo: "Métricas",
  que: "Cuánto llegó cada canal y cuánto hicimos en cada campaña.",
  pasos: [
    { id: "asesor", texto: "Preguntale al asesor cómo vienen las campañas: te nombra las piezas y de dónde salen los números." },
    { id: "actualizar", texto: "Trae los números de Instagram, Facebook y YouTube al momento." },
    { id: "canal", texto: "Cada canal muestra sus números y un enlace para verlos en la plataforma." },
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

/** Hasta 4 números grandes: alcance, vistas, interacciones (o me gusta) y seguidores; los que falten no se inventan. */
function grandes(d: DatosMetricas): [string, number][] {
  const out: [string, number][] = [];
  const v = (k: string) => (typeof d[k] === "number" ? (d[k] as number) : null);
  for (const k of ["alcance", "vistas", "interacciones", "me_gusta", "seguidores", "visitas", "visitantes", "enviados", "aperturas", "clics"]) {
    if (k === "me_gusta" && v("interacciones") !== null) continue;
    const n = v(k);
    if (n !== null) out.push([k, n]);
    if (out.length === 4) break;
  }
  return out;
}

function rango(desde?: string | null, hasta?: string | null) {
  if (desde && hasta) return `${diaCorto(desde)} al ${diaCorto(hasta)}`;
  return desde ? `desde el ${diaCorto(desde)}` : hasta ? `hasta el ${diaCorto(hasta)}` : "";
}

const GRUPOS: { clave: GrupoEstado; estado: string; texto: string; columna: string }[] = [
  { clave: "publicada", estado: "publicada", texto: "publicadas", columna: "Publicadas" },
  { clave: "programada", estado: "programada", texto: "programadas", columna: "Programadas" },
  { clave: "en_aprobacion", estado: "a_aprobar", texto: "en aprobación", columna: "En aprobación" },
  { clave: "borrador", estado: "borrador", texto: "borradores", columna: "Borradores" },
  { clave: "prueba", estado: "prueba", texto: "de prueba", columna: "De prueba" },
  { clave: "no_salio", estado: "error", texto: "no salieron", columna: "No salieron" },
];

function textoActualizar(nombre: string, r: { ok: boolean; piezas: number; error?: string | null }) {
  if (r.ok) return `${nombre}: ${r.piezas} ${r.piezas === 1 ? "pieza leída" : "piezas leídas"}`;
  return `${nombre}: ${/permiso|autorizar/i.test(r.error ?? "") ? "falta un permiso en la conexión" : "no pude leer los números"}`;
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
            <IconoAdmin nombre="regenerar" tam={14} /> {actualizando ? "Leyendo…" : "Actualizar desde Instagram, Facebook y YouTube"}
          </button>
        </div>
      </div>
      {errorActualizar && <AvisoError texto={errorActualizar} />}
      {resultado && (
        <div className="aviso met-resultado" role="status">
          <IconoAdmin nombre="info" tam={18} />
          <span>
            {textoActualizar("Instagram", resultado.instagram)}. {textoActualizar("Facebook", resultado.facebook)}. {textoActualizar("YouTube", resultado.youtube)}.
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
              <TarjetaCanal key={c.clave} canal={c} alGuardar={cargarCanales} />
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

function TarjetaCanal({ canal, alGuardar }: { canal: CanalMetricas; alGuardar: () => Promise<void> }) {
  const [abierto, setAbierto] = useState(false);
  const chip = API_CHIP[canal.api] ?? API_CHIP.error;
  const nums = canal.ultima ? grandes(canal.ultima.datos) : [];
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
          <div className="met-numeros">
            {nums.map(([k, n]) => (
              <div key={k} className="met-numero">
                <div className="metrica-valor">{miles(n)}</div>
                <div className="metrica-etiqueta">{ETIQUETA[k]}</div>
              </div>
            ))}
          </div>
          <div className="suave chico">
            Leído {hace(canal.ultima.capturado)}
            {rango(canal.ultima.periodo_desde, canal.ultima.periodo_hasta) && ` · ${rango(canal.ultima.periodo_desde, canal.ultima.periodo_hasta)}`}
          </div>
        </>
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
      <div className="met-acciones">
        {canal.enlace && (
          <a className="boton chico" href={canal.enlace} target="_blank" rel="noopener noreferrer">
            {canal.enlace_texto ?? "Abrir"} <IconoAdmin nombre="externo" tam={14} />
          </a>
        )}
        {!conectado && boton}
      </div>
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
      <div className="met-chips">
        {grupos.length === 0 ? (
          <span className="suave chico">{borradores.length > 0 ? "Todavía sin piezas hechas en este período." : `Sin piezas en este período (${campana.piezas_total} en total).`}</span>
        ) : (
          grupos.map((g) => <ChipEstado key={g.clave} estado={g.estado} texto={`${campana.por_estado[g.clave]} ${g.texto}`} />)
        )}
      </div>
      {filas.length > 0 && columnas.length > 0 && (
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
        <Plegable titulo="Piezas" resumen={`${piezas.length}`}>
          <ListaPiezas piezas={piezas} movible={movible} alMover={alMover} />
        </Plegable>
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

  // la apertura es una por día: se pide al entrar, no cada vez que cambia el período
  useEffect(() => {
    let vivo = true;
    adminApi
      .asesorApertura(dias)
      .then((a) => vivo && setApertura(a))
      .catch((e) => vivo && setErrorApertura(mensaje(e, "No pude armar el mensaje de hoy.")));
    return () => {
      vivo = false;
    };
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
