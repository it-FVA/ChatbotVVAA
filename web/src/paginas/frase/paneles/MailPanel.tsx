// Panel «Envío por mail (Perfit) · detalles» (se abre en una ventana desde la fila Mail de la tarjeta «Mañana»).
import { diaMes } from "../../../util/fechas";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorApi } from "../../../api";
import { type MailEstado, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { recortar } from "../comun";

/** (26/10, reunión: la Frase del día vuelve por mail con el disparador de Perfit) Estado del canal mail y la prueba al equipo.
 * Lo ven aprobadores y admins; el botón de prueba es de admins. La hora de inicio y la lista de prueba se cargan en Configuración. */
// (2/11, Franco) achicado: lo del día a día (ver el mail, probar, qué sale mañana) está en la tarjeta «Mañana»; acá quedan los detalles
// del envío por Perfit: la lista, las variables, el avance de un envío en curso y los mails de prueba.
export function MailPanel({ admin }: { admin: boolean }) {
  // (2/11 noche) se muestra dentro de una ventana: siempre abierto
  const [est, setEst] = useState<MailEstado | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  const modoTxt = est ? { apagado: "apagado", simulado: "simulado (registra, no manda)", real: "real" }[est.modo] : "";
  // solo los envíos con movimiento (en curso o con conteo): el estado de mañana está en la tarjeta de arriba
  const dias = est ? Object.entries(est.envios).filter(([, d]) => d.pieza && (d.estado === "enviando" || (d.conteo && d.conteo.total))) : [];
  return (
    <details className="fd-panel" open>
      <summary>
        <Icono nombre="chevron" tam={16} />
        <Icono nombre="sobre" tam={17} />
        <span>
          Envío por mail (Perfit) · detalles
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
              Perfit manda hasta {est.limite_por_hora} mails por hora con su disparador personalizado, así que el envío arranca a las {est.inicio} ({est.inicio < (est.hora || "07:00") ? "de madrugada, el mismo día" : "del día anterior"}) y se completa durante la mañana. La automation de Perfit (clave <code>{est.trigger_key}</code>) arma el mail con: {est.contexto_plantilla.join(", ")}.
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
            {dias.length > 0 && (
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
                      {d.arranca && d.estado === "pendiente" ? ` · arranca ${diaMes(d.arranca.slice(0, 10))} ${d.arranca.slice(11, 16)}` : ""}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            )}
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
            </div>
            {est.pruebas.length > 0 && (
              <p className="suave chico">
                Últimas pruebas: {est.pruebas.slice(0, 5).map((p) => `${p.email} (${p.estado}${p.enviado_en ? ", " + diaMes(p.enviado_en.slice(0, 10)) : ""})`).join(" · ")}
              </p>
            )}
          </>
        )}
      </div>
    </details>
  );
}
