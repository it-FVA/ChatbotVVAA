import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useSesion } from "../App";
import { Icono } from "./Iconos";

// Barra lateral. Rediseñada el 2/11 a pedido de Alberto (reunión del 2/11): de lo general a lo particular.
//   Chat · Canales (Diseñar: Instagram, Facebook, Blogpost, YouTube, Email; WhatsApp pronto) · Campañas (Frase del día,
//   Newsletter) · Proyectos (míos, compartidos conmigo) · Herramientas (Mis publicaciones, Mis recortes) · Equipo (Aprobación,
//   Administración). «Publicar» pasó a llamarse «Diseñar»: una cosa es diseñar la pieza y otra publicarla (eso lo hace el aprobador).
// Abajo, el usuario lleva a «Mi cuenta» (cambiar la contraseña).
const CANALES = [
  { clave: "instagram", texto: "Instagram", icono: "imagen" },
  { clave: "facebook", texto: "Facebook", icono: "megafono" },
  { clave: "wordpress", texto: "Blogpost", icono: "casa" },
  { clave: "youtube", texto: "YouTube", icono: "pelicula" },
] as const;

export default function Barra() {
  const { yo, setYo } = useSesion();
  const nav = useNavigate();
  const loc = useLocation();

  async function salir() {
    try {
      await api.logout();
    } finally {
      setYo(null);
      nav("/login", { replace: true });
    }
  }

  const link = ({ isActive }: { isActive: boolean }) => "barra-link" + (isActive ? " activo" : "");
  const sub = ({ isActive }: { isActive: boolean }) => "barra-link sub" + (isActive ? " activo" : "");
  // los canales de Diseñar comparten la página /publicar: el activo es el del ?canal= (ninguno si se entra con un borrador o un recorte)
  const canalActivo = loc.pathname === "/publicar" ? new URLSearchParams(loc.search).get("canal") : null;

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

        <div className="barra-grupo" title="Diseñar una pieza para cada canal. Publicarla es otro paso: lo hace quien aprueba.">
          Canales · Diseñar
        </div>
        {CANALES.map((c) => (
          <NavLink key={c.clave} to={`/publicar?canal=${c.clave}`} className={"barra-link sub" + (canalActivo === c.clave ? " activo" : "")} title={`Diseñar una pieza para ${c.texto}`}>
            <Icono nombre={c.icono} /> {c.texto}
          </NavLink>
        ))}
        <NavLink to="/newsletter" className={sub} title="Diseñar un email (el editor del newsletter)">
          <Icono nombre="sobre" /> Email
        </NavLink>
        <span className="barra-link sub pronto" title="Todavía no: la frase del día al grupo de WhatsApp está en estudio (reunión del 2/11)">
          <Icono nombre="celular" /> WhatsApp <span className="suave chico">pronto</span>
        </span>

        <div className="barra-grupo">Campañas</div>
        <NavLink to="/frase-del-dia" className={sub} title={yo?.rol.aprueba ? "El calendario anual de la frase que sale cada mañana" : "El calendario de la frase que sale cada mañana: mirá qué sale y pedí cambios"}>
          <Icono nombre="calendario" /> Frase del día
        </NavLink>
        <NavLink to="/newsletter" className={sub} title="El newsletter mensual">
          <Icono nombre="sobre" /> Newsletter
        </NavLink>

        <div className="barra-grupo">Proyectos</div>
        <NavLink to="/proyectos" className={sub} title="Carpetas para agrupar chats, piezas, recortes y newsletters de una misma campaña, y compartirlas con el equipo">
          <Icono nombre="carpeta" /> Mis proyectos
        </NavLink>
        <NavLink to="/compartidos" className={sub}>
          <Icono nombre="compartir" /> Compartidos conmigo
        </NavLink>

        <div className="barra-grupo">Herramientas</div>
        <NavLink to="/publicaciones" className={sub} title="Lo que diseñé: borradores, pruebas, pendientes de aprobación y publicadas">
          <Icono nombre="lista" /> Mis publicaciones
        </NavLink>
        <NavLink to="/recortes" className={sub} title="Recortes de video de YouTube, con editor">
          <Icono nombre="tijera" /> Mis recortes
        </NavLink>

        {(yo?.rol.aprueba || yo?.rol.admin) && <div className="barra-grupo">Equipo</div>}
        {yo?.rol.aprueba && (
          <NavLink to="/aprobacion" className={link} title="Las piezas que mandó el equipo: revisar, aprobar y publicar">
            <Icono nombre="check" /> Aprobación
          </NavLink>
        )}
        {yo?.rol.admin && (
          <NavLink to="/administracion" className={link}>
            <Icono nombre="usuarios" /> Administración
          </NavLink>
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
