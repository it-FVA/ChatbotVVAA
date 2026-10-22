import { NavLink, useNavigate } from "react-router-dom";
import { api, STREAMLIT_URL } from "../api";
import { useSesion } from "../App";
import { Icono } from "./Iconos";

// Barra lateral (22/10): Chat, Publicar, Mis publicaciones y Mis recortes en la web; «Newsletter» (y «Frase del día» para admins)
// siguen abriendo Streamlit hasta la fase siguiente. Dos secciones según el rol: «Aprobación» (aprobadores) y «Administración» (admins).
// Abajo, el usuario lleva a «Mi cuenta» (cambiar la contraseña).
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

  const link = ({ isActive }: { isActive: boolean }) => "barra-link" + (isActive ? " activo" : "");

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
        <NavLink to="/chat" className={link}>
          <Icono nombre="chat" /> Chat
        </NavLink>
        <NavLink to="/publicar" className={link}>
          <Icono nombre="enviar" /> Publicar
        </NavLink>
        <NavLink to="/publicaciones" className={link}>
          <Icono nombre="megafono" /> Mis publicaciones
        </NavLink>
        <NavLink to="/recortes" className={link}>
          <Icono nombre="pelicula" /> Mis recortes
        </NavLink>
        <a className="barra-link externo" href={STREAMLIT_URL + "/?vista=newsletter"} target="_blank" rel="noreferrer" title="El editor de Newsletter sigue en la app de Streamlit (fase siguiente)">
          <Icono nombre="externo" /> Newsletter <span className="suave chico">Streamlit</span>
        </a>
        {yo?.rol.aprueba && (
          <>
            <div className="barra-grupo">Equipo</div>
            <NavLink to="/aprobacion" className={link}>
              <Icono nombre="check" /> Aprobación
            </NavLink>
          </>
        )}
        {yo?.rol.admin && (
          <>
            <NavLink to="/administracion" className={link}>
              <Icono nombre="usuarios" /> Administración
            </NavLink>
            <a className="barra-link externo" href={STREAMLIT_URL + "/?vista=publicar"} target="_blank" rel="noreferrer" title="El calendario de la Frase del día sigue en el Panel admin de Streamlit (fase siguiente)">
              <Icono nombre="calendario" /> Frase del día <span className="suave chico">Streamlit</span>
            </a>
          </>
        )}
      </nav>
      <div className="barra-pie">
        <NavLink to="/cuenta" className={({ isActive }) => "barra-yo chico" + (isActive ? " activo" : "")} title="Mi cuenta: datos y contraseña">
          <strong>{yo?.nombre || yo?.usuario}</strong>
          <div className="suave">{yo?.rol.nombre}</div>
        </NavLink>
        <button className="boton sutil chico" onClick={salir} title="Cerrar la sesión">
          <Icono nombre="salir" tam={16} /> Salir
        </button>
      </div>
    </aside>
  );
}
