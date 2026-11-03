// Solicitudes de cambio (2/11): los creadores piden («Pedir un cambio» en el día), los aprobadores resuelven en el panel.
import { useCallback, useEffect, useState } from "react";
import { type Frase, type Solicitud, type Solicitudes, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { useToast } from "../../../componentes/Toasts";
import { fechaCorta, mensajeDe, recortar } from "../comun";
import { Buscador } from "./Buscador";
import { ElegirFoto } from "./ElegirFoto";

// ---------------- (2/11) Solicitudes de cambio: los creadores piden, los aprobadores resuelven ----------------
export function SolicitarCambio({ fecha, actual, onHecho }: { fecha: string; actual: Frase | null; onHecho: () => void }) {
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
export function FotoDeSolicitud({ s }: { s: Solicitud }) {
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

export function SolicitudesPanel({ aprueba, version, onCambio, onVerDia }: { aprueba: boolean; version: number; onCambio: () => void; onVerDia: (fecha: string) => void }) {
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
