import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useSesion } from "../../App";
import { Icono } from "../../componentes/Iconos";

// Sección «Administración» (22/10, solo admins), separada de «Aprobación». Menú propio: Usuarios y Lista blanca hoy;
// Dashboard, Salud, Servicios y Configuración quedan marcados como «pronto» (siguen en el Panel admin de Streamlit).
const MENU: { a: string; texto: string; icono: string; pronto?: boolean }[] = [
  { a: "/administracion/usuarios", texto: "Usuarios", icono: "usuarios" },
  { a: "/administracion/lista-blanca", texto: "Lista blanca", icono: "check" },
  { a: "/administracion/dashboard", texto: "Dashboard", icono: "reloj", pronto: true },
  { a: "/administracion/salud", texto: "Salud", icono: "alerta", pronto: true },
  { a: "/administracion/servicios", texto: "Servicios y costos", icono: "info", pronto: true },
  { a: "/administracion/configuracion", texto: "Configuración", icono: "ajustar", pronto: true },
];

export default function Administracion() {
  const { yo } = useSesion();
  if (!yo?.rol.admin) return <Navigate to="/recortes" replace />;
  return (
    <div className="pagina admin">
      <header className="pagina-cabecera">
        <div>
          <h1>Administración</h1>
          <p className="suave">Cuentas, permisos y, más adelante, el estado de los servicios.</p>
        </div>
      </header>
      <div className="admin-grilla">
        <nav className="admin-menu" aria-label="Administración">
          {MENU.map((m) =>
            m.pronto ? (
              <span key={m.a} className="admin-link pronto" aria-disabled="true" title="Por ahora sigue en el Panel admin de Streamlit">
                <Icono nombre={m.icono} tam={16} /> {m.texto} <span className="chico suave">pronto</span>
              </span>
            ) : (
              <NavLink key={m.a} to={m.a} className={({ isActive }) => "admin-link" + (isActive ? " activo" : "")}>
                <Icono nombre={m.icono} tam={16} /> {m.texto}
              </NavLink>
            ),
          )}
        </nav>
        <div className="admin-contenido">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
