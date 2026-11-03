// Solapa «Cambiar por otra» del detalle del día: la frase vuelve a «sin día» y entra la elegida.
import { apiFrases } from "../../../apiFrases";
import { fechaCorta } from "../comun";
import { Buscador } from "../paneles/Buscador";
import type { PropsSolapa } from "./index";

export default function Cambiar({ f, fecha, ocupado, correr }: PropsSolapa) {
  return (
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
  );
}
