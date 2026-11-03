// Frase del día (22/10): el calendario anual de frases.
// Para aprobadores y admins (botón propio en la barra; pedido de Franco: no va dentro de Administración). Qué hay: cabecera con
// conteos, interruptor (solo admins) y avisos; «Próximas 14 días»; calendario por mes con ARRASTRAR Y SOLTAR entre días (un día
// libre = mover; uno ocupado = intercambiar; desde el backlog = asignar) y «Deshacer»; detalle del día (vista previa de la imagen
// compuesta, editar texto, mover a / intercambiar con otra fecha, cambiar por otra, foto de fondo del banco, saltar, sacar);
// backlog con buscador (validadas sin día · pendientes de validación); «Repartir en el año», vaciar y agregar una frase.
// La configuración de salida (hora, canales, foto por defecto, estilo, pie) vive en Administración → Configuración (solo admins).
// (2/11, reunión del 2/11) Los creadores de contenido también entran: ven el calendario, el backlog y la vista previa, y piden cambios
// («me gustaría que este día salga esta frase»); los aprobadores los aceptan o rechazan desde el panel «Solicitudes». Y todos pueden
// ver el mail de un día como lo arma la plantilla (reproducción de la de Perfit) con «Ver el mail».
// (3/11, revisión 5.2 punto 13) Partida en paginas/frase/: el estado en useFraseDelDia.ts, un archivo por panel en paneles/ y una
// solapa del detalle del día por archivo en solapas/ (la lista de solapas se registra en solapas/index.ts). Acá queda solo el armado.
import { Link } from "react-router-dom";
import { apiFrases } from "../../apiFrases";
import { Hueso } from "../../componentes/Comunes";
import { Icono } from "../../componentes/Iconos";
import Modal from "../../componentes/Modal";
import { fechaLarga, iso } from "./comun";
import { BacklogPanel } from "./paneles/Backlog";
import { Calendario } from "./paneles/Calendario";
import { Conteo } from "./paneles/Conteo";
import { MailPanel } from "./paneles/MailPanel";
import { MananaCard } from "./paneles/MananaCard";
import { NuevaFrase } from "./paneles/NuevaFrase";
import { Proximas } from "./paneles/Proximas";
import { Repartir } from "./paneles/Repartir";
import { SolicitudesPanel } from "./paneles/Solicitudes";
import { VerMail } from "./paneles/VerMail";
import { VerWhatsapp } from "./paneles/VerWhatsapp";
import { useFraseDelDia } from "./useFraseDelDia";
import { DetalleDia } from "./DetalleDia";
import "../../frases.css";

export default function FraseDelDia() {
  const s = useFraseDelDia();
  const { avisar, resumen, proximas, diaSel, setDiaSel, error, arrastre, setArrastre, setSobre, deshacer, setDeshacer, modal, setModal, verMail, setVerMail, verWa, setVerWa, verMailDetalles, setVerMailDetalles, solapaPedida, setSolapaPedida, ocupado, version, recargar, ofrecerDeshacer, correr, cambiarCanales, alternarActiva, aprueba, c } = s;
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
        <>
          {/* (2/11, Franco) la tarjeta «Mañana» arriba de todo: qué sale mañana y por dónde, con los interruptores y la vista previa */}
          <MananaCard
            resumen={resumen}
            aprueba={aprueba}
            ocupado={ocupado}
            onActiva={alternarActiva}
            onCanales={cambiarCanales}
            onEncolar={() => correr(async () => (await apiFrases.mananaEncolar()).mensaje)}
            onFrenar={() => correr(async () => (await apiFrases.mananaFrenar()).mensaje)}
            onVerDia={(fecha, solapa) => {
              setDiaSel(fecha);
              if (solapa) setSolapaPedida({ s: solapa, n: Date.now() });
            }}
            onVerMail={(f) => setVerMail(f)}
            onVerWa={(f) => setVerWa(f)}
            onDetallesMail={() => setVerMailDetalles(true)}
            onProbarMail={() =>
              correr(async () => {
                const r = await apiFrases.mailPrueba(resumen.manana?.fecha);
                const ok = r.resultados.filter((x) => x.ok).length;
                return `Mail de prueba: ${ok} de ${r.resultados.length} enviado${r.resultados.length === 1 ? "" : "s"}` + (ok < r.resultados.length ? " (ver el panel del mail abajo)" : ".");
              })
            }
          />
          <div className="fd-conteos chico">
            <Conteo n={c.sin_fecha_validadas} texto="en el backlog" ayuda="validadas sin día" />
            <Conteo n={c.programadas} texto="programadas" ayuda="desde hoy" />
            <Conteo n={c.publicadas} texto="publicadas" />
            <Conteo n={c.pendientes_validar} texto="pendientes de validar" ayuda="esperan el OK de Pato" suave />
            <span className="suave chico">
              {c.validadas ?? 0} validadas de {c.total ?? 0} cargadas
              {resumen.frases_nuevas_hasta ? ` · hay frases nuevas hasta el ${fechaLarga(resumen.frases_nuevas_hasta)}` : " · ya salieron todas al menos una vez, siguen en rotación"}
            </span>
          </div>
          {resumen.avisos.map((a, i) => (
            <div key={i} className="aviso chico">
              <Icono nombre="alerta" tam={16} /> {a}
            </div>
          ))}
        </>
      )}

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
        <Calendario s={s} />

        <aside className="fd-lateral">
          <Proximas lista={proximas} onElegir={setDiaSel} />
          <BacklogPanel version={version} arrastrando={!!arrastre} soloLectura={!aprueba} onArrastrar={setArrastre} onSoltarArrastre={() => (setArrastre(null), setSobre(null))} onElegir={(fr) => setDiaSel(fr.fecha ?? diaSel)} />
        </aside>
      </div>

      {/* (2/11 noche, Franco) los detalles del envío por Perfit ya no ocupan la pantalla: se abren desde la fila Mail de la tarjeta */}
      {verMailDetalles && resumen && (
        <Modal titulo="Envío por mail (Perfit)" onCerrar={() => setVerMailDetalles(false)} ancho={720}>
          <MailPanel admin={resumen.admin} />
        </Modal>
      )}
      {diaSel && (
        <DetalleDia
          fecha={diaSel}
          solapaPedida={solapaPedida}
          estiloOpciones={resumen?.estilo_opciones}
          estiloGlobal={resumen?.estilo_global}
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
