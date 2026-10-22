import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi } from "../../api";
import { useToast } from "../../componentes/Toasts";
import { useAdmin } from "./Administracion";
import { adminApi, type Chequeo, type FilaHistorial, type InformeSalud } from "./adminApi";
import { AvisoError, EstadoChip, IconoAdmin, Plegable, diasHasta, fecha, hace, nombreChequeo } from "./comun";

// Administración → Salud (22/10): los chequeos de GET /salud/servicios como tarjetas agrupadas por estado (errores, avisos, ok),
// cada una con el detalle, «qué hacer» y «desde cuándo»; arriba los vencimientos y avisos próximos (tokens que vencen en menos
// de 14 días en rojo, en menos de 30 en amarillo); «Volver a chequear» corre todo de nuevo (tarda unos segundos: los chequeos
// pegan a cada servicio); abajo el historial (GET /salud/historial) como línea de tiempo de los últimos días.

const AVISO_DIAS = 14;
const PRONTO_DIAS = 30;
const ORDEN = { error: 0, aviso: 1, ok: 2 } as Record<string, number>;

export default function Salud() {
  const { avisar } = useToast();
  const { recargarResumen } = useAdmin();
  const [informe, setInforme] = useState<InformeSalud | null>(null);
  const [historial, setHistorial] = useState<FilaHistorial[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [corriendo, setCorriendo] = useState(false);

  const chequear = useCallback(
    async (primera = false) => {
      setCorriendo(true);
      try {
        const i = await adminApi.salud();
        setInforme(i);
        setError(null);
        adminApi.historial(150).then(setHistorial).catch(() => setHistorial([]));
        recargarResumen();
        if (!primera) avisar(i.estado === "ok" ? "Chequeo hecho: todo en orden." : `Chequeo hecho: ${i.chequeos.filter((c) => c.estado !== "ok").length} para mirar.`, i.estado === "ok" ? "ok" : "info");
      } catch (e) {
        setError(e instanceof ErrorApi ? e.message : "No pude correr los chequeos (¿la API está despertando?).");
      } finally {
        setCorriendo(false);
      }
    },
    [avisar, recargarResumen],
  );

  useEffect(() => {
    chequear(true);
  }, [chequear]);

  const grupos = useMemo(() => {
    const cheq = [...(informe?.chequeos ?? [])].sort((a, b) => (ORDEN[a.estado] ?? 1) - (ORDEN[b.estado] ?? 1) || a.nombre.localeCompare(b.nombre));
    return { error: cheq.filter((c) => c.estado === "error"), aviso: cheq.filter((c) => c.estado === "aviso"), ok: cheq.filter((c) => c.estado === "ok") };
  }, [informe]);

  const vencimientos = useMemo(() => {
    return (informe?.chequeos ?? [])
      .filter((c) => c.vence)
      .map((c) => ({ c, dias: diasHasta(c.vence) ?? 9999 }))
      .sort((a, b) => a.dias - b.dias);
  }, [informe]);
  const proximos = vencimientos.filter((v) => v.dias < PRONTO_DIAS);

  return (
    <>
      <div className="seccion-cabecera">
        <h2>
          <IconoAdmin nombre="pulso" /> Salud de los servicios
          {informe && <EstadoChip estado={informe.estado} texto={informe.estado === "ok" ? "todo en orden" : informe.estado === "aviso" ? "con avisos" : "con errores"} />}
        </h2>
        <div className="acciones">
          {informe && <span className="suave chico">Chequeado {hace(informe.creado)} en {(informe.ms / 1000).toFixed(1)} s</span>}
          <button className="boton primario" onClick={() => chequear()} disabled={corriendo} aria-busy={corriendo}>
            <IconoAdmin nombre="regenerar" tam={16} style={corriendo ? { animation: "girar 1s linear infinite" } : undefined} /> {corriendo ? "Chequeando…" : "Volver a chequear"}
          </button>
        </div>
      </div>
      {error && <AvisoError texto={error} />}
      {informe?.historial_aviso && <AvisoError texto={informe.historial_aviso} />}

      {informe && (proximos.length > 0 || grupos.error.length > 0 || grupos.aviso.length > 0) && (
        <section className="tarjeta avisos-proximos" aria-label="Avisos próximos">
          <h3>
            <IconoAdmin nombre="calendario" tam={18} /> Para no quedarse sin nada: vencimientos y avisos
          </h3>
          <ul>
            {proximos.map(({ c, dias }) => (
              <li key={"v" + c.nombre} className={dias < AVISO_DIAS ? "e-error" : "e-aviso"}>
                <strong>{nombreChequeo(c.nombre)}</strong>: el token {dias < 0 ? `venció hace ${-dias} días` : dias === 0 ? "vence hoy" : `vence en ${dias} días`} ({fecha(c.vence, false)}).
                {c.que_hacer && <span className="suave"> {c.que_hacer}</span>}
              </li>
            ))}
            {grupos.error.map((c) => (
              <li key={"e" + c.nombre} className="e-error">
                <strong>{nombreChequeo(c.nombre)}</strong>: {c.detalle}
              </li>
            ))}
            {grupos.aviso
              .filter((c) => !proximos.some((p) => p.c.nombre === c.nombre))
              .map((c) => (
                <li key={"a" + c.nombre} className="e-aviso">
                  <strong>{nombreChequeo(c.nombre)}</strong>: {c.detalle}
                </li>
              ))}
          </ul>
          {vencimientos.filter((v) => v.dias >= PRONTO_DIAS).length > 0 && (
            <p className="suave chico">
              Otros vencimientos conocidos: {vencimientos.filter((v) => v.dias >= PRONTO_DIAS).map(({ c, dias }) => `${nombreChequeo(c.nombre)} el ${fecha(c.vence, false)} (${dias} días)`).join(" · ")}.
            </p>
          )}
        </section>
      )}
      {informe && proximos.length === 0 && vencimientos.length > 0 && grupos.error.length === 0 && grupos.aviso.length === 0 && (
        <p className="suave chico">Vencimientos conocidos: {vencimientos.map(({ c, dias }) => `${nombreChequeo(c.nombre)} el ${fecha(c.vence, false)} (en ${dias} días)`).join(" · ")}.</p>
      )}

      {!informe ? (
        <div className="chequeos" aria-busy="true" aria-label="Corriendo los chequeos">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="hueso" style={{ height: 120, borderRadius: 12 }} />
          ))}
          <p className="suave chico" style={{ gridColumn: "1 / -1" }}>
            Consultando Supabase, OpenAI, WordPress, Meta, Google, GitHub Actions y la web… suele tardar menos de 10 segundos.
          </p>
        </div>
      ) : (
        (["error", "aviso", "ok"] as const).map(
          (g) =>
            grupos[g].length > 0 && (
              <section key={g} className="grupo-chequeos" aria-label={g}>
                <h3 className={"grupo-titulo e-" + g}>
                  <EstadoChip estado={g} texto={g === "error" ? `Errores (${grupos[g].length})` : g === "aviso" ? `Avisos (${grupos[g].length})` : `En orden (${grupos[g].length})`} />
                </h3>
                <div className="chequeos">
                  {grupos[g].map((c) => (
                    <TarjetaChequeo key={c.nombre} c={c} />
                  ))}
                </div>
              </section>
            ),
        )
      )}

      {informe && informe.capacidad?.some((c) => c.estado === "aviso" || c.estado === "error") && (
        <div className="aviso" role="status">
          <IconoAdmin nombre="info" tam={18} />
          <span>
            Capacidad de los planes: {informe.capacidad.filter((c) => c.estado === "aviso" || c.estado === "error").map((c) => `${c.nombre} ${c.porcentaje ?? "?"} %`).join(", ")}. <Link to="/administracion/servicios">Ver en Servicios y costos</Link>.
          </span>
        </div>
      )}

      <Historial filas={historial} />
    </>
  );
}

function TarjetaChequeo({ c }: { c: Chequeo }) {
  const dias = diasHasta(c.vence ?? null);
  return (
    <article className={"tarjeta chequeo e-" + c.estado}>
      <header>
        <strong>{nombreChequeo(c.nombre)}</strong>
        <EstadoChip estado={c.estado} />
      </header>
      <p className="chequeo-detalle">{c.detalle}</p>
      {c.que_hacer && (
        <p className="chequeo-hacer">
          <IconoAdmin nombre="info" tam={15} /> <span>{c.que_hacer}</span>
        </p>
      )}
      <footer className="suave chico">
        {c.estado !== "ok" && c.desde && <span title={fecha(c.desde)}>así desde {hace(c.desde)}</span>}
        {c.vence && dias !== null && <span>vence el {fecha(c.vence, false)} ({dias} días)</span>}
        {typeof c.ms === "number" && <span>{c.ms} ms</span>}
        {c.cacheado && <span title="Resultado guardado hace menos de 10 minutos (los chequeos a OpenAI, Meta y Google se repiten como mucho cada 10 min)">en caché</span>}
        {c.corrida?.url && (
          <a href={c.corrida.url} target="_blank" rel="noreferrer">
            ver la corrida <IconoAdmin nombre="externo" tam={12} />
          </a>
        )}
      </footer>
    </article>
  );
}

function Historial({ filas }: { filas: FilaHistorial[] | null }) {
  if (filas === null) return null;
  const corridas = filas.filter((f) => f.estado !== "arranque");
  const arranques = filas.filter((f) => f.estado === "arranque");
  if (!filas.length)
    return (
      <Plegable titulo="Historial">
        <p className="suave chico">Todavía no hay corridas guardadas.</p>
      </Plegable>
    );
  // la línea de tiempo: un punto por corrida, de la más vieja a la más nueva; los arranques como marcas chicas
  const todas = [...filas].sort((a, b) => a.creado.localeCompare(b.creado));
  const t0 = new Date(todas[0].creado).getTime();
  const t1 = Math.max(new Date(todas[todas.length - 1].creado).getTime(), t0 + 1);
  const x = (iso: string) => 2 + ((new Date(iso).getTime() - t0) / (t1 - t0)) * 96;
  // cambios de estado de cada chequeo (para la lista): comparo cada corrida con la anterior
  const cambios: { cuando: string; texto: string; estado: string }[] = [];
  const ordenadas = [...corridas].sort((a, b) => a.creado.localeCompare(b.creado));
  for (let i = 1; i < ordenadas.length; i++) {
    const antes = new Map((ordenadas[i - 1].detalle?.chequeos ?? []).map((c) => [c.nombre, c.estado]));
    for (const c of ordenadas[i].detalle?.chequeos ?? []) {
      const prev = antes.get(c.nombre);
      if (prev && prev !== c.estado) cambios.push({ cuando: ordenadas[i].creado, texto: `${nombreChequeo(c.nombre)}: ${prev} → ${c.estado}`, estado: c.estado });
    }
  }
  cambios.reverse();
  return (
    <Plegable titulo="Historial de los chequeos" abierto resumen={`${corridas.length} corridas · ${arranques.length} arranques de la API desde ${fecha(todas[0].creado)}`}>
      <div className="linea-tiempo" role="img" aria-label="Línea de tiempo de las corridas">
        <div className="linea-tiempo-pista">
          {arranques.map((f) => (
            <span key={"a" + f.id} className="lt-arranque" style={{ left: `${x(f.creado)}%` }} title={`La API arrancó ${fecha(f.creado)} (${hace(f.creado)})`} />
          ))}
          {corridas.map((f) => (
            <span key={f.id} className={"lt-punto e-" + f.estado} style={{ left: `${x(f.creado)}%` }} title={`${fecha(f.creado)}: ${f.estado}${(f.detalle?.chequeos ?? []).filter((c) => c.estado !== "ok").map((c) => `\n${nombreChequeo(c.nombre)}: ${c.estado}`).join("")}`} />
          ))}
        </div>
        <div className="linea-tiempo-fechas suave chico">
          <span>{fecha(todas[0].creado)}</span>
          <span>{fecha(todas[todas.length - 1].creado)}</span>
        </div>
        <div className="linea-tiempo-leyenda suave chico">
          <span>
            <i className="lt-punto e-ok" /> ok
          </span>
          <span>
            <i className="lt-punto e-aviso" /> aviso
          </span>
          <span>
            <i className="lt-punto e-error" /> error
          </span>
          <span>
            <i className="lt-arranque" /> arranque de la API (plan free: cada uno es un despertar en frío)
          </span>
        </div>
      </div>
      {cambios.length > 0 && (
        <>
          <h4>Qué cambió</h4>
          <ul className="cambios-salud">
            {cambios.slice(0, 20).map((c, i) => (
              <li key={i}>
                <span className="suave chico">{fecha(c.cuando)}</span> <EstadoChip estado={c.estado} texto={c.texto} />
              </li>
            ))}
          </ul>
        </>
      )}
      <h4>Últimas corridas</h4>
      <ul className="cambios-salud">
        {corridas.slice(0, 12).map((f) => (
          <li key={f.id}>
            <span className="suave chico">{fecha(f.creado)}</span> <EstadoChip estado={f.estado} />{" "}
            <span className="chico">{(f.detalle?.chequeos ?? []).filter((c) => c.estado !== "ok").map((c) => `${nombreChequeo(c.nombre)} (${c.estado})`).join(", ") || "todo en orden"}</span>
          </li>
        ))}
      </ul>
    </Plegable>
  );
}
