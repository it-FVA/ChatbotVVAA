import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import type { Yo } from "./tipos";
import Login from "./paginas/Login";
import PrimeraVez from "./paginas/PrimeraVez";
import Recortes from "./paginas/Recortes";
import Editor from "./paginas/Editor";
import Chat from "./paginas/Chat";
import Cuenta from "./paginas/Cuenta";
import Aprobacion, { Clips, Cola, Papelera, ParaAprobar, Registro } from "./paginas/Aprobacion";
import Publicar from "./paginas/Publicar";
import Publicaciones from "./paginas/Publicaciones";
import Administracion from "./paginas/admin/Administracion";
import Usuarios from "./paginas/admin/Usuarios";
import ListaBlanca from "./paginas/admin/ListaBlanca";
import Dashboard from "./paginas/admin/Dashboard";
import Salud from "./paginas/admin/Salud";
import Servicios from "./paginas/admin/Servicios";
import Configuracion from "./paginas/admin/Configuracion";
import Barra from "./componentes/Barra";
import Proyectos from "./paginas/Proyectos";
import Compartidos from "./paginas/Compartidos";
import { ProyectosProvider } from "./componentes/proyectos/ProyectosContexto";

interface Sesion {
  yo: Yo | null;
  cargando: boolean;
  setYo: (y: Yo | null) => void;
}

const Ctx = createContext<Sesion>({ yo: null, cargando: true, setYo: () => {} });
export const useSesion = () => useContext(Ctx);

export default function App() {
  const [yo, setYo] = useState<Yo | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    api
      .yo()
      .then(setYo)
      .catch(() => setYo(null))
      .finally(() => setCargando(false));
  }, []);

  return (
    <Ctx.Provider value={{ yo, cargando, setYo }}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/primera-vez" element={<PrimeraVez />} />
        <Route
          path="/*"
          element={
            <Protegido>
              <ProyectosProvider>
              <div className="app">
                <Barra />
                <main className="contenido">
                  <Routes>
                    <Route path="/" element={<Navigate to="/chat" replace />} />
                    <Route path="/chat" element={<Chat />} />
                    <Route path="/chat/:id" element={<Chat />} />
                    <Route path="/recortes" element={<Recortes />} />
                    <Route path="/recortes/:id" element={<Editor />} />
                    <Route path="/proyectos" element={<Proyectos />} />
                    <Route path="/proyectos/:id" element={<Proyectos />} />
                    <Route path="/compartidos" element={<Compartidos />} />
                    <Route path="/cuenta" element={<Cuenta />} />
                    <Route path="/publicar" element={<Publicar />} />
                    <Route path="/publicaciones" element={<Publicaciones />} />
                    <Route path="/aprobacion" element={<Aprobacion />}>
                      <Route index element={<ParaAprobar />} />
                      <Route path="cola" element={<Cola />} />
                      <Route path="registro" element={<Registro />} />
                      <Route path="papelera" element={<Papelera />} />
                      <Route path="clips" element={<Clips />} />
                      <Route path="*" element={<Navigate to="/aprobacion" replace />} />
                    </Route>
                    <Route path="/administracion" element={<Administracion />}>
                      <Route index element={<Navigate to="/administracion/dashboard" replace />} />
                      <Route path="dashboard" element={<Dashboard />} />
                      <Route path="salud" element={<Salud />} />
                      <Route path="servicios" element={<Servicios />} />
                      <Route path="usuarios" element={<Usuarios />} />
                      <Route path="lista-blanca" element={<ListaBlanca />} />
                      <Route path="configuracion" element={<Configuracion />} />
                      <Route path="*" element={<Navigate to="/administracion/dashboard" replace />} />
                    </Route>
                    <Route path="*" element={<Navigate to="/recortes" replace />} />
                  </Routes>
                </main>
              </div>
              </ProyectosProvider>
            </Protegido>
          }
        />
      </Routes>
    </Ctx.Provider>
  );
}

function Protegido({ children }: { children: React.ReactNode }) {
  const { yo, cargando } = useSesion();
  const loc = useLocation();
  if (cargando)
    return (
      <div className="pantalla-centro suave" aria-busy="true">
        <span className="girando" aria-hidden="true" /> Cargando…
      </div>
    );
  if (!yo) return <Navigate to="/login" replace state={{ desde: loc.pathname }} />;
  // (22/10) Con una contraseña temporal (la puso un admin) no se puede usar nada hasta elegir una propia.
  if (yo.debe_cambiar_clave && loc.pathname !== "/cuenta") return <Navigate to="/cuenta" replace />;
  return <>{children}</>;
}
