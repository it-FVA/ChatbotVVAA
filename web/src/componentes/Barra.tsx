import { NavLink, useNavigate } from "react-router-dom";
import { api, STREAMLIT_URL } from "../api";
import { useSesion } from "../App";
import { Icono } from "./Iconos";

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
      <nav className="barra-nav" aria-label="Secciones">
        <NavLink to="/chat" className={({ isActive }) => "barra-link" + (isActive ? " activo" : "")}>
          <Icono nombre="chat" /> Chat
        </NavLink>
        <NavLink to="/recortes" className={({ isActive }) => "barra-link" + (isActive ? " activo" : "")}>
          <Icono nombre="pelicula" /> Mis recortes
        </NavLink>
        <a className="barra-link externo" href={STREAMLIT_URL + "/?vista=publicar"} target="_blank" rel="noreferrer" title="Por ahora las publicaciones siguen en la app de Streamlit">
          <Icono nombre="megafono" /> Mis publicaciones <span className="suave chico">Streamlit</span>
        </a>
      </nav>
      <div className="barra-pie">
        <div className="chico">
          <strong>{yo?.usuario}</strong>
          <div className="suave">{yo?.rol.nombre}</div>
        </div>
        <button className="boton sutil chico" onClick={salir} title="Cerrar la sesión">
          <Icono nombre="salir" tam={16} /> Salir
        </button>
      </div>
    </aside>
  );
}
