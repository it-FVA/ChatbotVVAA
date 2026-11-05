// La tarjeta «Mañana»: qué sale mañana y por dónde, con los interruptores y la vista previa por canal.
import { horaArgentina } from "../../../util/fechas";
import { type CanalManana, type Resumen, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { CANAL_CORTO, recortar } from "../comun";
import type { Solapa } from "../solapas";

// ---------------- (2/11) Ver el mail de un día ----------------
/** (2/11, Franco) La tarjeta «Mañana»: qué sale mañana y por dónde. Para aprobadores con interruptores y acciones; los creadores
 *  ven lo mismo sin poder tocarlo (piden cambios desde el día). */
export function MananaCard({ resumen, version = 0, aprueba, ocupado, onActiva, onCanales, onEncolar, onFrenar, onVerDia, onVerMail, onVerWa, onProbarMail, onDetallesMail }: {
  resumen: Resumen;
  /** (3/11, Julián) sube con cada cambio: así la miniatura se vuelve a pedir después de cambiar la foto o el diseño, sin refrescar la página. */
  version?: number;
  aprueba: boolean;
  ocupado: boolean;
  onActiva: () => void;
  onCanales: (canales: string[]) => void;
  onEncolar: () => void;
  onFrenar: () => void;
  onVerDia: (fecha: string, solapa?: Solapa) => void;
  onVerMail: (fecha: string) => void;
  onVerWa: (fecha: string) => void;
  onProbarMail: () => void;
  onDetallesMail: () => void;
}) {
  const m = resumen.manana;
  if (!m) return null;
  const f = m.frase;
  const filas = m.canales ?? [];
  const prendidos = filas.filter((x) => x.prendido).map((x) => x.canal);
  const hora = resumen.hora ?? "07:00";
  const titulo = `Mañana, ${m.dia ? m.dia + " " : ""}${m.fecha_texto}`;

  function estadoDe(x: CanalManana): { texto: string; clase: string } {
    if (!x.prendido) return { texto: "apagado", clase: "suave" };
    if (x.modo === "apagado") return { texto: "el canal está apagado", clase: "suave" };
    const p = x.pieza;
    if (p?.estado === "pendiente") return { texto: x.canal === "mail" ? `programada · arranca ${horaArgentina(p.fecha_programada)}` : `programada · sale ${horaArgentina(p.fecha_programada)}`, clase: "verde" };
    if (p?.estado === "enviando") return { texto: "enviándose", clase: "verde" };
    if (p?.estado === "publicada") return { texto: "ya salió", clase: "verde" };
    if (p?.estado === "simulada") return { texto: "prueba (no salió)", clase: "suave" };
    if (p?.estado === "cancelada") return { texto: "cancelada", clase: "rojo" };
    if (p?.estado === "error") return { texto: "falló: ver Aprobación → Programadas", clase: "rojo" };
    if (!f) return { texto: "sin frase", clase: "suave" };
    return resumen.activa ? { texto: `se programa sola (sale ${hora})`, clase: "suave" } : { texto: "se programa al prender la Frase del día", clase: "suave" };
  }

  return (
    <section className="tarjeta fd-manana-card" data-ayuda="frase-del-dia.manana" aria-label="Mañana">
      <div className="fd-manana-cab">
        <h2>{titulo}</h2>
        <div className="fd-manana-estado">
          {aprueba && resumen.admin ? (
            <label className="interruptor" title={resumen.activa ? "Prendida: cada día la frase de ese día se encola por los canales prendidos" : "Apagada: el calendario se arma igual pero no sale nada"}>
              <input type="checkbox" checked={resumen.activa} onChange={onActiva} disabled={ocupado} />
              <span>
                Frase del día <strong>{resumen.activa ? "prendida" : "apagada"}</strong>
              </span>
            </label>
          ) : (
            <span className={"chip " + (resumen.activa ? "verde" : "")}>Frase del día {resumen.activa ? "prendida" : "apagada"}</span>
          )}
          <span className="suave chico">· sale a las {hora}</span>
        </div>
      </div>
      {/* (2/11 noche, Franco) el interruptor general y los de cada canal son independientes: se pueden dejar elegidos los canales con todo apagado */}
      <p className="suave chico fd-manana-nota">
        {resumen.activa
          ? "Prendida: cada mañana la frase del día sale por los canales marcados abajo."
          : "Apagada: no sale nada por ningún canal. Podés dejar marcados los canales que quieras y prenderla cuando decidas; recién ahí se encola."}
      </p>

      {f ? (
        <div className="fd-manana-frase">
          <button type="button" className="fd-manana-img" onClick={() => onVerDia(m.fecha)} title="Ver la imagen grande y el detalle del día">
            <img src={apiFrases.previaUrl(f.id, `${version}-${f.imagen_url || ""}`)} alt="Así saldría la imagen de mañana" />
          </button>
          <div className="fd-manana-texto">
            <blockquote className="fd-cita chico">{recortar(f.texto, 260)}</blockquote>
            <p className="chico suave">
              <strong>{f.autor || "(sin autor)"}</strong> · {f.estado === "saltada" ? "salteada: no sale nada" : f.estado_texto}
              {f.repetida ? ` · ya salió ${f.veces_publicada} ${f.veces_publicada === 1 ? "vez" : "veces"}` : ""}
            </p>
            <div className="fd-manana-acciones">
              <button type="button" className="boton chico" onClick={() => onVerDia(m.fecha)}>
                <Icono nombre="imagen" tam={14} /> Ver la imagen
              </button>
              {aprueba && (
                <>
                  <button type="button" className="boton chico" onClick={() => onVerDia(m.fecha, "cambiar")}>
                    <Icono nombre="regenerar" tam={14} /> Cambiar la frase
                  </button>
                  <button type="button" className="boton chico" onClick={() => onVerDia(m.fecha, "foto")}>
                    <Icono nombre="imagen" tam={14} /> Cambiar la foto
                  </button>
                  {m.en_cola ? (
                    <button type="button" className="boton chico" onClick={onFrenar} disabled={ocupado} title="Cancela las piezas de mañana ya programadas; la frase queda en el día">
                      <Icono nombre="cruz" tam={14} /> Frenar mañana
                    </button>
                  ) : (
                    <button type="button" className="boton primario chico" onClick={onEncolar} disabled={ocupado || !resumen.activa || !prendidos.length} title={resumen.activa ? "Programa la frase de mañana por los canales prendidos" : "Primero prendé la Frase del día"}>
                      <Icono nombre="enviar" tam={14} /> Encolar mañana
                    </button>
                  )}
                </>
              )}
              {!aprueba && (
                <button type="button" className="boton chico" onClick={() => onVerDia(m.fecha)}>
                  <Icono nombre="pregunta" tam={14} /> Pedir un cambio
                </button>
              )}
            </div>
          </div>
        </div>
      ) : (
        <p className="aviso chico">
          <Icono nombre="alerta" tam={16} /> Mañana no tiene frase asignada. {aprueba ? "Abrí el día en el calendario y asigná una, o Repartí en el año." : "Quien aprueba la asigna."}
        </p>
      )}

      <table className="fd-canales-tabla chico">
        <thead>
          <tr>
            <th>Canal</th>
            <th>Sale por acá</th>
            <th>Mañana</th>
            <th>Vista previa</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((x) => {
            const e = estadoDe(x);
            const corto = CANAL_CORTO[x.canal] ?? x.nombre;
            return (
              <tr key={x.canal} className={x.prendido ? "" : "apagado"}>
                <td>
                  <span title={x.nombre}>{corto}</span>
                  {x.modo !== "real" && <span className="chip chico suave" title="Cómo está el canal: en prueba no sale nada de verdad">{x.modo === "simulado" ? "prueba" : x.modo}</span>}
                </td>
                <td>
                  {aprueba ? (
                    <label className="interruptor chico" title={x.prendido ? "Prendido: sale por acá cada día" : "Apagado: no sale por acá"}>
                      <input type="checkbox" checked={x.prendido} disabled={ocupado} onChange={() => onCanales(x.prendido ? prendidos.filter((c) => c !== x.canal) : [...prendidos, x.canal])} />
                      <span className="sr-solo">{x.prendido ? "prendido" : "apagado"}</span>
                    </label>
                  ) : (
                    <span className={x.prendido ? "verde" : "suave"}>{x.prendido ? "sí" : "no"}</span>
                  )}
                </td>
                <td className={e.clase}>{e.texto}</td>
                <td>
                  {f && x.canal === "mail" && (
                    <>
                      <button type="button" className="boton sutil chico" onClick={() => onVerMail(m.fecha)}>
                        <Icono nombre="sobre" tam={13} /> Ver
                      </button>
                      {aprueba && (
                        <button type="button" className="boton sutil chico" onClick={onProbarMail} disabled={ocupado} title="Manda el mail de mañana a la lista de prueba del equipo, ahora">
                          Probar
                        </button>
                      )}
                      <button type="button" className="boton sutil chico" onClick={onDetallesMail} title="La lista de Perfit, las variables, los envíos en curso y los mails de prueba">
                        Detalles
                      </button>
                    </>
                  )}
                  {f && x.canal === "whatsapp" && (
                    <button type="button" className="boton sutil chico" onClick={() => onVerWa(m.fecha)}>
                      <Icono nombre="celular" tam={13} /> Ver
                    </button>
                  )}
                  {f && (x.canal === "historia" || x.canal === "instagram" || x.canal === "facebook" || x.canal === "home") && (
                    <button type="button" className="boton sutil chico" onClick={() => onVerDia(m.fecha)}>
                      <Icono nombre="imagen" tam={13} /> Ver
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
