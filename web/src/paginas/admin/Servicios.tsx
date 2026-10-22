import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi } from "../../api";
import Modal from "../../componentes/Modal";
import { useToast } from "../../componentes/Toasts";
import { adminApi, type Capacidad, type Servicio, type Servicios as Datos } from "./adminApi";
import { AvisoError, Cargando, EstadoChip, IconoAdmin, Metrica, fecha, hace, usd } from "./comun";
import { Medidor } from "./Graficos";

// Administración → Servicios y costos (22/10): el inventario de todo lo que usa la app (tabla servicios: nombre, proveedor,
// para qué, plan, costo mensual, confirmado o referencia, desde, link) con alta / edición / baja en un modal; el total fijo
// mensual y el total con la estimación de OpenAI del mes. Debajo, la CAPACIDAD (GET /salud/capacidad): por proveedor una barra
// de uso contra el límite del plan con el umbral marcado, el estado, la justificación y la fuente del límite; los umbrales se
// editan acá mismo y, para lo que la API no puede medir (Vercel), se carga el uso a mano.

const VACIO: Servicio = { nombre: "", proveedor: "", para_que: "", plan: "", costo_mensual_usd: null, confirmado: false, desde: "", url: "", notas: "", activo: true };

export default function Servicios() {
  const { avisar } = useToast();
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editando, setEditando] = useState<Servicio | null>(null);
  const [aBorrar, setABorrar] = useState<Servicio | null>(null);
  const [soloActivos, setSoloActivos] = useState(true);

  const cargar = useCallback(async () => {
    try {
      setDatos(await adminApi.servicios());
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer los servicios.");
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const lista = (datos?.servicios ?? []).filter((s) => !soloActivos || s.activo);
  const inactivos = (datos?.servicios ?? []).filter((s) => !s.activo).length;

  return (
    <>
      <div className="seccion-cabecera">
        <h2>
          <IconoAdmin nombre="moneda" /> Servicios y costos {datos && <span className="suave chico">({datos.servicios_activos} activos)</span>}
        </h2>
        <div className="acciones">
          <button className="boton primario" onClick={() => setEditando({ ...VACIO })}>
            <IconoAdmin nombre="mas" tam={16} /> Nuevo servicio
          </button>
        </div>
      </div>
      {error && <AvisoError texto={error} />}
      {!datos ? (
        <Cargando filas={4} />
      ) : (
        <>
          <div className="metricas tres">
            <Metrica etiqueta="Costo fijo por mes" valor={usd(datos.fijo_usd)} detalle={datos.sin_confirmar.length ? `Confirmado por factura: ${usd(datos.fijo_confirmado_usd)}. Referencia: ${datos.sin_confirmar.join(", ")}` : "Todos los montos confirmados"} />
            <Metrica etiqueta={`OpenAI estimado · ${datos.mes_texto}`} valor={usd(datos.openai_mes_usd)} detalle="Con los precios de Configuración sobre lo registrado este mes" />
            <Metrica etiqueta="Fijo + OpenAI del mes" valor={usd(datos.total_mes_usd)} detalle={datos.sin_monto.length ? `Sin monto cargado: ${datos.sin_monto.join(", ")}` : undefined} />
          </div>
          <div className="tarjeta tabla-caja">
            <table className="tabla servicios">
              <thead>
                <tr>
                  <th>Servicio</th>
                  <th>Para qué</th>
                  <th>Plan</th>
                  <th className="num">US$/mes</th>
                  <th>Monto</th>
                  <th>Desde</th>
                  <th>
                    <span className="visualmente-oculto">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {lista.map((s) => (
                  <tr key={s.id} className={s.activo ? "" : "inactivo"}>
                    <td data-col="Servicio">
                      <strong>{s.nombre}</strong>
                      {s.proveedor && s.proveedor !== s.nombre && <span className="suave chico"> · {s.proveedor}</span>}
                      {!s.activo && <span className="chip chico suave">inactivo</span>}
                      {s.url && (
                        <a href={s.url} target="_blank" rel="noreferrer" className="link-externo" title={s.url} aria-label={`Abrir el panel de ${s.nombre}`}>
                          <IconoAdmin nombre="externo" tam={13} />
                        </a>
                      )}
                    </td>
                    <td data-col="Para qué" className="chico celda-larga" title={s.para_que ?? undefined}>
                      {s.para_que || <span className="suave">—</span>}
                      {s.notas && <div className="suave chico">{s.notas}</div>}
                    </td>
                    <td data-col="Plan" className="chico">
                      {s.plan || <span className="suave">—</span>}
                    </td>
                    <td data-col="US$/mes" className="num">
                      {s.costo_mensual_usd === null ? <span className="suave" title="No se sabe el monto">sin monto</span> : usd(s.costo_mensual_usd)}
                    </td>
                    <td data-col="Monto">{s.confirmado ? <span className="chip chico" style={{ marginLeft: 0 }}>confirmado</span> : <span className="chip chico amarillo" style={{ marginLeft: 0 }} title="Sin factura o plan verificado que lo confirme">referencia</span>}</td>
                    <td data-col="Desde" className="suave chico">
                      {s.desde ? fecha(s.desde + "T12:00:00Z", false) : "—"}
                    </td>
                    <td data-col="" className="celda-acciones">
                      <button className="boton sutil chico" onClick={() => setEditando(s)} aria-label={`Editar ${s.nombre}`} title="Editar">
                        <IconoAdmin nombre="lapiz" tam={15} /> <span className="etiqueta">Editar</span>
                      </button>
                      <button className="boton peligro sutil chico" onClick={() => setABorrar(s)} aria-label={`Borrar ${s.nombre}`} title="Borrar del inventario">
                        <IconoAdmin nombre="tacho" tam={15} /> <span className="etiqueta">Borrar</span>
                      </button>
                    </td>
                  </tr>
                ))}
                {lista.length === 0 && (
                  <tr>
                    <td colSpan={7} className="suave" style={{ textAlign: "center", padding: 24 }}>
                      Todavía no hay servicios cargados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {inactivos > 0 && (
            <label className="interruptor chico" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={!soloActivos} onChange={(e) => setSoloActivos(!e.target.checked)} /> Mostrar también los {inactivos} inactivos
            </label>
          )}
          <p className="suave chico">«Confirmado» = el monto sale de la factura o del plan verificado en el panel del proveedor; «referencia» = lo que dice la página de precios o un supuesto, sin factura. Los inactivos no suman.</p>
        </>
      )}

      <CapacidadSeccion servicios={datos?.servicios ?? []} />

      {editando && (
        <EditarServicio
          s={editando}
          onCerrar={() => setEditando(null)}
          onHecho={(nuevo, esNuevo) => {
            setEditando(null);
            avisar(esNuevo ? `${nuevo.nombre} agregado.` : `${nuevo.nombre} guardado.`);
            cargar();
          }}
        />
      )}
      {aBorrar && (
        <Modal titulo={`¿Borrar ${aBorrar.nombre} del inventario?`} onCerrar={() => setABorrar(null)} peligro>
          <p>Desaparece de la lista y deja de sumar al costo fijo. Si solo dejaron de usarlo, mejor marcalo como inactivo (queda el registro de qué era y cuánto costaba).</p>
          <div className="acciones derecha">
            <button className="boton" onClick={() => setABorrar(null)}>
              Cancelar
            </button>
            <button
              className="boton peligro"
              onClick={async () => {
                try {
                  await adminApi.borrarServicio(aBorrar.id!);
                  avisar(`${aBorrar.nombre} borrado.`);
                  setABorrar(null);
                  cargar();
                } catch (e) {
                  avisar(e instanceof ErrorApi ? e.message : "No pude borrar.", "error");
                }
              }}
            >
              <IconoAdmin nombre="tacho" tam={16} /> Borrar
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function EditarServicio({ s, onCerrar, onHecho }: { s: Servicio; onCerrar: () => void; onHecho: (s: Servicio, esNuevo: boolean) => void }) {
  const [f, setF] = useState<Servicio>({ ...s, costo_mensual_usd: s.costo_mensual_usd });
  const [costoTxt, setCostoTxt] = useState(s.costo_mensual_usd === null || s.costo_mensual_usd === undefined ? "" : String(s.costo_mensual_usd));
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const set = (k: keyof Servicio, v: unknown) => setF((x) => ({ ...x, [k]: v }));
  const esNuevo = !s.id;

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const costo = costoTxt.trim() === "" ? null : Number(costoTxt.replace(",", "."));
    if (costo !== null && Number.isNaN(costo)) {
      setError("El costo tiene que ser un número (o vacío si no se sabe).");
      return;
    }
    setEnviando(true);
    try {
      const r = await adminApi.guardarServicio({ ...f, costo_mensual_usd: costo });
      onHecho(r.servicio, esNuevo);
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal titulo={esNuevo ? "Nuevo servicio" : `Editar ${s.nombre}`} onCerrar={onCerrar} ancho={560}>
      <form className="formulario" onSubmit={guardar}>
        <div className="dos-columnas">
          <label>
            Nombre
            <input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} required autoFocus />
          </label>
          <label>
            Proveedor
            <input value={f.proveedor ?? ""} onChange={(e) => set("proveedor", e.target.value)} />
          </label>
        </div>
        <label>
          Para qué lo usamos
          <input value={f.para_que ?? ""} onChange={(e) => set("para_que", e.target.value)} placeholder="qué función cumple en la app" />
        </label>
        <div className="dos-columnas">
          <label>
            Plan
            <input value={f.plan ?? ""} onChange={(e) => set("plan", e.target.value)} placeholder="Free, Hobby, Starter…" />
          </label>
          <label>
            Costo mensual (US$) <span className="suave chico">vacío = no se sabe</span>
            <input inputMode="decimal" value={costoTxt} onChange={(e) => setCostoTxt(e.target.value)} placeholder="0" />
          </label>
        </div>
        <div className="dos-columnas">
          <label>
            Desde (AAAA-MM-DD)
            <input value={f.desde ?? ""} onChange={(e) => set("desde", e.target.value)} placeholder="2026-10-21" pattern="\d{4}-\d{2}-\d{2}" />
          </label>
          <label>
            Link al panel del proveedor
            <input type="url" value={f.url ?? ""} onChange={(e) => set("url", e.target.value)} placeholder="https://…" />
          </label>
        </div>
        <label>
          Notas
          <input value={f.notas ?? ""} onChange={(e) => set("notas", e.target.value)} />
        </label>
        <div className="dos-columnas">
          <label className="casilla">
            <input type="checkbox" checked={f.confirmado} onChange={(e) => set("confirmado", e.target.checked)} /> Monto confirmado (factura o plan verificado)
          </label>
          <label className="casilla">
            <input type="checkbox" checked={f.activo} onChange={(e) => set("activo", e.target.checked)} /> Activo (suma al costo fijo)
          </label>
        </div>
        {error && <AvisoError texto={error} />}
        <div className="acciones derecha">
          <button type="button" className="boton" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton primario" disabled={enviando || !f.nombre.trim()}>
            {enviando ? "Guardando…" : esNuevo ? "Agregar" : "Guardar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function CapacidadSeccion({ servicios }: { servicios: Servicio[] }) {
  const { avisar } = useToast();
  const [items, setItems] = useState<Capacidad[] | null>(null);
  const [creado, setCreado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [umbrales, setUmbrales] = useState<Record<string, string>>({});
  const [gb, setGb] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const r = await adminApi.capacidad();
      setItems(r.capacidad);
      setCreado(r.creado);
      setError(null);
      const u: Record<string, string> = {};
      r.capacidad.forEach((c) => (u[c.proveedor] = String(c.umbral)));
      setUmbrales(u);
      const v = r.capacidad.find((c) => c.proveedor === "vercel");
      setGb(v?.uso_manual?.gb !== undefined && v?.uso_manual?.gb !== null ? String(v.uso_manual.gb) : "");
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer la capacidad.");
      setItems([]);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function guardarUmbrales() {
    setGuardando(true);
    try {
      const u: Record<string, number> = {};
      for (const [k, v] of Object.entries(umbrales)) {
        const n = Number(v);
        if (!Number.isFinite(n) || n < 1 || n > 100) throw new Error(`El umbral de ${k} tiene que ser un porcentaje de 1 a 100.`);
        u[k] = n;
      }
      await adminApi.guardarConfig({ umbrales_planes: u });
      avisar("Umbrales guardados.");
      cargar();
    } catch (e) {
      avisar(e instanceof Error ? e.message : "No pude guardar.", "error");
    } finally {
      setGuardando(false);
    }
  }

  async function guardarGb() {
    setGuardando(true);
    try {
      const n = Number(gb.replace(",", "."));
      if (!Number.isFinite(n) || n < 0) throw new Error("Los GB tienen que ser un número.");
      await adminApi.guardarConfig({ vercel_uso_manual: { gb: n } });
      avisar("Uso de Vercel cargado.");
      cargar();
    } catch (e) {
      avisar(e instanceof Error ? e.message : "No pude guardar.", "error");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section className="capacidad" aria-label="Capacidad de los planes">
      <div className="seccion-cabecera" style={{ marginTop: 26 }}>
        <h2>
          <IconoAdmin nombre="escudo" /> ¿Cuándo hay que pasar a plan pago?
        </h2>
        <div className="acciones">
          {creado && <span className="suave chico">medido {hace(creado)}</span>}
          <button className="boton chico" onClick={() => {
              setItems(null);
              cargar();
            }}>
            <IconoAdmin nombre="regenerar" tam={14} /> Medir de nuevo
          </button>
        </div>
      </div>
      <p className="suave chico">Por proveedor: el uso actual contra el límite del plan vigente. Pasado el umbral (la línea), el estado dice «conviene pasar a plan pago» y por qué. Los límites llevan su fuente; lo que no se puede medir se dice.</p>
      {error && <AvisoError texto={error} />}
      {items === null ? (
        <Cargando filas={4} />
      ) : (
        <div className="capacidad-lista">
          {items.map((c) => {
            const srv = servicios.find((s) => s.activo && ((s.proveedor || "") + " " + s.nombre).toLowerCase().includes(c.proveedor));
            return (
              <article key={c.proveedor} className={"tarjeta capacidad-item " + c.estado}>
                <header>
                  <div>
                    <strong>{c.nombre}</strong>
                    <span className="suave chico">
                      {" "}
                      · plan {c.plan ?? "?"}
                      {c.costo_mensual_usd !== null && c.costo_mensual_usd !== undefined ? ` · ${usd(c.costo_mensual_usd)}/mes${c.costo_confirmado ? "" : " (referencia)"}` : srv ? "" : " · sin costo cargado"}
                    </span>
                  </div>
                  <EstadoChip estado={c.estado} texto={c.estado === "aviso" ? "conviene plan pago" : c.estado === "error" ? "al límite" : c.estado === "sin_dato" ? "sin dato" : "ok"} />
                </header>
                <div className="capacidad-cifra">
                  {c.uso !== null && c.uso !== undefined ? (
                    <>
                      <strong>{c.unidad === "USD" ? usd(c.uso) : `${c.uso.toLocaleString("es-AR")} ${c.unidad}`}</strong>
                      {c.limite ? (
                        <span className="suave">
                          {" "}
                          de {c.unidad === "USD" ? usd(c.limite) : `${c.limite.toLocaleString("es-AR")} ${c.unidad}`} ({c.porcentaje} %)
                        </span>
                      ) : (
                        <span className="suave"> · sin límite para comparar</span>
                      )}
                    </>
                  ) : (
                    <span className="suave">sin medición</span>
                  )}
                  <span className="suave chico"> · {c.metrica}</span>
                </div>
                <Medidor porcentaje={c.porcentaje} umbral={c.umbral} estado={c.estado} etiqueta={`${c.nombre}: ${c.metrica}`} />
                <p className="capacidad-just">{c.justificacion}</p>
                {c.estado !== "ok" && c.desde && <p className="suave chico">Así desde {hace(c.desde)}.</p>}
                <details className="chico">
                  <summary className="suave">Fuente del límite y detalles</summary>
                  <ul className="suave chico">
                    {c.fuente_limite && (
                      <li>
                        Límite: {c.fuente_limite}
                        {c.referencia ? " (referencia, no un derecho del plan)" : ""}
                      </li>
                    )}
                    {c.nota && <li>{c.nota}</li>}
                    {c.tablas && <li>Tablas más grandes: {Object.entries(c.tablas).map(([t, v]) => `${t} ${v.mb} MB${v.filas ? ` (${v.filas.toLocaleString("es-AR")} filas)` : ""}`).join(", ")}.</li>}
                    {typeof c.arranques_24h === "number" && <li>Arranques de la API: {c.arranques_24h} en 24 h, {c.arranques_7d ?? "?"} en 7 días.</li>}
                    {c.tokens && <li>Este mes: {c.tokens.llamadas} llamadas; a este ritmo, {usd(c.proyeccion_30_dias_usd ?? null)} en 30 días.</li>}
                    {c.modelos_sin_precio && c.modelos_sin_precio.length > 0 && <li>Modelos sin precio cargado: {c.modelos_sin_precio.join(", ")}.</li>}
                    {!c.medido && c.uso_manual && (
                      <li>
                        Dato cargado a mano el {fecha(c.uso_manual.fecha, false)} por {c.uso_manual.por ?? "?"}.
                      </li>
                    )}
                  </ul>
                </details>
                {c.proveedor === "vercel" && (
                  <div className="capacidad-manual">
                    <label>
                      GB transferidos este mes (vercel.com → Usage)
                      <input inputMode="decimal" value={gb} onChange={(e) => setGb(e.target.value)} placeholder="por ejemplo 12.5" />
                    </label>
                    <button className="boton chico" onClick={guardarGb} disabled={guardando || !gb.trim()}>
                      Cargar
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
      {items && items.length > 0 && (
        <div className="tarjeta umbrales">
          <h3>Umbrales de aviso</h3>
          <p className="suave chico">Porcentaje del límite a partir del cual la fila pasa a «conviene plan pago». Se puede afinar por proveedor. Default: 70 %.</p>
          <div className="umbrales-grilla">
            {items.map((c) => (
              <label key={c.proveedor}>
                {c.nombre}
                <span className="campo-pct">
                  <input inputMode="numeric" value={umbrales[c.proveedor] ?? ""} onChange={(e) => setUmbrales((u) => ({ ...u, [c.proveedor]: e.target.value }))} aria-label={`Umbral de ${c.nombre}`} />
                  <span>%</span>
                </span>
              </label>
            ))}
          </div>
          <div className="acciones derecha">
            <Link to="/administracion/configuracion" className="suave chico">
              Presupuesto de OpenAI y más, en Configuración
            </Link>
            <button className="boton primario chico" onClick={guardarUmbrales} disabled={guardando}>
              Guardar umbrales
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
