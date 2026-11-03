// Solapa «Diseño» del detalle del día (2/11 noche): las herramientas de imagen de Diseñar, guardadas por frase.
import { type Frase, type Resumen, apiFrases } from "../../../apiFrases";
import { Icono } from "../../../componentes/Iconos";
import type { PropsSolapa } from "./index";

/** (2/11 noche, Franco) La solapa «Diseño» del día: las mismas herramientas de imagen de Diseñar, guardadas por frase. Cada cambio se
 *  guarda y la vista previa se vuelve a armar. «Volver al estilo general» borra lo propio de la frase. */
export const ETIQUETA_ESTILO: Record<string, string> = { logo: "Logo", posicion_logo: "Posición del logo", tipografia: "Tipografía", peso: "Peso", posicion: "Posición del texto", alineacion: "Alineación" };

export function DisenoFrase({ f, opciones, global, ocupado, correr }: { f: Frase; opciones?: Resumen["estilo_opciones"]; global?: Resumen["estilo_global"]; ocupado: boolean; correr: (a: () => Promise<string | void>) => Promise<void> }) {
  if (!opciones) return <p className="suave chico">Cargando las opciones de diseño…</p>;
  const listas: Record<string, string[]> = { logo: opciones.logos, posicion_logo: opciones.posiciones_logo, tipografia: opciones.tipografias, peso: opciones.pesos, posicion: opciones.posiciones, alineacion: opciones.alineaciones };
  const propio = f.estilo ?? {};
  const valor = (k: string) => propio[k] ?? global?.[k] ?? listas[k][0];
  const conLogo = valor("logo") !== "Sin logo";
  function cambiar(k: string, v: string) {
    correr(async () => ((await apiFrases.editar(f.id, { estilo: { ...propio, [k]: v } })), "Diseño guardado: la imagen se vuelve a armar."));
  }
  return (
    <div className="fd-form">
      <p className="suave chico">
        Cómo se dibuja la frase sobre la foto, para esta frase. Lo que no cambies queda como el estilo general (Configuración → Estilo).
        {Object.keys(propio).length > 0 ? " Esta frase tiene diseño propio." : " Esta frase usa el estilo general."}
      </p>
      <div className="fd-diseno">
        {Object.keys(listas).map((k) => (
          <label key={k} className="campo">
            <span>
              {ETIQUETA_ESTILO[k]}
              {propio[k] && <span className="chip chico amarillo"> propio</span>}
            </span>
            <select value={valor(k)} onChange={(e) => cambiar(k, e.target.value)} disabled={ocupado || (k === "posicion_logo" && !conLogo)}>
              {listas[k].map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      {Object.keys(propio).length > 0 && (
        <div className="acciones">
          <button type="button" className="boton chico" disabled={ocupado} onClick={() => correr(async () => ((await apiFrases.editar(f.id, { quitar_estilo: true })), "Vuelve al estilo general."))}>
            <Icono nombre="deshacer" tam={14} /> Volver al estilo general
          </button>
        </div>
      )}
    </div>
  );
}

export default function Diseno({ f, estiloOpciones, estiloGlobal, ocupado, correr }: PropsSolapa) {
  return <DisenoFrase f={f} opciones={estiloOpciones} global={estiloGlobal} ocupado={ocupado} correr={correr} />;
}
