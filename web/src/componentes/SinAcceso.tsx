// (27/11, Franco) Una sección que no es para tu rol: antes la web te mandaba a Recortes sin decir nada y parecía que «no cargó».
// La API igual niega los datos (403), esto es solo el cartel.
import { Link } from "react-router-dom";
import { EstadoVacio } from "./Comunes";

export default function SinAcceso({ seccion, para }: { seccion: string; para: string }) {
  return (
    <div className="pagina">
      <EstadoVacio
        icono="alerta"
        titulo={`${seccion} no está disponible para tu usuario`}
        texto={`Esta sección es solo para ${para}. Si te parece que tendrías que verla, pedile a un administrador que cambie tu rol.`}
        accion={
          <Link to="/chat" className="boton">
            Volver al chat
          </Link>
        }
      />
    </div>
  );
}
