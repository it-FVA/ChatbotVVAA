import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, ErrorApi } from "../../api";
import type { Estilo, Opciones } from "../../tipos";
import { ControlesEstilo, cssSubtitulo } from "../../componentes/Estilo";
import { useToast } from "../../componentes/Toasts";
import { adminApi, type CambioRegistro, type Config, type Precio } from "./adminApi";
import { AvisoError, Cargando, IconoAdmin, Plegable, fecha, hace } from "./comun";

// Administración → Configuración (22/10): precios de OpenAI por modelo (con fuente y fecha; aviso del precio promocional de
// gpt-5.6-sol hasta el 21/11/2026), presupuesto mensual, umbrales de capacidad, estilo por defecto de los subtítulos (mismos
// controles y endpoint del editor: PUT /recortes/estilo-defecto) y la Frase del día (interruptor, hora, canales, foto, pie).
// Cada bloque dice para qué sirve y quién lo cambió por última vez; todo se guarda con PUT /admin/config y queda registrado.

export default function Configuracion() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cambios, setCambios] = useState<CambioRegistro[]>([]);

  const cargar = useCallback(async () => {
    try {
      setCfg(await adminApi.config());
      setError(null);
      adminApi.cambios(200).then((c) => setCambios(c.filter((x) => x.accion === "config" || x.accion.startsWith("servicio_")))).catch(() => {});
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer la configuración.");
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <>
      <div className="seccion-cabecera">
        <h2>
          <IconoAdmin nombre="engranaje" /> Configuración
        </h2>
      </div>
      {error && <AvisoError texto={error} />}
      {!cfg ? (
        <Cargando filas={5} />
      ) : (
        <div className="config">
          <Precios cfg={cfg} onGuardado={cargar} />
          <Presupuesto cfg={cfg} onGuardado={cargar} />
          <Umbrales cfg={cfg} onGuardado={cargar} />
          <EstiloDefecto cfg={cfg} onGuardado={cargar} />
          <FraseDelDia cfg={cfg} onGuardado={cargar} />
          {cambios.length > 0 && (
            <Plegable titulo="Últimos cambios de configuración y servicios" resumen={`${cambios.length}`}>
              <ul className="cambios-lista">
                {cambios.slice(0, 40).map((c) => (
                  <li key={c.id}>
                    <span className="suave chico">{fecha(c.cuando)}</span> <strong>{c.quien}</strong> · {c.accion === "config" ? "cambió" : c.accion.replace("servicio_", "servicio: ")} <code>{c.usuario}</code>
                    {c.detalle && <span className="suave chico"> {resumirDetalle(c.detalle)}</span>}
                  </li>
                ))}
              </ul>
            </Plegable>
          )}
        </div>
      )}
    </>
  );
}

function resumirDetalle(d: Record<string, unknown>) {
  const t = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));
  if ("de" in d && "a" in d) return `${t(d.de)} → ${t(d.a)}`.slice(0, 160);
  return JSON.stringify(d).slice(0, 160);
}

function Bloque({ titulo, icono, explicacion, meta, children, acciones }: { titulo: string; icono: Parameters<typeof IconoAdmin>[0]["nombre"]; explicacion: ReactNode; meta?: { actualizado: string | null; por: string | null } | null; children: ReactNode; acciones?: ReactNode }) {
  return (
    <section className="tarjeta bloque-config" aria-label={titulo}>
      <header>
        <h3>
          <IconoAdmin nombre={icono} tam={18} /> {titulo}
        </h3>
        {meta?.actualizado && (
          <span className="suave chico" title={fecha(meta.actualizado)}>
            cambiado {hace(meta.actualizado)}
            {meta.por ? ` por ${meta.por}` : ""}
          </span>
        )}
      </header>
      <p className="suave chico explicacion">{explicacion}</p>
      {children}
      {acciones && <div className="acciones derecha">{acciones}</div>}
    </section>
  );
}

function useGuardar(onGuardado: () => void) {
  const { avisar } = useToast();
  const [guardando, setGuardando] = useState(false);
  const guardar = async (cambios: Record<string, unknown>, mensaje = "Guardado.") => {
    setGuardando(true);
    try {
      await adminApi.guardarConfig(cambios);
      avisar(mensaje);
      onGuardado();
      return true;
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude guardar.", "error");
      return false;
    } finally {
      setGuardando(false);
    }
  };
  return { guardar, guardando };
}

type FilaPrecio = { modelo: string; entrada: string; salida: string; cache: string; fuente: string; fecha: string };

function Precios({ cfg, onGuardado }: { cfg: Config; onGuardado: () => void }) {
  const { guardar, guardando } = useGuardar(onGuardado);
  const guardados = (cfg.valores.openai_precios?.valor as Record<string, Precio> | undefined) ?? {};
  const modelos = Array.from(new Set([...Object.keys(guardados), ...cfg.modelos_vistos])).sort();
  const [filas, setFilas] = useState<FilaPrecio[]>(() =>
    modelos.map((m) => ({ modelo: m, entrada: guardados[m]?.entrada?.toString() ?? "", salida: guardados[m]?.salida?.toString() ?? "", cache: guardados[m]?.cache?.toString() ?? "", fuente: guardados[m]?.fuente ?? "", fecha: guardados[m]?.fecha ?? "" })),
  );
  const set = (i: number, k: keyof FilaPrecio, v: string) => setFilas((fs) => fs.map((f, j) => (j === i ? { ...f, [k]: v } : f)));
  const num = (s: string) => (s.trim() === "" ? undefined : Number(s.replace(",", ".")));

  async function enviar() {
    const out: Record<string, Precio> = {};
    for (const f of filas) {
      if (!f.modelo.trim()) continue;
      if (f.entrada.trim() === "" && f.salida.trim() === "") continue; // sin precio: no se guarda (se muestran solo tokens)
      out[f.modelo.trim()] = { entrada: num(f.entrada) ?? 0, salida: num(f.salida) ?? 0, ...(f.cache.trim() !== "" ? { cache: num(f.cache) } : {}), fuente: f.fuente.trim(), ...(f.fecha.trim() ? { fecha: f.fecha.trim() } : {}) };
    }
    await guardar({ openai_precios: out }, "Precios guardados.");
  }

  return (
    <Bloque
      titulo="Precios de OpenAI"
      icono="moneda"
      explicacion={
        <>
          {cfg.explicaciones.openai_precios} Sacarlos de <code>developers.openai.com/api/docs/models</code>. Un modelo sin precio muestra solo tokens (nunca un costo inventado). La fuente es obligatoria.
        </>
      }
      meta={cfg.valores.openai_precios}
      acciones={
        <>
          <button className="boton chico" type="button" onClick={() => setFilas((fs) => [...fs, { modelo: "", entrada: "", salida: "", cache: "", fuente: "", fecha: "" }])}>
            <IconoAdmin nombre="mas" tam={14} /> Otro modelo
          </button>
          <button className="boton primario" type="button" onClick={enviar} disabled={guardando}>
            {guardando ? "Guardando…" : "Guardar precios"}
          </button>
        </>
      }
    >
      {Object.entries(cfg.avisos_precios).map(([m, t]) => (
        <div key={m} className="aviso" role="status">
          <IconoAdmin nombre="alerta" tam={18} />
          <span>
            <strong>{m}</strong>: {t}
          </span>
        </div>
      ))}
      <div className="tabla-caja">
        <table className="tabla chica precios">
          <thead>
            <tr>
              <th>Modelo</th>
              <th className="num">Entrada</th>
              <th className="num">Salida</th>
              <th className="num">Caché</th>
              <th>Fuente</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f, i) => (
              <tr key={i}>
                <td data-col="Modelo">
                  {modelos.includes(f.modelo) && f.modelo ? <code>{f.modelo}</code> : <input value={f.modelo} onChange={(e) => set(i, "modelo", e.target.value)} placeholder="nombre del modelo" aria-label="Modelo" />}
                  {!guardados[f.modelo] && f.modelo && <span className="chip chico amarillo">sin precio</span>}
                </td>
                <td data-col="Entrada" className="num">
                  <input inputMode="decimal" value={f.entrada} onChange={(e) => set(i, "entrada", e.target.value)} aria-label={`Entrada de ${f.modelo}`} />
                </td>
                <td data-col="Salida" className="num">
                  <input inputMode="decimal" value={f.salida} onChange={(e) => set(i, "salida", e.target.value)} aria-label={`Salida de ${f.modelo}`} />
                </td>
                <td data-col="Caché" className="num">
                  <input inputMode="decimal" value={f.cache} onChange={(e) => set(i, "cache", e.target.value)} placeholder="= entrada" aria-label={`Caché de ${f.modelo}`} />
                </td>
                <td data-col="Fuente">
                  <input value={f.fuente} onChange={(e) => set(i, "fuente", e.target.value)} placeholder="página y fecha de donde salió" aria-label={`Fuente de ${f.modelo}`} />
                </td>
                <td data-col="Fecha">
                  <input value={f.fecha} onChange={(e) => set(i, "fecha", e.target.value)} placeholder="AAAA-MM-DD" aria-label={`Fecha de ${f.modelo}`} style={{ width: 110 }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="suave chico">US$ por millón de tokens. «Caché» es el precio de los tokens de entrada que OpenAI ya tenía; vacío = igual que entrada.</p>
    </Bloque>
  );
}

function Presupuesto({ cfg, onGuardado }: { cfg: Config; onGuardado: () => void }) {
  const { guardar, guardando } = useGuardar(onGuardado);
  const actual = cfg.valores.presupuesto_openai_usd?.valor;
  const [v, setV] = useState(actual ? String(actual) : "");
  return (
    <Bloque
      titulo="Presupuesto mensual de OpenAI"
      icono="escudo"
      explicacion={cfg.explicaciones.presupuesto_openai_usd}
      meta={cfg.valores.presupuesto_openai_usd}
      acciones={
        <button className="boton primario" type="button" onClick={() => guardar({ presupuesto_openai_usd: Number(v.replace(",", ".") || 0) }, "Presupuesto guardado.")} disabled={guardando}>
          Guardar
        </button>
      }
    >
      <label className="campo-inline">
        US$ por mes
        <input inputMode="decimal" value={v} onChange={(e) => setV(e.target.value)} placeholder="0 = sin presupuesto" style={{ width: 160 }} />
      </label>
      {!actual && <p className="suave chico">Hoy no hay presupuesto cargado: el Dashboard muestra el gasto sin compararlo con nada.</p>}
    </Bloque>
  );
}

function Umbrales({ cfg, onGuardado }: { cfg: Config; onGuardado: () => void }) {
  const { guardar, guardando } = useGuardar(onGuardado);
  const actual = (cfg.valores.umbrales_planes?.valor as Record<string, number> | number | undefined) ?? {};
  const base = typeof actual === "number" ? { default: actual } : actual;
  const [u, setU] = useState<Record<string, string>>(() => Object.fromEntries(cfg.proveedores_umbral.map((p) => [p, base[p] !== undefined ? String(base[p]) : ""])));
  async function enviar() {
    const out: Record<string, number> = {};
    for (const [k, v] of Object.entries(u)) if (v.trim() !== "") out[k] = Number(v);
    if (out.default === undefined) out.default = cfg.defaults.umbral;
    await guardar({ umbrales_planes: out }, "Umbrales guardados.");
  }
  return (
    <Bloque
      titulo="Umbrales de capacidad"
      icono="pulso"
      explicacion={`${cfg.explicaciones.umbrales_planes} Vacío = el default (${cfg.defaults.umbral} %).`}
      meta={cfg.valores.umbrales_planes}
      acciones={
        <button className="boton primario" type="button" onClick={enviar} disabled={guardando}>
          Guardar umbrales
        </button>
      }
    >
      <div className="umbrales-grilla">
        {cfg.proveedores_umbral.map((p) => (
          <label key={p}>
            {p === "default" ? "Todos (default)" : p}
            <span className="campo-pct">
              <input inputMode="numeric" value={u[p] ?? ""} onChange={(e) => setU((x) => ({ ...x, [p]: e.target.value }))} placeholder={String(cfg.defaults.umbral)} aria-label={`Umbral de ${p}`} />
              <span>%</span>
            </span>
          </label>
        ))}
      </div>
    </Bloque>
  );
}

function EstiloDefecto({ cfg, onGuardado }: { cfg: Config; onGuardado: () => void }) {
  const { avisar } = useToast();
  const [op, setOp] = useState<Opciones | null>(null);
  const [estilo, setEstilo] = useState<Estilo | null>(null);
  const [guardando, setGuardando] = useState(false);
  useEffect(() => {
    api
      .opciones()
      .then((o) => {
        setOp(o);
        setEstilo(o.estilo_equipo ?? o.estilo_defecto);
      })
      .catch(() => setOp(null));
  }, []);
  async function enviar() {
    if (!estilo) return;
    setGuardando(true);
    try {
      await api.guardarEstiloDefecto(estilo);
      avisar("Estilo por defecto guardado: vale para los recortes verticales nuevos.");
      onGuardado();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude guardar.", "error");
    } finally {
      setGuardando(false);
    }
  }
  return (
    <Bloque
      titulo="Estilo por defecto de los subtítulos"
      icono="subtitulos"
      explicacion={`${cfg.explicaciones.clips_estilo} Los recortes ya hechos no cambian; cada uno se ajusta desde su editor.`}
      meta={cfg.valores.clips_estilo}
      acciones={
        <button className="boton primario" type="button" onClick={enviar} disabled={guardando || !estilo}>
          {guardando ? "Guardando…" : "Guardar como estilo por defecto"}
        </button>
      }
    >
      {!op || !estilo ? (
        <p className="suave chico">Cargando las opciones del editor…</p>
      ) : (
        <div className="estilo-config">
          <ControlesEstilo estilo={estilo} opciones={op} onCambio={setEstilo} />
          <div className="muestra-subtitulo" aria-label="Vista previa">
            <span style={cssSubtitulo(estilo, op, "vertical", 240).texto}>la gratitud es la respuesta</span>
          </div>
        </div>
      )}
    </Bloque>
  );
}

function FraseDelDia({ cfg, onGuardado }: { cfg: Config; onGuardado: () => void }) {
  const { guardar, guardando } = useGuardar(onGuardado);
  const v = (k: string) => cfg.valores[k]?.valor;
  const [activa, setActiva] = useState(Boolean(v("frase_activa")));
  const [hora, setHora] = useState(String(v("frase_hora") || cfg.defaults.frase_hora));
  const [canales, setCanales] = useState<string[]>((v("frase_canales") as string[] | undefined) ?? cfg.defaults.frase_canales);
  const [foto, setFoto] = useState(String(v("frase_imagen") || ""));
  const [pie, setPie] = useState(v("frase_pie") === undefined || v("frase_pie") === null ? cfg.defaults.frase_pie : String(v("frase_pie")));
  const meta = ["frase_activa", "frase_hora", "frase_canales", "frase_imagen", "frase_pie"].map((k) => cfg.valores[k]).filter(Boolean).sort((a, b) => (b.actualizado || "").localeCompare(a.actualizado || ""))[0];
  return (
    <Bloque
      titulo="Frase del día"
      icono="megafono"
      explicacion="Cada día la cola encola la frase asignada en el calendario como posteo (una pieza por canal) a la hora elegida, con la foto de fondo de ese día o la foto por defecto. Las frases y el calendario siguen en el Panel admin de Streamlit."
      meta={meta}
      acciones={
        <button className="boton primario" type="button" onClick={() => guardar({ frase_activa: activa, frase_hora: hora, frase_canales: canales, frase_imagen: foto, frase_pie: pie }, "Frase del día guardada.")} disabled={guardando}>
          Guardar
        </button>
      }
    >
      <div className="frase-grilla">
        <label className="interruptor grande">
          <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} />
          <span>
            <strong>{activa ? "Prendida" : "Apagada"}</strong>
            <span className="suave chico"> · {cfg.explicaciones.frase_activa}</span>
          </span>
        </label>
        <label>
          Hora de salida (Argentina) <span className="suave chico">{cfg.explicaciones.frase_hora}</span>
          <input type="time" value={hora} onChange={(e) => setHora(e.target.value)} step={900} style={{ width: 140 }} />
        </label>
        <fieldset className="opciones">
          <legend>Canales</legend>
          {Object.entries(cfg.frase_canales_posibles).map(([k, t]) => (
            <label key={k} className="casilla">
              <input type="checkbox" checked={canales.includes(k)} onChange={(e) => setCanales((cs) => (e.target.checked ? [...cs, k] : cs.filter((c) => c !== k)))} /> {t}
            </label>
          ))}
          <span className="suave chico">{cfg.explicaciones.frase_canales} El mail se suma cuando haya herramienta de envío.</span>
        </fieldset>
        <label>
          Foto de fondo por defecto (URL) <span className="suave chico">{cfg.explicaciones.frase_imagen}</span>
          <input type="url" value={foto} onChange={(e) => setFoto(e.target.value)} placeholder="https://…" />
        </label>
        {foto && <img src={foto} alt="Foto por defecto" className="foto-defecto" />}
        {activa && !foto && <AvisoError texto="Prendida sin foto por defecto: los días sin foto elegida no se encolan." />}
        <label>
          Pie del posteo <span className="suave chico">{cfg.explicaciones.frase_pie}</span>
          <input value={pie} onChange={(e) => setPie(e.target.value)} />
        </label>
      </div>
    </Bloque>
  );
}
