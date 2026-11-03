// El detalle de un día (ventana): la frase, la vista previa y, para aprobadores, las solapas registradas en solapas/index.ts.
import { useCallback, useEffect, useState } from "react";
import { type Dia, type Resumen, apiFrases } from "../../apiFrases";
import { Icono } from "../../componentes/Iconos";
import Modal from "../../componentes/Modal";
import { useToast } from "../../componentes/Toasts";
import { fechaCorta, fechaLarga, horaArgentina, mensajeDe } from "./comun";
import { Buscador } from "./paneles/Buscador";
import { SolicitarCambio } from "./paneles/Solicitudes";
import { SOLAPAS, type Solapa } from "./solapas";

export function DetalleDia({ fecha, version, aprueba, solapaPedida, estiloOpciones, estiloGlobal, onVerMail, onVerWhatsapp, onCerrar, onCambio, ofrecerDeshacer }: { fecha: string; version: number; aprueba: boolean; solapaPedida?: { s: Solapa; n: number } | null; estiloOpciones?: Resumen["estilo_opciones"]; estiloGlobal?: Resumen["estilo_global"]; onVerMail: () => void; onVerWhatsapp: () => void; onCerrar: () => void; onCambio: (nuevaFecha?: string | null) => void; ofrecerDeshacer: (texto: string, hacer: () => Promise<void>) => void }) {
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
  const SolapaActiva = (SOLAPAS.find((x) => x.clave === solapa) ?? SOLAPAS[0]).Componente;
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
                En la cola: estado <strong>{d.cola.estado}</strong>, sale el {horaArgentina(d.cola.fecha_programada)}
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
            {SOLAPAS.map((x) => (
              <button key={x.clave} role="tab" aria-selected={solapa === x.clave} className={"solapa" + (solapa === x.clave ? " activa" : "")} onClick={() => setSolapa(x.clave)}>
                {x.titulo}
              </button>
            ))}
          </div>
          <SolapaActiva f={f} fecha={fecha} d={d} ocupado={ocupado} correr={correr} estiloOpciones={estiloOpciones} estiloGlobal={estiloGlobal} />
        </>
      )}
    </Modal>
  );
}
