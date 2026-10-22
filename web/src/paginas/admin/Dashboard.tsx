import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi } from "../../api";
import { useAdmin } from "./Administracion";
import { adminApi, type Costos, type Uso } from "./adminApi";
import { AvisoError, Cargando, EstadoChip, IconoAdmin, Metrica, Plegable, diaCorto, fecha, hace, miles, nombreChequeo, pct, usd } from "./comun";
import { BarrasApiladas } from "./Graficos";

// Administración → Dashboard (22/10, portada). Responde en orden: ¿funciona la app? (última corrida de Salud), ¿cuánto cuesta?
// (OpenAI estimado del mes + costos fijos de Servicios, con el mes anterior al lado) y ¿quién la usa? (período 7/28/90 días o
// un mes: personas activas, tabla por persona con su costo, gráficos por semana / por día / por mes, consumo por modelo).
// Misma lógica que el Dashboard de Streamlit (publicar_ui.uso_admin + costo_openai_admin), con los datos de api/admin_rutas.py.

type Periodo = { dias?: number; mes?: string };

const MESES_TXT = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

function mesesRecientes(n = 6) {
  const out: { mes: string; texto: string }[] = [];
  const d = new Date();
  for (let i = 0; i < n; i++) {
    const a = d.getFullYear();
    const m = d.getMonth();
    out.push({ mes: `${a}-${String(m + 1).padStart(2, "0")}`, texto: `${MESES_TXT[m]} ${a}` });
    d.setMonth(m - 1, 1);
  }
  return out;
}

export default function Dashboard() {
  const { errorResumen } = useAdmin();
  const [periodo, setPeriodo] = useState<Periodo>({ dias: 28 });
  const [uso, setUso] = useState<Uso | null>(null);
  const [costos, setCostos] = useState<Costos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const meses = useMemo(() => mesesRecientes(6), []);

  useEffect(() => {
    let vivo = true;
    setUso(null);
    setCostos(null);
    Promise.all([adminApi.uso(periodo.dias, periodo.mes), adminApi.costos(periodo.dias, periodo.mes)])
      .then(([u, c]) => {
        if (!vivo) return;
        setUso(u);
        setCostos(c);
        setError(null);
      })
      .catch((e) => vivo && setError(e instanceof ErrorApi ? e.message : "No pude leer el uso."));
    return () => {
      vivo = false;
    };
  }, [periodo]);

  return (
    <>
      <Funciona />
      {errorResumen && <AvisoError texto={errorResumen} />}
      <CostoDelMes />

      <div className="seccion-cabecera" style={{ marginTop: 22 }}>
        <h2>
          <IconoAdmin nombre="usuarios" /> ¿Quién usa la app?
        </h2>
        <div className="acciones periodo" role="group" aria-label="Período">
          {[7, 28, 90].map((d) => (
            <button key={d} className={"boton chico" + (periodo.dias === d ? " primario" : "")} onClick={() => setPeriodo({ dias: d })} aria-pressed={periodo.dias === d}>
              {d} días
            </button>
          ))}
          <select value={periodo.mes ?? ""} onChange={(e) => setPeriodo(e.target.value ? { mes: e.target.value } : { dias: 28 })} aria-label="Un mes">
            <option value="">un mes…</option>
            {meses.map((m) => (
              <option key={m.mes} value={m.mes}>
                {m.texto}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error && <AvisoError texto={error} />}
      {!uso || !costos ? <Cargando filas={5} /> : <UsoDetalle uso={uso} costos={costos} />}
    </>
  );
}

function Funciona() {
  const { resumen } = useAdmin();
  const s = resumen?.salud;
  if (!resumen) return <div className="hueso" style={{ height: 64, borderRadius: 12, marginBottom: 14 }} aria-busy="true" />;
  const estado = s?.estado ?? "sin_dato";
  const errores = s?.errores ?? 0;
  const avisos = s?.avisos ?? 0;
  const capMal = s?.capacidad_mal ?? [];
  const titulo =
    estado === "ok" ? "Sí, la app funciona: todo en orden." : estado === "aviso" ? `La app funciona, con ${avisos} aviso${avisos === 1 ? "" : "s"} para mirar.` : estado === "error" ? `Hay ${errores} problema${errores === 1 ? "" : "s"}${avisos ? ` y ${avisos} aviso${avisos === 1 ? "" : "s"}` : ""}.` : "Todavía no sé si funciona.";
  return (
    <div className={"funciona tarjeta " + estado} role="status">
      <div className="funciona-luz" aria-hidden="true" />
      <div className="funciona-texto">
        <strong>¿Funciona la app?</strong> {titulo}
        <div className="suave chico">
          {s?.creado ? (
            <>
              Último chequeo {hace(s.creado)} ({s.chequeos} servicios revisados)
              {(s?.mal ?? []).length > 0 && <>: {s!.mal!.map((m) => nombreChequeo(m.nombre)).join(", ")}</>}
              {capMal.length > 0 && <>. Capacidad: {capMal.map((c) => `${c.nombre} ${c.porcentaje ?? "?"} %`).join(", ")}</>}
              {s?.arranques_24h ? `. La API arrancó ${s.arranques_24h} ${s.arranques_24h === 1 ? "vez" : "veces"} en 24 h (plan free: se duerme).` : "."}
            </>
          ) : (
            s?.detalle
          )}
        </div>
      </div>
      <Link to="/administracion/salud" className="boton chico">
        Ver Salud <IconoAdmin nombre="chevron" tam={14} />
      </Link>
    </div>
  );
}

function CostoDelMes() {
  const { resumen } = useAdmin();
  const c = resumen?.costo;
  if (!resumen) return null;
  if (!c)
    return (
      <div className="aviso" role="status">
        <IconoAdmin nombre="info" tam={18} /> Sin Supabase no hay registro de costos.
      </div>
    );
  const fijosTxt = c.con_costo.length ? c.con_costo.map((s) => `${s.nombre} ${usd(s.usd)}${s.confirmado ? "" : " (referencia)"}`).join(" · ") : "ningún servicio con costo cargado";
  const sobre = c.presupuesto_usd ? Math.min(c.openai_usd / c.presupuesto_usd, 1) : null;
  return (
    <section className="costo-mes" aria-label="Costo del mes">
      <div className="tarjeta costo-principal">
        <div className="metrica-etiqueta">Costo de {c.mes_texto} (hasta hoy, día {c.dia_del_mes})</div>
        <div className="costo-total">{usd(c.total_usd)}</div>
        <ul className="costo-desglose">
          <li>
            <span>OpenAI (estimado)</span>
            <strong>{usd(c.openai_usd)}</strong>
            <span className="suave chico">
              {miles(c.openai_llamadas)} llamadas · a este ritmo, {usd(c.proyeccion_30_dias_usd)} en 30 días
              {c.presupuesto_usd ? ` · presupuesto ${usd(c.presupuesto_usd)}` : ""}
            </span>
            {sobre !== null && (
              <div className="barra-presupuesto" aria-hidden="true">
                <div style={{ width: `${sobre * 100}%` }} className={sobre >= 1 ? "error" : sobre >= 0.7 ? "aviso" : "ok"} />
              </div>
            )}
            {c.modelos_sin_precio.length > 0 && (
              <span className="chico rojo">
                Sin precio cargado (sus tokens no suman plata): {c.modelos_sin_precio.join(", ")}. <Link to="/administracion/configuracion">Cargarlo</Link>.
              </span>
            )}
          </li>
          <li>
            <span>Servicios fijos ({c.servicios_activos} activos)</span>
            <strong>{usd(c.fijo_usd)}</strong>
            <span className="suave chico">{fijosTxt}</span>
            {c.sin_confirmar.length > 0 && <span className="chico suave">Montos de referencia, sin factura: {c.sin_confirmar.join(", ")}.</span>}
            {c.sin_monto.length > 0 && <span className="chico suave">Sin monto cargado: {c.sin_monto.join(", ")}.</span>}
          </li>
        </ul>
        <p className="suave chico costo-nota">{c.nota}</p>
      </div>
      <div className="tarjeta costo-anterior">
        <div className="metrica-etiqueta">Mes anterior · {c.anterior.mes_texto}</div>
        <div className="costo-total chico">{usd(c.anterior.total_usd)}</div>
        <div className="suave chico">
          OpenAI {usd(c.anterior.openai_usd)} ({miles(c.anterior.openai_llamadas)} llamadas) + fijos {usd(c.fijo_usd)}
        </div>
        {c.anterior.openai_llamadas === 0 && <div className="suave chico">Sin llamadas registradas: el registro empezó el {fecha(resumen.registro_desde + "T12:00:00Z", false)}.</div>}
        <Link to="/administracion/servicios" className="boton chico" style={{ marginTop: 10 }}>
          Servicios y costos <IconoAdmin nombre="chevron" tam={14} />
        </Link>
      </div>
    </section>
  );
}

function UsoDetalle({ uso, costos }: { uso: Uso; costos: Costos }) {
  const r = uso.resumen;
  const personasSerie = useMemo(() => {
    const vistas = new Set<string>();
    uso.por_semana.forEach((s) => Object.keys(s.por_persona).forEach((u) => vistas.add(u)));
    return Array.from(vistas).sort();
  }, [uso]);
  const personasCosto = useMemo(() => costos.por_persona.map((p) => p.usuario), [costos]);
  const personasMes = useMemo(() => {
    const vistas = new Set<string>();
    costos.meses.forEach((m) => Object.keys(m.por_persona).forEach((u) => vistas.add(u)));
    return Array.from(vistas).sort();
  }, [costos]);
  const totalCosto = costos.total_usd;

  return (
    <>
      <div className="metricas">
        <Metrica etiqueta="Personas activas" valor={`${r.personas_activas} de ${r.personas_total}`} detalle={uso.sin_actividad.length ? `Sin actividad: ${uso.sin_actividad.join(", ")}` : "Todas hicieron algo"} />
        <Metrica etiqueta="Conversaciones" valor={miles(r.conversaciones)} detalle={`${miles(r.mensajes ?? 0)} mensajes`} />
        <Metrica etiqueta="Piezas creadas" valor={miles(r.piezas)} />
        <Metrica etiqueta="Recortes pedidos" valor={miles(r.recortes)} />
        <Metrica etiqueta={`OpenAI · ${uso.periodo.texto}`} valor={usd(totalCosto)} detalle={costos.llamadas ? `${miles(costos.llamadas)} llamadas · ${miles(costos.tokens.entrada + costos.tokens.salida)} tokens` : "sin llamadas registradas"} />
      </div>
      {costos.modelos_sin_precio.length > 0 && (
        <div className="aviso" role="status">
          <IconoAdmin nombre="alerta" tam={18} />
          <span>
            Modelos sin precio cargado (se cuentan sus tokens, no su costo): {costos.modelos_sin_precio.join(", ")}. <Link to="/administracion/configuracion">Cargar el precio</Link>.
          </span>
        </div>
      )}

      <div className="tarjeta tabla-caja" style={{ marginTop: 14 }}>
        <table className="tabla">
          <thead>
            <tr>
              <th>Persona</th>
              <th>Última vez</th>
              <th className="num">Conversaciones</th>
              <th className="num">Mensajes</th>
              <th className="num">Piezas</th>
              <th className="num">Recortes</th>
              <th className="num">OpenAI</th>
              <th>Lo último que hizo</th>
            </tr>
          </thead>
          <tbody>
            {uso.personas.map((p) => {
              const nada = !(p.conversaciones || p.piezas || p.recortes || p.llamadas);
              return (
                <tr key={p.usuario} className={nada ? "inactivo" : ""}>
                  <td data-col="Persona">
                    <strong>{p.usuario}</strong>
                    {p.nombre && <span className="suave chico"> {p.nombre}</span>}
                    {!p.activo && <span className="chip chico suave">desactivada</span>}
                    {!p.en_tabla && (
                      <span className="chip chico suave" title="Sigue en la lista vieja de secrets, sin importar a la tabla de usuarios">
                        secrets
                      </span>
                    )}
                  </td>
                  <td data-col="Última vez" title={p.ultima_vez ? fecha(p.ultima_vez) : undefined}>
                    {hace(p.ultima_vez)}
                  </td>
                  <td data-col="Conversaciones" className="num">
                    {p.conversaciones}
                  </td>
                  <td data-col="Mensajes" className="num">
                    {p.mensajes}
                  </td>
                  <td data-col="Piezas" className="num">
                    {p.piezas}
                  </td>
                  <td data-col="Recortes" className="num">
                    {p.recortes}
                  </td>
                  <td data-col="OpenAI" className="num" title={`${p.llamadas} llamadas`}>
                    {p.llamadas ? (
                      <>
                        {usd(p.costo_usd)} <span className="suave chico">({pct(p.parte_costo)})</span>
                      </>
                    ) : (
                      <span className="suave">—</span>
                    )}
                  </td>
                  <td data-col="Lo último" className="chico">
                    {p.lo_ultimo ? (
                      <>
                        <span className="chip chico suave" style={{ marginLeft: 0, marginRight: 6 }}>
                          {p.lo_ultimo.tipo}
                        </span>
                        {p.lo_ultimo.texto}
                      </>
                    ) : (
                      <span className="suave">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {costos.llamadas > 0 && (
            <tfoot>
              <tr>
                <td data-col="" colSpan={6}>
                  <strong>Total OpenAI del período</strong> <span className="suave chico">(incluye las llamadas del sistema: cola, Frase del día)</span>
                </td>
                <td data-col="Total" className="num">
                  <strong>{usd(totalCosto)}</strong>
                </td>
                <td data-col="" />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {uso.nota && <p className="suave chico">{uso.nota}</p>}

      <div className="graficos">
        <div className="tarjeta">
          <h3>Conversaciones nuevas por semana, por persona</h3>
          <BarrasApiladas titulo="Conversaciones por semana" columnas={uso.por_semana.map((s) => ({ etiqueta: diaCorto(s.semana), titulo: "semana del " + diaCorto(s.semana), valores: s.por_persona }))} series={personasSerie} />
        </div>
        <div className="tarjeta">
          <h3>Costo de OpenAI por día, por persona</h3>
          <BarrasApiladas titulo="Costo por día" columnas={costos.por_dia.map((d) => ({ etiqueta: diaCorto(d.dia), titulo: diaCorto(d.dia), valores: d.por_persona }))} series={personasCosto} formato={(n) => usd(n).replace("US$ ", "$")} />
        </div>
        <div className="tarjeta">
          <h3>Costo de OpenAI por mes (últimos 6)</h3>
          <BarrasApiladas titulo="Costo por mes" columnas={[...costos.meses].reverse().map((m) => ({ etiqueta: m.texto.split(" ")[0].slice(0, 3), titulo: m.texto + ` · ${miles(m.llamadas)} llamadas`, valores: m.por_persona }))} series={personasMes} formato={(n) => usd(n).replace("US$ ", "$")} />
          <table className="tabla chica">
            <thead>
              <tr>
                <th>Mes</th>
                <th className="num">Costo</th>
                <th className="num">Llamadas</th>
                <th className="num">Personas</th>
                <th>Quién más gastó</th>
              </tr>
            </thead>
            <tbody>
              {costos.meses
                .filter((m) => m.llamadas > 0)
                .map((m) => (
                  <tr key={m.mes}>
                    <td data-col="Mes">{m.texto}</td>
                    <td data-col="Costo" className="num">
                      {usd(m.usd)}
                    </td>
                    <td data-col="Llamadas" className="num">
                      {miles(m.llamadas)}
                    </td>
                    <td data-col="Personas" className="num">
                      {m.personas}
                    </td>
                    <td data-col="Quién más">{m.quien_mas ? `${m.quien_mas.usuario} (${usd(m.quien_mas.usd)})` : "—"}</td>
                  </tr>
                ))}
              {costos.meses.every((m) => !m.llamadas) && (
                <tr>
                  <td colSpan={5} className="suave">
                    Todavía no hay meses con registro (empezó el {fecha(costos.registro_desde + "T12:00:00Z", false)}).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <Plegable titulo="Consumo por modelo y para qué se usó" resumen={costos.por_modelo.length ? `${costos.por_modelo.length} combinaciones` : "sin llamadas"}>
        <table className="tabla chica">
          <thead>
            <tr>
              <th>Modelo</th>
              <th>Para qué</th>
              <th className="num">Llamadas</th>
              <th className="num">Tokens entrada</th>
              <th className="num">En caché</th>
              <th className="num">Tokens salida</th>
              <th className="num">Costo</th>
            </tr>
          </thead>
          <tbody>
            {costos.por_modelo.map((m) => (
              <tr key={m.modelo + m.que}>
                <td data-col="Modelo">
                  <code>{m.modelo}</code>
                  {!m.con_precio && <span className="chip chico amarillo">sin precio</span>}
                </td>
                <td data-col="Para qué">{m.que_texto}</td>
                <td data-col="Llamadas" className="num">
                  {miles(m.llamadas)}
                </td>
                <td data-col="Entrada" className="num">
                  {miles(m.tokens_entrada)}
                </td>
                <td data-col="En caché" className="num">
                  {miles(m.tokens_cache)}
                </td>
                <td data-col="Salida" className="num">
                  {miles(m.tokens_salida)}
                </td>
                <td data-col="Costo" className="num">
                  {m.con_precio ? usd(m.usd) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="suave chico">«En caché» son tokens de entrada que OpenAI ya tenía (el system message repetido): se cobran al precio de caché. {costos.nota}</p>
        {Object.keys(costos.precios).length > 0 && (
          <p className="suave chico">
            Precios usados (US$ por millón de tokens): {Object.entries(costos.precios).map(([m, p]) => `${m} entrada ${p.entrada} · salida ${p.salida}${p.cache !== undefined ? ` · caché ${p.cache}` : ""}`).join(" | ")}. <Link to="/administracion/configuracion">Ver fuentes y editar</Link>.
          </p>
        )}
      </Plegable>

      <Plegable titulo="Lo último que pasó" resumen={`${uso.ultimas.conversaciones.length} conversaciones · ${uso.ultimas.piezas.length} piezas · ${uso.ultimas.recortes.length} recortes`}>
        <div className="ultimas">
          <div>
            <h4>Conversaciones</h4>
            <ul>
              {uso.ultimas.conversaciones.map((c) => (
                <li key={c.id}>
                  <span className="suave chico">{hace(c.cuando)}</span> <strong>{c.usuario}</strong> · {c.titulo} <span className="suave chico">· {c.mensajes} mensajes</span>
                </li>
              ))}
              {!uso.ultimas.conversaciones.length && <li className="suave">Ninguna en el período.</li>}
            </ul>
          </div>
          <div>
            <h4>Piezas y recortes</h4>
            <ul>
              {uso.ultimas.piezas.map((p, i) => (
                <li key={"p" + i}>
                  <span className="suave chico">{hace(p.cuando)}</span> <strong>{p.usuario}</strong> · {p.canal} · {p.titulo} <EstadoChip estado="ok" texto={p.estado} />
                </li>
              ))}
              {uso.ultimas.recortes.map((k) => (
                <li key={k.id}>
                  <span className="suave chico">{hace(k.cuando)}</span> <strong>{k.usuario}</strong> · recorte {k.formato} · {k.titulo} <EstadoChip estado={k.estado === "error" ? "error" : k.estado === "listo" ? "ok" : "aviso"} texto={k.estado} />
                </li>
              ))}
              {!uso.ultimas.piezas.length && !uso.ultimas.recortes.length && <li className="suave">Nada en el período.</li>}
            </ul>
          </div>
        </div>
      </Plegable>
    </>
  );
}
