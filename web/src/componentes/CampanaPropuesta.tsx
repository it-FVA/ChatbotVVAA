// El recuadro «Campaña guardada» debajo de la respuesta cuando el chat armó una campaña (8/11, Beto): el link al Proyecto y una fila
// por pieza (canal, título, formato) con «Abrir en Diseñar». Las piezas ya están guardadas como borrador: no hace falta apretar nada
// para conservarlas. Lo dibuja Mensaje.tsx cuando el mensaje trae `campana`.
import { Link } from "react-router-dom";
import { useSesion } from "../App";
import type { Campana } from "../tiposChat";
import { Icono, type NombreIcono } from "./Iconos";

const ICONO_CANAL: Record<string, NombreIcono> = { instagram: "imagen", facebook: "megafono", youtube: "pelicula", wordpress: "lista", newsletter: "sobre" };
const FORMATO: Record<string, string> = { historia: "historia", cuadrado: "posteo cuadrado", reel: "reel", carrusel: "carrusel" };

export default function CampanaPropuesta({ campana }: { campana: Campana }) {
  const { yo } = useSesion();
  return (
    <section className="campana-caja" aria-label="Campaña guardada">
      <div className="campana-cabecera">
        <Icono nombre="carpeta" tam={18} />
        <strong>Campaña guardada: {campana.nombre}</strong>
        <Link className="boton sutil chico" to={`/proyectos/${encodeURIComponent(campana.proyecto_id)}`}>
          Ver el proyecto
        </Link>
      </div>
      <p className="suave chico">Cada pieza quedó como borrador, lista para abrir en Diseñar y terminar.</p>
      <ul className="campana-piezas">
        {campana.piezas.map((p) => {
          const icono = (yo?.canales?.find((c) => c.clave === p.canal)?.icono as NombreIcono | undefined) || ICONO_CANAL[p.canal] || "megafono";
          return (
            <li key={p.id} className="campana-pieza">
              <Icono nombre={icono} tam={18} />
              <div className="campana-pieza-datos">
                <span className="campana-pieza-titulo">{p.titulo || "Sin título"}</span>
                <span className="suave chico">
                  {p.canal_texto}
                  {p.formato && FORMATO[p.formato] ? ` · ${FORMATO[p.formato]}` : ""}
                </span>
                {p.porque && <span className="suave chico">{p.porque}</span>}
                {p.fuente && <span className="suave chico">Fuente: {p.fuente}</span>}
              </div>
              <Link className="boton primario chico" to={p.url_editar}>
                <Icono nombre="enviar" tam={16} /> Abrir en Diseñar
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
