// Solapa «Mover / intercambiar» del detalle del día.
import { useEffect, useState } from "react";
import { type Dia, type Frase, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import { fechaCorta, iso, recortar } from "../comun";
import type { PropsSolapa } from "./index";

export function MoverIntercambiar({ f, fecha, ocupado, correr }: { f: Frase; fecha: string; hoy?: string; ocupado: boolean; correr: (a: () => Promise<string | void>, despues?: string | null, deshacer?: { texto: string; hacer: () => Promise<void> }) => Promise<void> }) {
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

export default function Mover({ f, fecha, d, ocupado, correr }: PropsSolapa) {
  return <MoverIntercambiar f={f} fecha={fecha} hoy={d.pasado ? fecha : undefined} ocupado={ocupado} correr={correr} />;
}
