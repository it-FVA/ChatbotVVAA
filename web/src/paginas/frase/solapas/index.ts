// (3/11) LA lista de solapas del detalle del día, en un solo lugar. Una solapa nueva = un archivo acá (un componente con PropsSolapa)
// y una línea en SOLAPAS. DetalleDia.tsx dibuja los botones y el contenido a partir de esta lista.
import type { Dia, Frase, Resumen } from "../../../apiFrases";
import type { Correr } from "../comun";
import Texto from "./Texto";
import Mover from "./Mover";
import Cambiar from "./Cambiar";
import Foto from "./Foto";
import Diseno from "./Diseno";
import Saltar from "./Saltar";

/** Lo que recibe cada solapa: la frase del día, el día, si hay una acción en curso y `correr` (ejecuta, avisa, refresca, deshacer). */
export interface PropsSolapa {
  f: Frase;
  fecha: string;
  d: Dia;
  ocupado: boolean;
  correr: Correr;
  estiloOpciones?: Resumen["estilo_opciones"];
  estiloGlobal?: Resumen["estilo_global"];
}

export const SOLAPAS = [
  { clave: "texto", titulo: "Texto", Componente: Texto },
  { clave: "mover", titulo: "Mover / intercambiar", Componente: Mover },
  { clave: "cambiar", titulo: "Cambiar por otra", Componente: Cambiar },
  { clave: "foto", titulo: "Foto de fondo", Componente: Foto },
  { clave: "diseno", titulo: "Diseño", Componente: Diseno },
  { clave: "saltar", titulo: "Saltar / sacar", Componente: Saltar },
] as const;

export type Solapa = (typeof SOLAPAS)[number]["clave"];
