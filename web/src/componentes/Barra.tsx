import { NavLink, useNavigate } from "react-router-dom";
import { api, STREAMLIT_URL } from "../api";
import { useSesion } from "../App";

export default function Barra() {
  const { yo, setYo } = useSesion();
  const nav = useNavigate();

  async function salir() {
    try {
      await api.logout();
    } finally {
      setYo(null);
      nav("/login", { replace: true });
    }
  }

  return (
    <aside className="barra">
      <div className="barra-marca">
        <img src="/logo.png" alt="" />
        <div>
          <div className="barra-titulo">Vivir Agradecidos</div>
          <div className="suave chico">Asistente de contenido</div>
        </div>
      </div>
      <nav className="barra-nav">
        <NavLink to="/recortes" className={({ isActive }) => "barra-link" + (isActive ? " activo" : "")}>
          🎬 Mis recortes
        </NavLink>
        <a className="barra-link externo" href={STREAMLIT_URL} target="_blank" rel="noreferrer" title="Por ahora el chat sigue en la app de Streamlit">
          💬 Chat <span className="suave chico">↗ Streamlit</span>
        </a>
        <a className="barra-link externo" href={STREAMLIT_URL + "/?vista=publicar"} target="_blank" rel="noreferrer" title="Por ahora las publicaciones siguen en la app de Streamlit">
          📣 Mis publicaciones <span className="suave chico">↗ Streamlit</span>
        </a>
      </nav>
      <div className="barra-pie">
        <div className="chico">
          <strong>{yo?.usuario}</strong>
          <div className="suave">{yo?.rol.nombre}</div>
        </div>
        <button className="boton chico" onClick={salir}>
          Salir
        </button>
      </div>
    </aside>
  );
}
