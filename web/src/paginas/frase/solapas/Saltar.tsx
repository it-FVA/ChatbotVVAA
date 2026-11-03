// Solapa «Saltar / sacar» del detalle del día.
import { diaMes } from "../../../util/fechas";
import { apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";

import type { PropsSolapa } from "./index";

export default function Saltar({ f, fecha, ocupado, correr }: PropsSolapa) {
  return (
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
          onClick={() => correr(async () => (await apiFrases.sacar(f.id)).mensaje, null, { texto: `Sacada del ${diaMes(fecha)}.`, hacer: async () => void (await apiFrases.mover(f.id, fecha)) })}
          disabled={ocupado}
        >
          <Icono nombre="tacho" tam={15} /> Sacar del calendario
        </button>
      </div>
    </div>
  );
}
