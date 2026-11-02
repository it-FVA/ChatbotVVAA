// Frase del día (22/10): el calendario anual que vivía en el Panel admin de Streamlit (frases_ui.py), con paridad y mejor UX.
// Para aprobadores y admins (botón propio en la barra; pedido de Franco: no va dentro de Administración). Qué hay: cabecera con
// conteos, interruptor (solo admins) y avisos; «Próximas 14 días»; calendario por mes con ARRASTRAR Y SOLTAR entre días (un día
// libre = mover; uno ocupado = intercambiar; desde el backlog = asignar) y «Deshacer»; detalle del día (vista previa de la imagen
// compuesta, editar texto, mover a / intercambiar con otra fecha, cambiar por otra, foto de fondo del banco, saltar, sacar);
// backlog con buscador (validadas sin día · pendientes de validación); «Repartir en el año», vaciar y agregar una frase.
// La configuración de salida (hora, canales, foto por defecto, estilo, pie) vive en Administración → Configuración (solo admins).
// (2/11, reunión del 2/11) Los creadores de contenido también entran: ven el calendario, el backlog y la vista previa, y piden cambios
// («me gustaría que este día salga esta frase»); los aprobadores los aceptan o rechazan desde el panel «Solicitudes». Y todos pueden
// ver el mail de un día como lo arma la plantilla (reproducción de la de Perfit) con «Ver el mail».
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorApi } from "../api";
import { apiChat } from "../apiChat";
import { apiFrases, type Backlog, type Dia, type Frase, type MailEstado, type MailPrevia, type WhatsappPrevia, type Mes, type Proxima, type Resumen, type Solicitud, type Solicitudes } from "../apiFrases";
import { useSesion } from "../App";
import type { FotoBanco } from "../tiposChat";
import { Icono } from "../componentes/Iconos";
import Modal from "../componentes/Modal";
import { Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import "../frases.css";

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const DIAS = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"];
const ICONO_ESTADO: Record<string, string> = { programada: "calendario", publicada: "megafono", simulada: "ojo", saltada: "chevron" };

type Arrastre = { id: string; desde: string | null; texto: string };
type Deshacer = { texto: string; hacer: () => Promise<void> };

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function fechaLarga(s: string) {
  const [y, m, d] = s.split("-").map(Number);
  return `${d} de ${MESES[m - 1]} de ${y}`;
}
function fechaCorta(s: string) {
  const [, m, d] = s.split("-").map(Number);
  return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}
function recortar(t: string, n: number) {
  t = (t || "").replace(/\s+/g, " ").trim();
  return t.length <= n ? t : t.slice(0, n - 1).trimEnd() + "…";
}
function mensajeDe(e: unknown) {
  return e instanceof ErrorApi ? e.message : "No pude conectarme con la API.";
}

export default function FraseDelDia() {
  const { yo } = useSesion();
  const { avisar } = useToast();
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [proximas, setProximas] = useState<Proxima[] | null>(null);
  const [cuando, setCuando] = useState<{ anio: number; mes: number } | null>(null);
  const [mes, setMes] = useState<Mes | null>(null);
  const [diaSel, setDiaSel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [arrastre, setArrastre] = useState<Arrastre | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);
  const [deshacer, setDeshacer] = useState<Deshacer | null>(null);
  const [modal, setModal] = useState<"repartir" | "vaciar" | "nueva" | null>(null);
  const [verMail, setVerMail] = useState<string | null>(null); // (2/11) la fecha del mail que se está mirando
  const [verWa, setVerWa] = useState<string | null>(null); // (2/11 tarde) prototipo WhatsApp: la fecha del mensaje que se está mirando
  const [solapaPedida, setSolapaPedida] = useState<{ s: Solapa; n: number } | null>(null); // (2/11 tarde) desde el mail: abrir el día en «Foto de fondo»
  const [ocupado, setOcupado] = useState(false);
  const [version, setVersion] = useState(0); // para refrescar backlog y próximas tras un cambio
  const timerDeshacer = useRef<number | null>(null);

  const cargarResumen = useCallback(async () => {
    try {
      const r = await apiFrases.resumen();
      setResumen(r);
      setError(null);
      if (r.hoy && !cuando) {
        const [y, m] = r.hoy.split("-").map(Number);
        setCuando({ anio: y, mes: m });
      }
    } catch (e) {
      setError(mensajeDe(e));
      setResumen((r) => r ?? { disponible: false, admin: false, conteos: {}, activa: false, avisos: [] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cargarMes = useCallback(async () => {
    if (!cuando) return;
    try {
      setMes(await apiFrases.mes(cuando.anio, cuando.mes));
    } catch (e) {
      avisar(mensajeDe(e), "error");
    }
  }, [cuando, avisar]);

  const recargar = useCallback(() => {
    cargarResumen();
    cargarMes();
    apiFrases.proximas(14).then(setProximas).catch(() => {});
    setVersion((v) => v + 1);
  }, [cargarResumen, cargarMes]);

  useEffect(() => {
    cargarResumen();
    apiFrases.proximas(14).then(setProximas).catch(() => {});
  }, [cargarResumen]);
  useEffect(() => {
    setMes(null);
    cargarMes();
  }, [cargarMes]);

  function ofrecerDeshacer(texto: string, hacer: () => Promise<void>) {
    if (timerDeshacer.current) window.clearTimeout(timerDeshacer.current);
    setDeshacer({ texto, hacer });
    timerDeshacer.current = window.setTimeout(() => setDeshacer(null), 15000);
  }

  async function correr(accion: () => Promise<string | void>, deshacerCon?: { texto: string; hacer: () => Promise<void> }) {
    setOcupado(true);
    try {
      const msg = await accion();
      if (msg) avisar(msg);
      if (deshacerCon) ofrecerDeshacer(deshacerCon.texto, deshacerCon.hacer);
      recargar();
    } catch (e) {
      avisar(mensajeDe(e), "error");
    } finally {
      setOcupado(false);
    }
  }

  /** Soltar una frase sobre un día: libre → mover (o asignar); ocupado → intercambiar (o cambiar por otra si venía del backlog). */
  async function soltar(fecha: string) {
    const a = arrastre;
    setArrastre(null);
    setSobre(null);
    if (!a || !mes || a.desde === fecha) return;
    const destino = mes.frases[fecha];
    if (destino?.cerrada) {
      avisar("La frase de ese día ya está en la cola o ya salió: no se puede cambiar.", "error");
      return;
    }
    if (!destino) {
      await correr(
        async () => (await apiFrases.mover(a.id, fecha)).mensaje,
        a.desde ? { texto: `Movida del ${fechaCorta(a.desde)} al ${fechaCorta(fecha)}.`, hacer: async () => void (await apiFrases.mover(a.id, a.desde!)) } : { texto: `Asignada al ${fechaCorta(fecha)}.`, hacer: async () => void (await apiFrases.sacar(a.id)) },
      );
    } else {
      await correr(
        async () => (a.desde ? `Intercambiadas: ${fechaCorta(a.desde)} ↔ ${fechaCorta(fecha)}.` : `Cambiada: la del ${fechaCorta(fecha)} volvió al backlog.`) && (await apiFrases.intercambiar(a.id, destino.id)).mensaje,
        { texto: a.desde ? `Intercambiadas ${fechaCorta(a.desde)} y ${fechaCorta(fecha)}.` : `Cambiada la frase del ${fechaCorta(fecha)}.`, hacer: async () => void (await apiFrases.intercambiar(a.id, destino.id)) },
      );
    }
  }

  async function alternarActiva() {
    if (!resumen?.admin) return;
    await correr(async () => (await apiFrases.activa(!resumen.activa)).mensaje);
  }

  const meses = useMemo(() => {
    if (!resumen?.hoy) return [];
    const [y0, m0] = resumen.hoy.split("-").map(Number);
    const out: { anio: number; mes: number }[] = [];
    let y = y0;
    let m = m0;
    for (let i = 0; i < 13; i++) {
      out.push({ anio: y, mes: m });
      m += 1;
      if (m > 12) {
        m = 1;
        y += 1;
      }
    }
    return out;
  }, [resumen?.hoy]);

  const aprueba = resumen ? !!resumen.aprueba : !!yo?.rol.aprueba;
  const c = resumen?.conteos ?? {};

  return (
    <div className="pagina frases">
      <header className="pagina-cabecera">
        <div>
          <h1>Frase del día</h1>
          <p className="suave">
            {aprueba
              ? "Una frase por día, que sale sola cada mañana por mail y redes con una foto de fondo. Solo entran las validadas del Sheet. Arrastrá una frase a otro día para moverla o intercambiarla; desde el backlog, para asignarla."
              : "Una frase por día, que sale sola cada mañana por mail y redes con una foto de fondo. Acá ves qué sale cada día. Si querés que un día salga otra frase, abrí ese día y pedí el cambio: lo revisa quien aprueba."}
          </p>
        </div>
        <div className="acciones">
          {aprueba && (
            <>
              <button type="button" className="boton primario" onClick={() => setModal("repartir")} disabled={!resumen?.disponible}>
                <Icono nombre="calendario" tam={16} /> Repartir en el año
              </button>
              <button type="button" className="boton" onClick={() => setModal("nueva")} disabled={!resumen?.disponible}>
                <Icono nombre="mas" tam={16} /> Agregar una frase
              </button>
            </>
          )}
          {resumen?.admin && (
            <Link className="boton sutil" to="/administracion/configuracion" title="Hora de salida, canales, foto por defecto, estilo y pie del posteo">
              <Icono nombre="ajustar" tam={16} /> Configuración
            </Link>
          )}
        </div>
      </header>

      {error && (
        <div className="aviso error" role="alert">
          <Icono nombre="alerta" tam={18} /> {error}
        </div>
      )}

      {resumen === null ? (
        <div className="tarjeta" aria-busy="true">
          <Hueso alto={22} ancho="60%" />
          <Hueso alto={14} style={{ marginTop: 10 }} />
        </div>
      ) : (
        <section className="tarjeta fd-cabecera" aria-label="Estado">
          <div className="fd-conteos">
            <Conteo n={c.sin_fecha_validadas} texto="en el backlog" ayuda="validadas sin día" />
            <Conteo n={c.programadas} texto="programadas" ayuda="desde hoy" />
            <Conteo n={c.publicadas} texto="publicadas" />
            <Conteo n={c.pendientes_validar} texto="pendientes de validar" ayuda="esperan el OK de Pato" suave />
            <span className="suave chico">
              {c.validadas ?? 0} validadas de {c.total ?? 0} cargadas
            </span>
          </div>
          <label className={"interruptor fd-activa" + (resumen.admin ? "" : " solo-lectura")} title={resumen.admin ? "Apagada: el calendario se arma igual pero no sale nada. Prendida: cada día la frase de ese día se encola como posteo." : "El interruptor lo cambia un admin"}>
            <input type="checkbox" checked={resumen.activa} onChange={alternarActiva} disabled={!resumen.admin || ocupado} />
            <span>
              Frase del día <strong>{resumen.activa ? "activa" : "apagada"}</strong>
              {resumen.hora && <span className="suave chico"> · sale a las {resumen.hora} por {(resumen.canales ?? []).join(", ")}</span>}
            </span>
          </label>
          <div className="fd-lineas suave chico">
            {resumen.frases_nuevas_hasta ? (
              <span>
                Hay frases nuevas hasta el <strong>{fechaLarga(resumen.frases_nuevas_hasta)}</strong>
                {resumen.nuevas_sin_dia ? ` (${resumen.nuevas_sin_dia} todavía sin día)` : ""}; después vuelve a empezar por las más antiguas publicadas. Si un día queda vacío, la cola le asigna sola la siguiente de la rotación.
              </span>
            ) : (
              <span>Ya salieron todas las validadas al menos una vez: siguen en rotación, de la más antigua a la más reciente.</span>
            )}
            {resumen.manana && (
              <span>
                Mañana ({resumen.manana.fecha_texto}):{" "}
                {resumen.manana.frase ? (
                  resumen.manana.frase.estado === "saltada" ? (
                    "salteado, no sale nada."
                  ) : (
                    <>
                      «{recortar(resumen.manana.frase.texto, 90)}» — {resumen.manana.frase.autor}
                      {resumen.manana.en_cola ? " · ya está en la cola." : resumen.activa ? " · la cola la encola en su próxima pasada." : ""}
                    </>
                  )
                ) : (
                  "sin frase asignada."
                )}
              </span>
            )}
          </div>
          {resumen.avisos.map((a, i) => (
            <div key={i} className="aviso chico">
              <Icono nombre="alerta" tam={16} /> {a}
            </div>
          ))}
        </section>
      )}

      {resumen && <MailPanel admin={resumen.admin} aprueba={aprueba} hoy={resumen.hoy} onVerMail={(f) => setVerMail(f)} />}
      {resumen?.disponible && <SolicitudesPanel aprueba={aprueba} version={version} onCambio={recargar} onVerDia={setDiaSel} />}

      {deshacer && (
        <div className="aviso fd-deshacer" role="status">
          <Icono nombre="check" tam={16} /> <span>{deshacer.texto}</span>
          <button
            type="button"
            className="boton chico"
            onClick={() => {
              const d = deshacer;
              setDeshacer(null);
              correr(async () => {
                await d.hacer();
                return "Deshecho.";
              });
            }}
            disabled={ocupado}
          >
            <Icono nombre="deshacer" tam={14} /> Deshacer
          </button>
        </div>
      )}

      <div className="fd-grilla">
        <section className="fd-calendario" aria-label="Calendario">
          <div className="fd-mes-nav">
            <button type="button" className="boton chico icono-solo" aria-label="Mes anterior" onClick={() => cuando && setCuando(mesVecino(cuando, -1))} disabled={!cuando || !meses.length || (cuando.anio === meses[0].anio && cuando.mes === meses[0].mes)}>
              <Icono nombre="chevron" tam={16} style={{ transform: "rotate(180deg)" }} />
            </button>
            <select value={cuando ? `${cuando.anio}-${cuando.mes}` : ""} onChange={(e) => setCuando({ anio: Number(e.target.value.split("-")[0]), mes: Number(e.target.value.split("-")[1]) })} aria-label="Mes">
              {meses.map((x) => (
                <option key={`${x.anio}-${x.mes}`} value={`${x.anio}-${x.mes}`}>
                  {MESES[x.mes - 1][0].toUpperCase() + MESES[x.mes - 1].slice(1)} {x.anio}
                </option>
              ))}
            </select>
            <button type="button" className="boton chico icono-solo" aria-label="Mes siguiente" onClick={() => cuando && setCuando(mesVecino(cuando, 1))} disabled={!cuando || !meses.length || (cuando.anio === meses[meses.length - 1].anio && cuando.mes === meses[meses.length - 1].mes)}>
              <Icono nombre="chevron" tam={16} />
            </button>
            <span className="suave chico fd-leyenda">
              <Icono nombre="calendario" tam={13} /> programada · <Icono nombre="megafono" tam={13} /> publicada · <Icono nombre="ojo" tam={13} /> simulada · ⏭ salteada · ↻ ya salió antes
            </span>
          </div>
          {mes === null ? (
            <div className="fd-dias" aria-busy="true">
              {Array.from({ length: 35 }).map((_, i) => (
                <Hueso key={i} alto={74} radio={8} />
              ))}
            </div>
          ) : (
            <div className="fd-dias" role="grid" aria-label={`${MESES[mes.mes - 1]} ${mes.anio}`}>
              {DIAS.map((d) => (
                <div key={d} className="fd-dia-nombre" role="columnheader">
                  {d}
                </div>
              ))}
              {Array.from({ length: mes.primer_dia_semana }).map((_, i) => (
                <div key={"v" + i} className="fd-dia vacio" aria-hidden="true" />
              ))}
              {Array.from({ length: mes.dias }).map((_, i) => {
                const f = `${mes.anio}-${String(mes.mes).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`;
                const fr = mes.frases[f];
                const pasado = f < mes.hoy;
                const hoy = f === mes.hoy;
                const puedeSoltar = aprueba && !!arrastre && !pasado && arrastre.desde !== f && !(fr?.cerrada);
                return (
                  <div
                    key={f}
                    role="gridcell"
                    tabIndex={0}
                    className={"fd-dia" + (hoy ? " hoy" : "") + (pasado ? " pasado" : "") + (fr ? " con-frase " + fr.estado : " libre") + (sobre === f && puedeSoltar ? " sobre" : "") + (arrastre && !puedeSoltar ? " no-soltar" : "")}
                    onClick={() => setDiaSel(f)}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setDiaSel(f))}
                    onDragOver={(e) => {
                      if (!puedeSoltar) return;
                      e.preventDefault();
                      e.dataTransfer.dropEffect = "move";
                      if (sobre !== f) setSobre(f);
                    }}
                    onDragLeave={() => sobre === f && setSobre(null)}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (puedeSoltar) soltar(f);
                    }}
                    aria-label={`${i + 1}: ${fr ? recortar(fr.texto, 60) : "sin frase"}`}
                  >
                    <div className="fd-dia-num">
                      <span>{i + 1}</span>
                      {hoy && <span className="chip amarillo chico">hoy</span>}
                      {fr && (
                        <span className="fd-estado" title={fr.estado_texto}>
                          {fr.estado === "saltada" ? "⏭" : <Icono nombre={ICONO_ESTADO[fr.estado] ?? "calendario"} tam={13} />}
                          {fr.repetida ? " ↻" : ""}
                        </span>
                      )}
                    </div>
                    {fr ? (
                      <div
                        className={"fd-frase" + (fr.cerrada || pasado || !aprueba ? " fija" : "")}
                        draggable={aprueba && !fr.cerrada && !pasado}
                        onDragStart={(e) => aprueba && empezarArrastre(e, { id: fr.id, desde: f, texto: fr.texto }, setArrastre)}
                        onDragEnd={() => (setArrastre(null), setSobre(null))}
                        title={!aprueba ? "Abrí el día para ver la frase o pedir un cambio" : fr.cerrada ? "En la cola o ya salió: no se mueve" : "Arrastrá a otro día para mover o intercambiar"}
                      >
                        <span className="fd-texto">{recortar(fr.texto, 70)}</span>
                        {fr.autor && <span className="fd-autor suave chico">{fr.autor}</span>}
                      </div>
                    ) : (
                      <div className="fd-sin suave chico">{pasado ? "—" : "sin frase"}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <aside className="fd-lateral">
          <Proximas lista={proximas} onElegir={setDiaSel} />
          <BacklogPanel version={version} arrastrando={!!arrastre} soloLectura={!aprueba} onArrastrar={setArrastre} onSoltarArrastre={() => (setArrastre(null), setSobre(null))} onElegir={(fr) => setDiaSel(fr.fecha ?? diaSel)} />
        </aside>
      </div>

      {diaSel && (
        <DetalleDia
          fecha={diaSel}
          solapaPedida={solapaPedida}
          version={version}
          aprueba={aprueba}
          onVerMail={() => setVerMail(diaSel)}
          onVerWhatsapp={() => setVerWa(diaSel)}
          onCerrar={() => setDiaSel(null)}
          onCambio={(nuevaFecha) => {
            recargar();
            if (nuevaFecha !== undefined) setDiaSel(nuevaFecha);
          }}
          ofrecerDeshacer={ofrecerDeshacer}
        />
      )}
      {verWa && <VerWhatsapp fecha={verWa} onCerrar={() => setVerWa(null)} />}
      {verMail && (
        <VerMail
          fecha={verMail}
          onCerrar={() => setVerMail(null)}
          onCambiarFoto={() => {
            // (2/11 tarde) el aprobador cambia la foto desde el mail; el creador va al día a pedirla
            setDiaSel(verMail);
            setSolapaPedida({ s: "foto", n: Date.now() });
            setVerMail(null);
          }}
        />
      )}
      {modal === "repartir" && resumen && (
        <Repartir
          hoy={resumen.hoy || iso(new Date())}
          sinDia={c.sin_fecha_validadas ?? 0}
          onCerrar={() => setModal(null)}
          onHecho={(msg) => {
            setModal(null);
            avisar(msg);
            recargar();
          }}
        />
      )}
      {modal === "vaciar" && (
        <Modal titulo="¿Vaciar el calendario?" onCerrar={() => setModal(null)} peligro>
          <p className="suave">Saca TODAS las frases del calendario que todavía no salieron (vuelven a «sin día»). Las que ya están en la cola o ya salieron quedan.</p>
          <div className="acciones" style={{ justifyContent: "flex-end" }}>
            <button type="button" className="boton" onClick={() => setModal(null)}>
              Cancelar
            </button>
            <button type="button" className="boton peligro" onClick={() => correr(async () => (await apiFrases.vaciar()).mensaje).then(() => setModal(null))} disabled={ocupado}>
              <Icono nombre="tacho" /> Sí, vaciar
            </button>
          </div>
        </Modal>
      )}
      {modal === "nueva" && (
        <NuevaFrase
          onCerrar={() => setModal(null)}
          onHecha={() => {
            setModal(null);
            avisar("Agregada: quedó validada y sin día. Asignala desde el backlog o un día libre.");
            recargar();
          }}
        />
      )}

      <p className="suave chico fd-pie">
        {aprueba && (
          <>
            <button type="button" className="boton sutil chico" onClick={() => setModal("vaciar")} disabled={!resumen?.disponible}>
              <Icono nombre="tacho" tam={14} /> Vaciar el calendario
            </button>{" "}
          </>
        )}
        Las frases vienen del Sheet Frases_consolidadas_591 (importar_frases.py).
      </p>
    </div>
  );
}

function mesVecino(c: { anio: number; mes: number }, paso: number) {
  let m = c.mes + paso;
  let y = c.anio;
  if (m > 12) (m = 1), (y += 1);
  if (m < 1) (m = 12), (y -= 1);
  return { anio: y, mes: m };
}

function empezarArrastre(e: DragEvent, a: Arrastre, set: (a: Arrastre) => void) {
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", a.id);
  set(a);
}

function Conteo({ n, texto, ayuda, suave }: { n: number | undefined; texto: string; ayuda?: string; suave?: boolean }) {
  return (
    <span className={"fd-conteo" + (suave ? " suave" : "")} title={ayuda}>
      <strong>{n ?? 0}</strong> {texto}
    </span>
  );
}

// ---------------- Próximas 14 días ----------------
function Proximas({ lista, onElegir }: { lista: Proxima[] | null; onElegir: (f: string) => void }) {
  return (
    <details className="tarjeta fd-panel" open>
      <summary>
        <Icono nombre="chevron" tam={16} /> <Icono nombre="reloj" tam={16} /> Próximas 14 días
      </summary>
      <ul className="fd-proximas">
        {lista === null && <li className="suave chico">Cargando…</li>}
        {lista?.map((p) => (
          <li key={p.fecha} className={p.frase ? p.frase.estado : "libre"}>
            <button type="button" onClick={() => onElegir(p.fecha)} title="Ver el día">
              <span className="fd-prox-fecha">
                {p.dia.slice(0, 2)} {fechaCorta(p.fecha)}
              </span>
              {p.frase ? (
                <span className="fd-prox-texto">
                  {recortar(p.frase.texto, 80)} <em className="suave">— {p.frase.autor}</em>
                  <span className="fd-prox-estado chico suave">
                    {" "}
                    · {p.frase.estado === "saltada" ? "⏭ salteada" : p.frase.estado}
                    {p.frase.repetida ? " ↻" : ""}
                  </span>
                </span>
              ) : (
                <span className="fd-prox-texto suave">
                  <em>sin frase (la cola asigna la siguiente de la rotación)</em>
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}

// ---------------- Backlog ----------------
function BacklogPanel({ version, arrastrando, soloLectura, onArrastrar, onSoltarArrastre, onElegir }: { version: number; arrastrando: boolean; soloLectura?: boolean; onArrastrar: (a: Arrastre) => void; onSoltarArrastre: () => void; onElegir: (f: Frase) => void }) {
  const [q, setQ] = useState("");
  const [datos, setDatos] = useState<Backlog | null>(null);
  const [solapa, setSolapa] = useState<"sin_dia" | "pendientes">("sin_dia");
  useEffect(() => {
    const t = window.setTimeout(() => apiFrases.backlog(q).then(setDatos).catch(() => setDatos({ sin_dia: [], sin_dia_total: 0, pendientes: [], pendientes_total: 0 })), 250);
    return () => window.clearTimeout(t);
  }, [q, version]);
  const lista = datos ? (solapa === "sin_dia" ? datos.sin_dia : datos.pendientes) : null;
  return (
    <details className={"tarjeta fd-panel fd-backlog" + (arrastrando ? " arrastrando" : "")} open>
      <summary>
        <Icono nombre="chevron" tam={16} /> <Icono nombre="pelicula" tam={16} /> Backlog
        {datos && (
          <span className="suave chico">
            {" "}
            · {datos.sin_dia_total} sin día · {datos.pendientes_total} pendientes
          </span>
        )}
      </summary>
      <div className="fd-panel-cuerpo">
        <label className="buscar">
          <Icono nombre="buscar" tam={16} />
          <input type="search" placeholder="Buscar por texto o autor" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Buscar en el backlog" />
        </label>
        <div className="solapas chico" role="tablist">
          <button role="tab" aria-selected={solapa === "sin_dia"} className={"solapa" + (solapa === "sin_dia" ? " activa" : "")} onClick={() => setSolapa("sin_dia")}>
            Validadas sin día {datos ? `(${datos.sin_dia_total})` : ""}
          </button>
          <button role="tab" aria-selected={solapa === "pendientes"} className={"solapa" + (solapa === "pendientes" ? " activa" : "")} onClick={() => setSolapa("pendientes")}>
            Pendientes {datos ? `(${datos.pendientes_total})` : ""}
          </button>
        </div>
        {solapa === "pendientes" && <p className="suave chico">Las nuevas del Sheet esperan el OK de Pato: no se pueden asignar hasta que estén validadas (se marcan en el Sheet y se vuelve a correr importar_frases.py).</p>}
        {solapa === "sin_dia" && <p className="suave chico">{soloLectura ? "Las validadas que todavía no tienen día. Para pedir que una salga un día, abrí ese día en el calendario." : "Arrastrá una frase a un día del calendario para asignarla (si el día está ocupado, la reemplaza y esa vuelve acá)."}</p>}
        <ul className="fd-lista">
          {lista === null && <li className="suave chico">Cargando…</li>}
          {lista && lista.length === 0 && <li className="suave chico">{q ? "Nada que coincida." : solapa === "sin_dia" ? "No hay validadas sin día: están todas en el calendario." : "No hay pendientes."}</li>}
          {lista?.map((f) => (
            <li
              key={f.id}
              className={"fd-item" + (solapa === "sin_dia" && !soloLectura ? " arrastrable" : "")}
              draggable={solapa === "sin_dia" && !soloLectura}
              onDragStart={(e) => solapa === "sin_dia" && !soloLectura && empezarArrastre(e, { id: f.id, desde: null, texto: f.texto }, onArrastrar)}
              onDragEnd={onSoltarArrastre}
              onClick={() => onElegir(f)}
              title={soloLectura ? (solapa === "sin_dia" ? "Validada, sin día todavía" : "Pendiente de validación") : solapa === "sin_dia" ? "Arrastrá a un día del calendario" : "Pendiente de validación"}
            >
              <span className="fd-texto">{recortar(f.texto, 140)}</span>
              <span className="suave chico">
                {f.autor}
                {f.veces_publicada ? ` · ↻ salió ${f.veces_publicada} ${f.veces_publicada === 1 ? "vez" : "veces"}` : ""}
                {solapa === "pendientes" ? " · 🕓 pendiente" : ""}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}

// ---------------- Detalle de un día ----------------
type Solapa = "texto" | "mover" | "cambiar" | "foto" | "saltar";

function DetalleDia({ fecha, version, aprueba, solapaPedida, onVerMail, onVerWhatsapp, onCerrar, onCambio, ofrecerDeshacer }: { fecha: string; version: number; aprueba: boolean; solapaPedida?: { s: Solapa; n: number } | null; onVerMail: () => void; onVerWhatsapp: () => void; onCerrar: () => void; onCambio: (nuevaFecha?: string | null) => void; ofrecerDeshacer: (texto: string, hacer: () => Promise<void>) => void }) {
  const { avisar } = useToast();
  const [d, setD] = useState<Dia | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [solapa, setSolapa] = useState<Solapa>(solapaPedida?.s ?? "texto");
  useEffect(() => {
    if (solapaPedida) setSolapa(solapaPedida.s);
  }, [solapaPedida]);
  const [ocupado, setOcupado] = useState(false);
  const [previaOk, setPreviaOk] = useState<boolean | null>(null);
  const [v, setV] = useState(0);

  const cargar = useCallback(() => {
    apiFrases
      .dia(fecha)
      .then((x) => {
        setD(x);
        setError(null);
        setPreviaOk(null);
      })
      .catch((e) => setError(mensajeDe(e)));
  }, [fecha]);
  useEffect(cargar, [cargar, version]);

  async function correr(accion: () => Promise<string | void>, despues?: string | null, deshacerCon?: { texto: string; hacer: () => Promise<void> }) {
    setOcupado(true);
    try {
      const msg = await accion();
      if (msg) avisar(msg);
      if (deshacerCon) ofrecerDeshacer(deshacerCon.texto, deshacerCon.hacer);
      setV((x) => x + 1);
      onCambio(despues);
    } catch (e) {
      avisar(mensajeDe(e), "error");
    } finally {
      setOcupado(false);
    }
  }

  const f = d?.frase ?? null;
  const titulo = `${d ? d.dia[0].toUpperCase() + d.dia.slice(1) + " " : ""}${fechaLarga(fecha)}`;

  return (
    <Modal titulo={titulo} onCerrar={onCerrar} ancho={760}>
      {error && <div className="aviso error">{error}</div>}
      {!d && !error && <p className="suave">Cargando…</p>}
      {d && !f && !aprueba && (
        <>
          <p className="suave">Este día no tiene frase{d.pasado ? " y ya pasó." : " todavía: la cola le asigna la siguiente de la rotación. Si querés que salga una en particular, pedila:"}</p>
          {!d.pasado && <SolicitarCambio fecha={fecha} actual={null} onHecho={() => onCambio()} />}
        </>
      )}
      {d && !f && aprueba && (
        <>
          <p className="suave">Este día no tiene frase{d.pasado ? " y ya pasó." : ". Elegí una de las validadas sin día:"}</p>
          {!d.pasado && (
            <Buscador
              onElegir={(fr) =>
                correr(
                  async () => (await apiFrases.mover(fr.id, fecha)).mensaje,
                  undefined,
                  { texto: `Asignada al ${fechaCorta(fecha)}.`, hacer: async () => void (await apiFrases.sacar(fr.id)) },
                )
              }
              textoBoton="Asignar a este día"
              ocupado={ocupado}
            />
          )}
        </>
      )}
      {d && f && (
        <div className="fd-detalle">
          <div className="fd-detalle-izq">
            <blockquote className="fd-cita">{f.texto}</blockquote>
            <p className="chico">
              <strong>{f.autor || "(sin autor)"}</strong> · {f.estado === "saltada" ? "⏭ " : ""}
              {f.estado_texto}
              {f.repetida && ` · ↻ ya salió ${f.veces_publicada} ${f.veces_publicada === 1 ? "vez" : "veces"} (última ${String(f.ultima_publicada).slice(0, 10)})`}
              {f.fuente && ` · fuente: ${f.fuente}`}
              {f.tema && ` · tema: ${f.tema}`}
            </p>
            {d.cola && (
              <p className="suave chico">
                En la cola: estado <strong>{d.cola.estado}</strong>, sale el {String(d.cola.fecha_programada || "").slice(0, 16).replace("T", " ")}
                {d.cola.permalink && (
                  <>
                    {" "}
                    ·{" "}
                    <a href={d.cola.permalink} target="_blank" rel="noreferrer">
                      ver publicación
                    </a>
                  </>
                )}
              </p>
            )}
            {f.cerrada ? (
              <div className="aviso chico">
                <Icono nombre="info" tam={16} /> Esta frase ya está en la cola o ya salió: {aprueba ? "no se mueve ni se edita desde acá. Para frenarla, cancelá la pieza en la cola (Aprobación → En cola)." : "ese día ya no se puede cambiar."}
              </div>
            ) : d.pasado ? (
              <div className="aviso chico">
                <Icono nombre="info" tam={16} /> Ese día ya pasó.
              </div>
            ) : null}
          </div>
          <div className="fd-detalle-der">
            <div className="fd-previa">
              {previaOk === false ? (
                <p className="suave chico">Sin foto para la vista previa: elegí una en «Foto de fondo» o cargá una por defecto en Configuración.</p>
              ) : (
                <img src={apiFrases.previaUrl(f.id, `${v}-${f.imagen_url || ""}`)} alt="Así saldría la imagen" onLoad={() => setPreviaOk(true)} onError={() => setPreviaOk(false)} />
              )}
              {d.foto?.url && previaOk !== false && <span className="suave chico">Así saldría (foto: {d.foto.de_donde})</span>}
              <div className="fd-previa-botones">
                <button type="button" className="boton chico" onClick={onVerMail} title="El mail de ese día, armado con la plantilla">
                  <Icono nombre="sobre" tam={15} /> Ver el mail
                </button>
                <button type="button" className="boton chico" onClick={onVerWhatsapp} title="Cómo saldría en el grupo de WhatsApp de la comunidad (prototipo, todavía no se manda)">
                  <Icono nombre="celular" tam={15} /> Ver el WhatsApp
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {d && f && !f.cerrada && !d.pasado && !aprueba && (
        <>
          <h3 className="fd-sub">Pedir un cambio para este día</h3>
          <SolicitarCambio fecha={fecha} actual={f} onHecho={() => onCambio()} />
        </>
      )}

      {d && f && !f.cerrada && !d.pasado && aprueba && (
        <>
          <div className="solapas chico fd-solapas" role="tablist">
            {(
              [
                ["texto", "Texto"],
                ["mover", "Mover / intercambiar"],
                ["cambiar", "Cambiar por otra"],
                ["foto", "Foto de fondo"],
                ["saltar", "Saltar / sacar"],
              ] as [Solapa, string][]
            ).map(([k, t]) => (
              <button key={k} role="tab" aria-selected={solapa === k} className={"solapa" + (solapa === k ? " activa" : "")} onClick={() => setSolapa(k)}>
                {t}
              </button>
            ))}
          </div>
          {solapa === "texto" && <EditarTexto f={f} ocupado={ocupado} onGuardar={(texto, autor) => correr(async () => ((await apiFrases.editar(f.id, { texto, autor })), "Guardado."))} />}
          {solapa === "mover" && <MoverIntercambiar f={f} fecha={fecha} hoy={d.pasado ? fecha : undefined} ocupado={ocupado} correr={correr} />}
          {solapa === "cambiar" && (
            <>
              <p className="suave chico">La frase de este día vuelve a «sin día» y entra la que elijas.</p>
              <Buscador
                excluir={f.id}
                textoBoton="Poner esta en su lugar"
                ocupado={ocupado}
                onElegir={(otra) =>
                  correr(
                    async () => {
                      await apiFrases.intercambiar(f.id, otra.id);
                      return "Cambiada.";
                    },
                    undefined,
                    { texto: `Cambiada la frase del ${fechaCorta(fecha)}.`, hacer: async () => void (await apiFrases.intercambiar(f.id, otra.id)) },
                  )
                }
              />
            </>
          )}
          {solapa === "foto" && <FotoFondo f={f} ocupado={ocupado} correr={correr} />}
          {solapa === "saltar" && (
            <div className="fd-dos">
              <div>
                {f.estado === "saltada" ? (
                  <>
                    <p className="suave chico">Este día está salteado: no sale nada. La frase queda guardada en este día.</p>
                    <button type="button" className="boton" onClick={() => correr(async () => ((await apiFrases.editar(f.id, { estado: "programada" })), "Vuelve a estar programada."))} disabled={ocupado}>
                      <Icono nombre="deshacer" tam={15} /> Volver a programarla
                    </button>
                  </>
                ) : (
                  <>
                    <p className="suave chico">Saltar: ese día no sale nada; la frase queda en su lugar (marcada ⏭) y se puede volver a programar.</p>
                    <button type="button" className="boton" onClick={() => correr(async () => ((await apiFrases.editar(f.id, { estado: "saltada" })), "Salteado."))} disabled={ocupado}>
                      ⏭ Saltar ese día
                    </button>
                  </>
                )}
              </div>
              <div>
                <p className="suave chico">Sacar del calendario: la frase vuelve a «sin día» y el día queda libre (lo llena «Repartir», una asignación a mano o la rotación de la cola).</p>
                <button
                  type="button"
                  className="boton peligro sutil"
                  onClick={() => correr(async () => (await apiFrases.sacar(f.id)).mensaje, null, { texto: `Sacada del ${fechaCorta(fecha)}.`, hacer: async () => void (await apiFrases.mover(f.id, fecha)) })}
                  disabled={ocupado}
                >
                  <Icono nombre="tacho" tam={15} /> Sacar del calendario
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}

function EditarTexto({ f, ocupado, onGuardar }: { f: Frase; ocupado: boolean; onGuardar: (texto: string, autor: string) => void }) {
  const [texto, setTexto] = useState(f.texto);
  const [autor, setAutor] = useState(f.autor || "");
  useEffect(() => {
    setTexto(f.texto);
    setAutor(f.autor || "");
  }, [f]);
  const sinCambios = texto.trim() === f.texto && autor.trim() === (f.autor || "");
  return (
    <div className="fd-form">
      <label>
        Frase
        <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={4} />
      </label>
      <label>
        Autor
        <input value={autor} onChange={(e) => setAutor(e.target.value)} />
      </label>
      <div className="acciones">
        <button type="button" className="boton primario" onClick={() => onGuardar(texto, autor)} disabled={ocupado || sinCambios || !texto.trim()}>
          <Icono nombre="check" tam={15} /> Guardar el texto
        </button>
      </div>
    </div>
  );
}

function MoverIntercambiar({ f, fecha, ocupado, correr }: { f: Frase; fecha: string; hoy?: string; ocupado: boolean; correr: (a: () => Promise<string | void>, despues?: string | null, deshacer?: { texto: string; hacer: () => Promise<void> }) => Promise<void> }) {
  const [nueva, setNueva] = useState(fecha);
  const [otra, setOtra] = useState(() => iso(new Date(new Date(fecha + "T12:00:00").getTime() + 86400000)));
  const [otraFrase, setOtraFrase] = useState<Dia | null>(null);
  useEffect(() => {
    if (!otra || otra === fecha) {
      setOtraFrase(null);
      return;
    }
    apiFrases.dia(otra).then(setOtraFrase).catch(() => setOtraFrase(null));
  }, [otra, fecha]);
  const puedeInter = !!otraFrase?.frase && !otraFrase.frase.cerrada && !otraFrase.pasado;
  return (
    <div className="fd-dos">
      <div className="fd-form">
        <strong className="chico">Mover a otra fecha</strong>
        <p className="suave chico">La fecha destino tiene que estar libre. (También podés arrastrar la frase en el calendario.)</p>
        <input type="date" value={nueva} onChange={(e) => setNueva(e.target.value)} aria-label="Nueva fecha" />
        <button type="button" className="boton" disabled={ocupado || !nueva || nueva === fecha} onClick={() => correr(async () => (await apiFrases.mover(f.id, nueva)).mensaje, nueva, { texto: `Movida del ${fechaCorta(fecha)} al ${fechaCorta(nueva)}.`, hacer: async () => void (await apiFrases.mover(f.id, fecha)) })}>
          <Icono nombre="calendario" tam={15} /> Mover
        </button>
      </div>
      <div className="fd-form">
        <strong className="chico">Intercambiar con la frase de otra fecha</strong>
        <input type="date" value={otra} onChange={(e) => setOtra(e.target.value)} aria-label="Fecha con la que se intercambia" />
        {otraFrase?.frase ? (
          <p className="suave chico">
            Ese día tiene: «{recortar(otraFrase.frase.texto, 80)}» — {otraFrase.frase.autor}
            {otraFrase.frase.cerrada && " ⚠ ya está en la cola o ya salió: no se puede intercambiar."}
          </p>
        ) : otra && otra !== fecha ? (
          <p className="suave chico">Ese día no tiene frase: usá «Mover».</p>
        ) : null}
        <button type="button" className="boton" disabled={ocupado || !puedeInter} onClick={() => correr(async () => (await apiFrases.intercambiar(f.id, otraFrase!.frase!.id)).mensaje, otra, { texto: `Intercambiadas ${fechaCorta(fecha)} y ${fechaCorta(otra)}.`, hacer: async () => void (await apiFrases.intercambiar(f.id, otraFrase!.frase!.id)) })}>
          <Icono nombre="regenerar" tam={15} /> Intercambiar
        </button>
      </div>
    </div>
  );
}

function FotoFondo({ f, ocupado, correr }: { f: Frase; ocupado: boolean; correr: (a: () => Promise<string | void>) => Promise<void> }) {
  return (
    <div className="fd-form">
      <p className="suave chico">Foto del banco de imágenes de WordPress (las etiquetadas «cuadrado» primero). Sin elección, va la foto por defecto. La foto elegida va a la imagen compuesta, al mail y a las redes.</p>
      <ElegirFoto
        actual={f.imagen_url}
        ocupado={ocupado}
        textoQuitar="Volver a la foto por defecto"
        onElegir={(url) => correr(async () => (url ? ((await apiFrases.editar(f.id, { imagen_url: url })), "Foto elegida.") : ((await apiFrases.editar(f.id, { quitar_imagen: true })), "Vuelve a la foto por defecto.")))}
      />
    </div>
  );
}

/** (2/11 tarde) Elegir una foto: buscar en el banco de WordPress o pegar una URL. `actual` es la elegida hoy; onElegir(null) = sacarla.
 *  Lo usan los aprobadores (FotoFondo, guarda en la frase) y los creadores (SolicitarCambio, la proponen). */
function ElegirFoto({ actual, ocupado, textoQuitar, onElegir }: { actual: string | null; ocupado: boolean; textoQuitar: string; onElegir: (url: string | null) => void }) {
  const [q, setQ] = useState("");
  const [fotos, setFotos] = useState<FotoBanco[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [url, setUrl] = useState("");
  async function buscar() {
    setBuscando(true);
    try {
      setFotos(await apiChat.banco(q.trim(), "cuadrado"));
    } catch {
      setFotos([]);
    } finally {
      setBuscando(false);
    }
  }
  return (
    <>
      {actual && (
        <div className="fd-foto-actual">
          <img src={actual} alt="Foto elegida" />
          <button type="button" className="boton chico" onClick={() => onElegir(null)} disabled={ocupado}>
            {textoQuitar}
          </button>
        </div>
      )}
      <div className="campo-con-boton">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en el banco: ej. amanecer montaña calma" onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), buscar())} aria-label="Buscar en el banco" />
        <button type="button" className="boton" onClick={buscar} disabled={buscando}>
          <Icono nombre="buscar" tam={15} /> {buscando ? "Buscando…" : "Buscar"}
        </button>
      </div>
      {fotos && fotos.length === 0 && !buscando && <p className="suave chico">El banco no devolvió nada para esa búsqueda.</p>}
      {fotos && fotos.length > 0 && (
        <div className="pieza-fotos">
          {fotos.map((x) => (
            <button key={x.id} type="button" className={"pieza-foto" + (actual === x.url ? " elegida" : "")} onClick={() => onElegir(x.url)} disabled={ocupado} title={x.titulo || `#${x.id}`}>
              <img src={x.miniatura} alt={x.titulo || ""} loading="lazy" />
              <span className="chico">{(x.titulo || `#${x.id}`).slice(0, 28)}</span>
            </button>
          ))}
        </div>
      )}
      <div className="campo-con-boton">
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="…o pegá la URL de una imagen que ya está en internet" aria-label="URL de la foto" />
        <button type="button" className="boton" disabled={ocupado || !url.trim()} onClick={() => (onElegir(url.trim()), setUrl(""))}>
          Usar esa URL
        </button>
      </div>
    </>
  );
}

/** Buscador entre las validadas sin día (frases_ui._buscador). */
function Buscador({ excluir, textoBoton, ocupado, onElegir }: { excluir?: string; textoBoton: string; ocupado: boolean; onElegir: (f: Frase) => void }) {
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<Frase[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => {
    const t = window.setTimeout(() => apiFrases.backlog(q).then((b) => setLista(b.sin_dia.filter((x) => x.id !== excluir).slice(0, 30))).catch(() => setLista([])), 200);
    return () => window.clearTimeout(t);
  }, [q, excluir]);
  const elegida = lista?.find((x) => x.id === sel) ?? null;
  return (
    <div className="fd-form">
      <label className="buscar">
        <Icono nombre="buscar" tam={16} />
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar entre las validadas sin día (texto o autor)" aria-label="Buscar frase" />
      </label>
      {lista && lista.length === 0 && <p className="suave chico">No hay frases sin día que coincidan.</p>}
      {lista && lista.length > 0 && (
        <ul className="fd-lista fd-elegir" role="listbox" aria-label="Frases">
          {lista.map((x) => (
            <li key={x.id} role="option" aria-selected={sel === x.id} className={"fd-item" + (sel === x.id ? " elegida" : "")} onClick={() => setSel(x.id)}>
              <span className="fd-texto">{recortar(x.texto, 120)}</span>
              <span className="suave chico">{x.autor}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="acciones">
        <button type="button" className="boton primario" disabled={ocupado || !elegida} onClick={() => elegida && onElegir(elegida)}>
          <Icono nombre="check" tam={15} /> {textoBoton}
        </button>
      </div>
    </div>
  );
}

// ---------------- Repartir y agregar ----------------
function Repartir({ hoy, sinDia, onCerrar, onHecho }: { hoy: string; sinDia: number; onCerrar: () => void; onHecho: (msg: string) => void }) {
  const { avisar } = useToast();
  const [modo, setModo] = useState<"orden" | "azar">("orden");
  const [desde, setDesde] = useState(() => iso(new Date(new Date(hoy + "T12:00:00").getTime() + 86400000)));
  const [ocupado, setOcupado] = useState(false);
  async function ir() {
    setOcupado(true);
    try {
      onHecho((await apiFrases.repartir(modo, desde)).mensaje);
    } catch (e) {
      avisar(mensajeDe(e), "error");
      setOcupado(false);
    }
  }
  return (
    <Modal titulo="Repartir en el año" onCerrar={onCerrar} ancho={520}>
      <p className="suave chico">
        Asigna un día a cada frase candidata a partir de la fecha elegida: primero las nunca publicadas ({sinDia} validadas sin día); cuando se acaban, siguen las ya publicadas de la más antigua a la más reciente. Las fechas que ya tienen frase no se tocan.
      </p>
      <div className="fd-form">
        <label>
          Orden
          <select value={modo} onChange={(e) => setModo(e.target.value as "orden" | "azar")}>
            <option value="orden">En el orden del Sheet</option>
            <option value="azar">Al azar (sin repetir autor dos días seguidos)</option>
          </select>
        </label>
        <label>
          A partir del
          <input type="date" value={desde} min={hoy} onChange={(e) => setDesde(e.target.value)} />
        </label>
      </div>
      <div className="acciones" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="boton" onClick={onCerrar} disabled={ocupado}>
          Cancelar
        </button>
        <button type="button" className="boton primario" onClick={ir} disabled={ocupado || !desde}>
          <Icono nombre="calendario" tam={15} /> {ocupado ? "Repartiendo…" : "Repartir"}
        </button>
      </div>
    </Modal>
  );
}

function NuevaFrase({ onCerrar, onHecha }: { onCerrar: () => void; onHecha: () => void }) {
  const { avisar } = useToast();
  const [texto, setTexto] = useState("");
  const [autor, setAutor] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function agregar() {
    setOcupado(true);
    try {
      await apiFrases.crear(texto.trim(), autor.trim());
      onHecha();
    } catch (e) {
      avisar(mensajeDe(e), "error");
      setOcupado(false);
    }
  }
  return (
    <Modal titulo="Agregar una frase" onCerrar={onCerrar} ancho={520}>
      <p className="suave chico">Queda validada y sin día; después la asignás desde el backlog o un día libre.</p>
      <div className="fd-form">
        <label>
          Frase
          <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={4} />
        </label>
        <label>
          Autor
          <input value={autor} onChange={(e) => setAutor(e.target.value)} placeholder="Brother David" />
        </label>
      </div>
      <div className="acciones" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="boton" onClick={onCerrar} disabled={ocupado}>
          Cancelar
        </button>
        <button type="button" className="boton primario" onClick={agregar} disabled={ocupado || !texto.trim()}>
          <Icono nombre="mas" tam={15} /> Agregar
        </button>
      </div>
    </Modal>
  );
}


/** (26/10, reunión: la Frase del día vuelve por mail con el disparador de Perfit) Estado del canal mail y la prueba al equipo.
 * Lo ven aprobadores y admins; el botón de prueba es de admins. La hora de inicio y la lista de prueba se cargan en Configuración. */
function MailPanel({ admin, aprueba, hoy, onVerMail }: { admin: boolean; aprueba: boolean; hoy?: string; onVerMail: (fecha: string) => void }) {
  const { avisar } = useToast();
  const [est, setEst] = useState<MailEstado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [probando, setProbando] = useState(false);
  const [ultima, setUltima] = useState<{ aviso: string; modo: string; resultados: { email: string; ok: boolean; aviso: string }[] } | null>(null);
  const cargar = useCallback(() => {
    apiFrases
      .mailEstado()
      .then((e) => {
        setEst(e);
        setError(null);
      })
      .catch((e) => setError(e instanceof ErrorApi ? e.message : "No pude leer el estado del mail."));
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  async function probar() {
    if (!est?.lista_prueba.length) {
      avisar("Primero cargá los mails de prueba en Administración → Configuración → Frase del día.", "error");
      return;
    }
    setProbando(true);
    try {
      const r = await apiFrases.mailPrueba(hoy);
      setUltima({ aviso: r.aviso, modo: r.modo, resultados: r.resultados });
      avisar(r.ok ? r.aviso : "No se mandó: " + r.aviso, r.ok ? "info" : "error");
      cargar();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude mandar la prueba.", "error");
    } finally {
      setProbando(false);
    }
  }

  const modoTxt = est ? { apagado: "apagado", simulado: "simulado (registra, no manda)", real: "real" }[est.modo] : "";
  const dias = est ? Object.entries(est.envios) : [];
  return (
    <details className="fd-panel tarjeta" open={!!est && (est.canal_prendido || est.modo === "real")}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre="sobre" tam={17} />
        <span>
          Frase por mail (Perfit)
          {est && (
            <span className="suave chico">
              {" "}
              · {est.canal_prendido ? "canal prendido" : "canal apagado"} · modo {modoTxt}
              {est.faltan.length > 0 && ` · faltan ${est.faltan.length} variables`}
            </span>
          )}
        </span>
      </summary>
      <div className="fd-panel-cuerpo fd-mail">
        {error && (
          <div className="aviso error chico">
            <Icono nombre="alerta" tam={16} /> {error}
          </div>
        )}
        {est && (
          <>
            <p className="suave chico">
              Perfit manda hasta {est.limite_por_hora} mails por hora con su disparador personalizado, así que el envío arranca el día anterior a las {est.inicio} y se completa a la mañana. La automation de Perfit (clave <code>{est.trigger_key}</code>) arma el mail con: {est.contexto_plantilla.join(", ")}.
            </p>
            {est.faltan.length > 0 && (
              <div className="aviso chico">
                <Icono nombre="alerta" tam={16} /> Faltan variables en el servidor: {est.faltan.join(", ")}. Hasta que estén, el modo real no manda nada.
              </div>
            )}
            {est.error && (
              <div className="aviso error chico">
                <Icono nombre="alerta" tam={16} /> Perfit: {est.error}
              </div>
            )}
            {est.lista && (
              <p className="chico">
                Lista de Perfit: <strong>{est.lista.nombre}</strong> · {est.lista.activos ?? "?"} contactos activos de {est.lista.total ?? "?"}.
              </p>
            )}
            <ul className="fd-mail-dias">
              {dias.map(([fecha, d]) => (
                <li key={fecha}>
                  <strong>{d.fecha_texto}</strong>:{" "}
                  {!d.frase ? (
                    <span className="suave">sin frase asignada</span>
                  ) : !d.pieza ? (
                    <span className="suave">«{recortar(d.frase.texto, 60)}» · {est.canal_prendido ? "todavía no está en la cola" : "el canal mail está apagado"}</span>
                  ) : (
                    <span>
                      «{recortar(d.frase.texto, 60)}» · {d.estado}
                      {d.conteo && d.conteo.total ? ` · ${d.conteo.enviado ?? 0} enviados, ${d.conteo.pendiente ?? 0} pendientes, ${d.conteo.error ?? 0} con error` : ""}
                      {d.arranca && d.estado === "pendiente" ? ` · arranca ${fechaCorta(d.arranca.slice(0, 10))} ${d.arranca.slice(11, 16)}` : ""}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            <div className="fd-mail-prueba">
              <span className="chico">
                Mails de prueba: {est.lista_prueba.length ? est.lista_prueba.join(", ") : <span className="suave">ninguno cargado todavía</span>}
                {admin && (
                  <>
                    {" "}
                    · <Link to="/administracion/configuracion">cambiar</Link>
                  </>
                )}
              </span>
              {hoy && (
                <button type="button" className="boton chico" onClick={() => onVerMail(hoy)} title="El mail de hoy, armado con la plantilla (reproducción de la de Perfit)">
                  <Icono nombre="ojo" tam={15} /> Ver el mail de hoy
                </button>
              )}
              {aprueba && (
                <button type="button" className="boton chico" onClick={probar} disabled={probando || est.modo === "apagado"} title={est.modo === "apagado" ? "PUBLICAR_MAIL está apagado" : "Manda la frase de hoy a los mails de prueba, ahora"}>
                  <Icono nombre="sobre" tam={15} /> {probando ? "Mandando…" : "Probar el mail de hoy"}
                </button>
              )}
            </div>
            {ultima && (
              <div className="chico">
                <strong>{ultima.aviso}</strong>
                <ul className="fd-mail-resultados">
                  {ultima.resultados.map((r) => (
                    <li key={r.email} className={r.ok ? "" : "rojo"}>
                      {r.email}: {r.aviso}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {est.pruebas.length > 0 && (
              <p className="suave chico">
                Últimas pruebas: {est.pruebas.slice(0, 5).map((p) => `${p.email} (${p.estado}${p.enviado_en ? ", " + fechaCorta(p.enviado_en.slice(0, 10)) : ""})`).join(" · ")}
              </p>
            )}
          </>
        )}
      </div>
    </details>
  );
}


// ---------------- (2/11) Ver el mail de un día ----------------
function VerMail({ fecha, onCerrar, onCambiarFoto }: { fecha: string; onCerrar: () => void; onCambiarFoto?: () => void }) {
  const [m, setM] = useState<MailPrevia | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setM(null);
    setError(null);
    apiFrases
      .mailPrevia(fecha)
      .then(setM)
      .catch((e) => setError(mensajeDe(e)));
  }, [fecha]);
  return (
    <Modal titulo={`El mail del ${fechaLarga(fecha)}`} onCerrar={onCerrar} ancho={760}>
      {error && <div className="aviso error">{error}</div>}
      {!m && !error && <p className="suave">Armando el mail…</p>}
      {m && (
        <div className="fd-mail-previa">
          <p className="chico">
            <strong>Asunto:</strong> {m.asunto}
            <span className="suave"> · foto: {m.imagen_de}</span>
          </p>
          <iframe title="Vista previa del mail" srcDoc={m.html} sandbox="" />
          {m.frase && (
            <div className="acciones">
              <button type="button" className="boton chico" onClick={onCambiarFoto} title={onCambiarFoto ? "Elegir otra foto de fondo para esta frase (banco de WordPress o URL)" : "Abrí el día en el calendario y pedí otra foto"}>
                <Icono nombre="imagen" tam={15} /> {onCambiarFoto ? "Cambiar la foto de fondo" : "Pedir otra foto de fondo"}
              </button>
            </div>
          )}
          <p className="suave chico">
            <Icono nombre="info" tam={14} /> {m.aviso}
          </p>
        </div>
      )}
    </Modal>
  );
}

/** (2/11 tarde) Prototipo de la reunión: la frase en el grupo de WhatsApp, dibujada como un chat. Todavía no se manda (sin endpoint). */
function VerWhatsapp({ fecha, onCerrar }: { fecha: string; onCerrar: () => void }) {
  const [m, setM] = useState<WhatsappPrevia | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setM(null);
    setError(null);
    apiFrases
      .whatsappPrevia(fecha)
      .then(setM)
      .catch((e) => setError(mensajeDe(e)));
  }, [fecha]);
  const hora = "07:00";
  return (
    <Modal titulo={`El WhatsApp del ${fechaLarga(fecha)}`} onCerrar={onCerrar} ancho={520}>
      {error && <div className="aviso error">{error}</div>}
      {!m && !error && <p className="suave">Armando el mensaje…</p>}
      {m && (
        <div className="fd-wa">
          <p className="chico">
            <strong>Grupo:</strong> {m.grupo}
            <span className="suave"> · modo {m.modo}{m.canal_prendido ? " · canal prendido" : " · canal apagado en Configuración"}</span>
            {m.pieza && <span className="suave"> · pieza {m.pieza.estado}</span>}
          </p>
          <div className="wa-chat" aria-label="Así se vería en WhatsApp">
            <div className="wa-cab">
              <span className="wa-avatar">VA</span>
              <span>
                <strong>{m.grupo}</strong>
                <span className="wa-sub">Vivir Agradecidos, vos y la comunidad</span>
              </span>
            </div>
            <div className="wa-fondo">
              <div className="wa-dia">{m.fecha_texto}</div>
              <div className="wa-burbuja">
                <div className="wa-quien">Vivir Agradecidos</div>
                {m.imagen ? <img src={m.imagen} alt="La frase sobre la foto" /> : <div className="wa-sin-imagen suave chico">Sin imagen ({m.imagen_de})</div>}
                <div className="wa-texto">{m.texto}</div>
                <div className="wa-hora">{hora} ✓✓</div>
              </div>
            </div>
          </div>
          <p className="suave chico">
            <Icono nombre="info" tam={14} /> {m.aviso}
          </p>
        </div>
      )}
    </Modal>
  );
}

// ---------------- (2/11) Solicitudes de cambio: los creadores piden, los aprobadores resuelven ----------------
function SolicitarCambio({ fecha, actual, onHecho }: { fecha: string; actual: Frase | null; onHecho: () => void }) {
  const { avisar } = useToast();
  const [modo, setModo] = useState<"existente" | "nueva" | "foto">("existente");
  const [texto, setTexto] = useState("");
  const [autor, setAutor] = useState("Br. David");
  const [nota, setNota] = useState("");
  const [foto, setFoto] = useState<string | null>(null); // (2/11 tarde) foto de fondo propuesta, sola o junto con la frase
  const [ocupado, setOcupado] = useState(false);
  const [hecha, setHecha] = useState<string | null>(null);

  async function mandar(frase_id: string | null) {
    setOcupado(true);
    try {
      const soloFoto = modo === "foto";
      const r = await apiFrases.solicitar({ fecha, frase_id, texto: frase_id || soloFoto ? null : texto, autor: frase_id || soloFoto ? null : autor, nota, imagen_url: foto });
      setHecha(r.mensaje);
      avisar(r.mensaje);
      onHecho();
    } catch (e) {
      avisar(mensajeDe(e), "error");
    } finally {
      setOcupado(false);
    }
  }

  if (hecha)
    return (
      <div className="aviso chico">
        <Icono nombre="check" tam={16} /> {hecha} Lo seguís en el panel «Solicitudes».
      </div>
    );
  return (
    <div className="fd-form fd-solicitar">
      {actual && modo !== "foto" && <p className="suave chico">Hoy ese día tiene «{recortar(actual.texto, 90)}». Si aceptan tu pedido, la que elijas toma su lugar (la que estaba vuelve al backlog o se intercambia).</p>}
      {actual && modo === "foto" && <p className="suave chico">La frase queda («{recortar(actual.texto, 90)}»); lo que cambia es la foto de fondo con la que sale por mail y redes.</p>}
      <div className="solapas chico" role="tablist">
        <button role="tab" aria-selected={modo === "existente"} className={"solapa" + (modo === "existente" ? " activa" : "")} onClick={() => setModo("existente")}>
          Una frase que ya está cargada
        </button>
        <button role="tab" aria-selected={modo === "nueva"} className={"solapa" + (modo === "nueva" ? " activa" : "")} onClick={() => setModo("nueva")}>
          Una frase nueva
        </button>
        {actual && (
          <button role="tab" aria-selected={modo === "foto"} className={"solapa" + (modo === "foto" ? " activa" : "")} onClick={() => setModo("foto")}>
            Solo otra foto de fondo
          </button>
        )}
      </div>
      <label className="campo">
        <span>Comentario para quien aprueba <span className="suave">(opcional)</span></span>
        <input value={nota} onChange={(e) => setNota(e.target.value)} placeholder="Por qué este día, por ejemplo: es el Día de la Madre" maxLength={300} />
      </label>
      {modo !== "foto" && (
        <details className="fd-solicitar-foto" open={!!foto}>
          <summary className="chico">
            <Icono nombre="chevron" tam={14} /> Foto de fondo <span className="suave">(opcional{foto ? ", elegida" : ": si no, va la de la frase o la por defecto"})</span>
          </summary>
          <ElegirFoto actual={foto} ocupado={ocupado} textoQuitar="Sacar: que vaya la foto que corresponda" onElegir={setFoto} />
        </details>
      )}
      {modo === "foto" && actual && (
        <>
          <ElegirFoto actual={foto} ocupado={ocupado} textoQuitar="Sacar esta foto" onElegir={setFoto} />
          {foto && (
            <div className="fd-foto-previa">
              <img src={apiFrases.previaUrl(actual.id, "", foto)} alt="Así saldría con esa foto" />
              <span className="suave chico">Así saldría con esa foto.</span>
            </div>
          )}
          <div className="acciones">
            <button type="button" className="boton primario" disabled={ocupado || !foto} onClick={() => mandar(null)}>
              <Icono nombre="enviar" tam={15} /> Pedir esta foto para este día
            </button>
          </div>
        </>
      )}
      {modo === "existente" ? (
        <Buscador excluir={actual?.id} textoBoton="Pedir que salga este día" ocupado={ocupado} onElegir={(fr) => mandar(fr.id)} />
      ) : modo === "nueva" ? (
        <>
          <label className="campo">
            <span>La frase</span>
            <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={3} placeholder="Escribí la frase tal cual saldría" />
          </label>
          <label className="campo">
            <span>Autor</span>
            <input value={autor} onChange={(e) => setAutor(e.target.value)} />
          </label>
          <div className="acciones">
            <button type="button" className="boton primario" disabled={ocupado || !texto.trim()} onClick={() => mandar(null)}>
              <Icono nombre="enviar" tam={15} /> Pedir que salga este día
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

/** (2/11 tarde) La foto propuesta en una solicitud, compuesta sobre la frase cuando hay una con id (la pedida o la del día). */
function FotoDeSolicitud({ s }: { s: Solicitud }) {
  if (!s.imagen_url) return null;
  const fid = s.frase?.id ?? (s.solo_foto ? s.actual?.id : undefined);
  const src = fid ? apiFrases.previaUrl(fid, "", s.imagen_url) : s.imagen_url;
  return (
    <a className="fd-solicitud-foto" href={s.imagen_url} target="_blank" rel="noreferrer" title="La foto de fondo propuesta (abre la original)">
      <img src={src} alt="Foto de fondo propuesta" loading="lazy" />
      <span className="suave chico">{fid ? "así saldría con la foto propuesta" : "foto de fondo propuesta"}</span>
    </a>
  );
}

function SolicitudesPanel({ aprueba, version, onCambio, onVerDia }: { aprueba: boolean; version: number; onCambio: () => void; onVerDia: (fecha: string) => void }) {
  const { avisar } = useToast();
  const [datos, setDatos] = useState<Solicitudes | null>(null);
  const [respuesta, setRespuesta] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState<string | null>(null);
  const cargar = useCallback(() => {
    apiFrases.solicitudes().then(setDatos).catch(() => setDatos({ aprueba, pendientes: [], resueltas: [] }));
  }, [aprueba]);
  useEffect(cargar, [cargar, version]);

  async function resolver(s: Solicitud, que: "aceptar" | "rechazar" | "retirar") {
    setOcupado(s.id);
    try {
      const r = que === "aceptar" ? await apiFrases.aceptarSolicitud(s.id, respuesta[s.id]) : que === "rechazar" ? await apiFrases.rechazarSolicitud(s.id, respuesta[s.id]) : await apiFrases.retirarSolicitud(s.id);
      avisar(r.mensaje);
      cargar();
      onCambio();
    } catch (e) {
      avisar(mensajeDe(e), "error");
    } finally {
      setOcupado(null);
    }
  }

  const n = datos?.pendientes.length ?? 0;
  if (datos && !n && !datos.resueltas.length && aprueba) return null;
  return (
    <details className="fd-panel tarjeta" open={n > 0}>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre="pregunta" tam={17} />
        <span>
          {aprueba ? "Solicitudes del equipo" : "Mis solicitudes"}
          {datos && (
            <span className="suave chico">
              {" "}
              · {n ? `${n} pendiente${n === 1 ? "" : "s"}` : "nada pendiente"}
            </span>
          )}
        </span>
      </summary>
      <div className="fd-panel-cuerpo">
        {!datos && <p className="suave chico">Cargando…</p>}
        {datos && !n && <p className="suave chico">{aprueba ? "No hay pedidos de cambio pendientes." : "No tenés pedidos pendientes. Abrí un día del calendario para pedir que salga otra frase."}</p>}
        <ul className="fd-solicitudes">
          {datos?.pendientes.map((s) => (
            <li key={s.id} className="fd-solicitud">
              <div className="fd-solicitud-cab chico">
                <button type="button" className="enlace" onClick={() => onVerDia(s.fecha)}>
                  <strong>{s.fecha_texto}</strong>
                </button>
                {aprueba && <span className="suave"> · pide {s.usuario}</span>}
                <span className="suave"> · {fechaCorta(s.creado.slice(0, 10))}</span>
                {s.pasado && <span className="rojo"> · ese día ya pasó</span>}
              </div>
              <div className="fd-solicitud-cambio chico">
                {s.solo_foto ? (
                  <span>
                    <span className="suave">Otra foto de fondo para:</span> «{recortar(s.actual?.texto || "", 160)}»{s.actual?.autor ? ` — ${s.actual.autor}` : ""}
                    {!s.actual && <span className="rojo"> (ese día ya no tiene frase)</span>}
                  </span>
                ) : (
                  <>
                    <span>
                      <span className="suave">Que salga:</span> «{recortar(s.frase?.texto || s.texto || "", 160)}» — {s.frase?.autor || s.autor || "(sin autor)"}
                      {!s.frase && <span className="chip chico"> nueva</span>}
                      {s.frase?.fecha && s.frase.fecha !== s.fecha && <span className="suave"> (hoy está el {fechaCorta(s.frase.fecha)})</span>}
                      {s.imagen_url && <span className="suave"> · con una foto de fondo propuesta</span>}
                    </span>
                    <span className="suave">{s.actual ? `En lugar de: «${recortar(s.actual.texto, 100)}»` : "El día está libre."}</span>
                  </>
                )}
                <FotoDeSolicitud s={s} />
                {s.nota && <span className="fd-nota">“{s.nota}”</span>}
              </div>
              {aprueba ? (
                <div className="fd-solicitud-acciones">
                  <input value={respuesta[s.id] ?? ""} onChange={(e) => setRespuesta({ ...respuesta, [s.id]: e.target.value })} placeholder="Respuesta (opcional; al rechazar, decí por qué)" maxLength={300} />
                  <button type="button" className="boton primario chico" disabled={ocupado === s.id || s.pasado} onClick={() => resolver(s, "aceptar")}>
                    <Icono nombre="check" tam={14} /> Aceptar
                  </button>
                  <button type="button" className="boton chico" disabled={ocupado === s.id} onClick={() => resolver(s, "rechazar")}>
                    <Icono nombre="cruz" tam={14} /> Rechazar
                  </button>
                </div>
              ) : (
                <div className="fd-solicitud-acciones">
                  <span className="suave chico">Esperando a quien aprueba.</span>
                  <button type="button" className="boton sutil chico" disabled={ocupado === s.id} onClick={() => resolver(s, "retirar")}>
                    <Icono nombre="tacho" tam={14} /> Retirar
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
        {datos && datos.resueltas.length > 0 && (
          <details className="fd-resueltas">
            <summary className="suave chico">Últimas resueltas ({datos.resueltas.length})</summary>
            <ul className="fd-solicitudes">
              {datos.resueltas.map((s) => (
                <li key={s.id} className={"fd-solicitud " + s.estado}>
                  <div className="chico">
                    <strong>{s.fecha_texto}</strong>
                    {aprueba && <span className="suave"> · pidió {s.usuario}</span>} · {s.solo_foto ? "otra foto para " : ""}«{recortar(s.frase?.texto || s.texto || s.actual?.texto || "", 90)}»{s.imagen_url && !s.solo_foto ? " (con foto)" : ""} ·{" "}
                    <span className={s.estado === "aceptada" ? "verde" : s.estado === "rechazada" ? "rojo" : "suave"}>{s.estado}</span>
                    {s.resuelta_por && s.estado !== "retirada" && <span className="suave"> por {s.resuelta_por}</span>}
                    {s.respuesta && <span className="fd-nota"> “{s.respuesta}”</span>}
                  </div>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </details>
  );
}
