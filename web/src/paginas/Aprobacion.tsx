import { Navigate } from "react-router-dom";
import { STREAMLIT_URL } from "../api";
import { useSesion } from "../App";
import { EstadoVacio } from "../componentes/Comunes";
import { Icono } from "../componentes/Iconos";

// «Aprobación» (22/10): sección aparte de Administración, para aprobadores. Por ahora es un marcador: la cola para aprobar,
// el registro y la papelera siguen en el Panel admin de Streamlit (fase 3 del plan).
export default function Aprobacion() {
  const { yo } = useSesion();
  if (!yo?.rol.aprueba) return <Navigate to="/recortes" replace />;
  return (
    <div className="pagina">
      <header className="pagina-cabecera">
        <div>
          <h1>Aprobación</h1>
          <p className="suave">Piezas para aprobar, cola, registro y papelera.</p>
        </div>
      </header>
      <EstadoVacio
        titulo="Por ahora se aprueba en la app de Streamlit"
        texto="Esta sección se arma en la fase 3 (publicar y aprobar desde la web). Mientras tanto, el Panel admin de Streamlit sigue igual."
        accion={
          <a className="boton primario" href={STREAMLIT_URL + "/?vista=publicar"} target="_blank" rel="noreferrer">
            <Icono nombre="externo" tam={16} /> Abrir el Panel admin en Streamlit
          </a>
        }
      />
    </div>
  );
}
