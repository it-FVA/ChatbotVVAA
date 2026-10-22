import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useSesion } from "../../App";
import { adminApi, type Resumen } from "./adminApi";
import { IconoAdmin, type NombreIconoAdmin } from "./comun";
import "../../admin.css";

// Sección «Administración» (22/10, solo admins), separada de «Aprobación». Menú propio: Dashboard (portada), Salud (con el badge
// de avisos), Servicios y costos, Usuarios, Lista blanca y Configuración. El resumen (GET /admin/resumen) se comparte por
// contexto: el Dashboard lo muestra y el badge de Salud sale de ahí; «Volver a chequear» en Salud lo refresca.
const MENU: { a: string; texto: string; icono: NombreIconoAdmin; badge?: boolean }[] = [
  { a: "/administracion/dashboard", texto: "Dashboard", icono: "tablero" },
  { a: "/administracion/salud", texto: "Salud", icono: "pulso", badge: true },
  { a: "/administracion/servicios", texto: "Servicios y costos", icono: "moneda" },
  { a: "/administracion/usuarios", texto: "Usuarios", icono: "usuarios" },
  { a: "/administracion/lista-blanca", texto: "Lista blanca", icono: "check" },
  { a: "/administracion/configuracion", texto: "Configuración", icono: "engranaje" },
];

interface Admin {
  resumen: Resumen | null;
  errorResumen: string | null;
  recargarResumen: () => Promise<void>;
}

const Ctx = createContext<Admin>({ resumen: null, errorResumen: null, recargarResumen: async () => {} });
export const useAdmin = () => useContext(Ctx);

export default function Administracion() {
  const { yo } = useSesion();
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [errorResumen, setError] = useState<string | null>(null);
  const esAdmin = !!yo?.rol.admin;

  const recargarResumen = useCallback(async () => {
    try {
      setResumen(await adminApi.resumen());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pude leer el resumen.");
    }
  }, []);

  useEffect(() => {
    if (esAdmin) recargarResumen();
  }, [esAdmin, recargarResumen]);

  const valor = useMemo(() => ({ resumen, errorResumen, recargarResumen }), [resumen, errorResumen, recargarResumen]);
  if (!esAdmin) return <Navigate to="/recortes" replace />;

  const s = resumen?.salud;
  const avisos = (s?.errores ?? 0) + (s?.avisos ?? 0);
  const badgeEstado = s?.estado === "error" ? "error" : s?.estado === "aviso" ? "aviso" : "ok";

  return (
    <Ctx.Provider value={valor}>
      <div className="pagina admin">
        <header className="pagina-cabecera">
          <div>
            <h1>Administración</h1>
            <p className="suave">¿Funciona la app? ¿Cuánto cuesta? Quién la usa, los servicios, las cuentas y la configuración.</p>
          </div>
        </header>
        <div className="admin-grilla">
          <nav className="admin-menu" aria-label="Administración">
            {MENU.map((m) => (
              <NavLink key={m.a} to={m.a} className={({ isActive }) => "admin-link" + (isActive ? " activo" : "")}>
                <IconoAdmin nombre={m.icono} tam={16} /> {m.texto}
                {m.badge && s && s.estado !== "sin_dato" && (
                  <span className={"badge " + badgeEstado} aria-label={avisos ? `${avisos} avisos` : "todo en orden"} title={avisos ? `${s.errores ?? 0} errores, ${s.avisos ?? 0} avisos (último chequeo)` : "Último chequeo: todo en orden"}>
                    {avisos || "✓"}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="admin-contenido">
            <Outlet />
          </div>
        </div>
      </div>
    </Ctx.Provider>
  );
}
