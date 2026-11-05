import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useSesion } from "../App";
import { Icono, type NombreIcono } from "./Iconos";
import { useProyectos } from "./proyectos/ProyectosContexto";

// Barra lateral. Rediseñada el 2/11 a pedido de Alberto (reunión del 2/11): de lo general a lo particular.
//   Chat · Canales (Diseñar: Instagram, Facebook, Blogpost, YouTube, Email; WhatsApp pronto) · Campañas (Frase del día,
//   Newsletter) · Proyectos (míos, compartidos conmigo) · Herramientas (Mis publicaciones, Mis recortes) · Gestión (Aprobación,
//   Administración; se llamó «Equipo» hasta el 3/11). «Publicar» pasó a llamarse «Diseñar»: una cosa es diseñar la pieza y otra publicarla (eso lo hace el aprobador).
// Abajo, el usuario lleva a «Mi cuenta» (cambiar la contraseña).
// (3/11) Los canales del menú salen del registro de la API (canales.py, GET /yo → canales con en_disenar): no hay lista propia.
// (4/11, Franco) En celular el menú ocupaba toda la primera pantalla: ahora arriba va solo el logo y «Menú», que abre el menú
// completo como cajón lateral (se cierra al elegir, con Esc o tocando afuera). En la computadora no cambia.
// (4/11) Al abrir una pieza o un recorte desde una carpeta queda marcada la carpeta («Mis proyectos» o «Compartidos»), no
// «Mis publicaciones» / «Mis recortes»; una carpeta de otra persona marca «Compartidos».

export default function Barra() {
  const { yo, setYo } = useSesion();
  const canalesMenu = (yo?.canales || []).filter((c) => c.en_disenar);
  const nav = useNavigate();
  const loc = useLocation();
  const proyectos = useProyectos();
  const [abierto, setAbierto] = useState(false); // el cajón del celular

  // se cierra al cambiar de pantalla y con Escape
  useEffect(() => setAbierto(false), [loc.pathname, loc.search]);
  useEffect(() => {
    if (!abierto) return;
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setAbierto(false);
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [abierto]);

  // ¿se está mirando algo de una carpeta? (la vista de Proyectos manda {desde: {id}} al abrir un ítem)
  // (4/11) una pieza o un recorte de otra persona abierto por su link (sin pasar por la carpeta): la carpeta compartida donde está
  const abiertoSuelto = /^\/(publicaciones|recortes)\/([^/]+)/.exec(loc.pathname);
  const carpetaDelItem = abiertoSuelto ? proyectos.carpetaDe(abiertoSuelto[1] === "publicaciones" ? "pieza" : "recorte", abiertoSuelto[2]) : null;
  const ajenaDelItem = carpetaDelItem && proyectos.porId.get(carpetaDelItem.id)?.permiso !== "dueño" ? carpetaDelItem.id : null;
  const desdeId = (loc.state as { desde?: { id: string } } | null)?.desde?.id || ajenaDelItem || null;
  const carpetaId = desdeId || (loc.pathname.startsWith("/proyectos/") ? loc.pathname.split("/")[2] : null);
  const carpeta = carpetaId ? proyectos.porId.get(carpetaId) : undefined;
  const carpetaAjena = !!carpeta && carpeta.permiso !== "dueño";

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
  // las secciones que también se abren desde una carpeta: si se llegó por una carpeta, la marcada es la carpeta
  const subSinCarpeta = ({ isActive }: { isActive: boolean }) => sub({ isActive: isActive && !desdeId });
  // los canales de Diseñar comparten la página /publicar: el activo es el del ?canal= (ninguno si se entra con un borrador o un recorte)
  const canalActivo = loc.pathname === "/publicar" ? new URLSearchParams(loc.search).get("canal") : null;

  return (
    <aside className={"barra" + (abierto ? " abierta" : "")}>
      <div className="barra-marca">
        <img src="/logo.png" alt="" />
        <div>
          <div className="barra-titulo">Vivir Agradecidos</div>
          <div className="suave chico">Asistente de contenido</div>
        </div>
        <button type="button" className="boton sutil barra-menu-boton" onClick={() => setAbierto((a) => !a)} aria-expanded={abierto} aria-controls="barra-cajon">
          <Icono nombre={abierto ? "cruz" : "menu"} tam={20} /> <span>Menú</span>
        </button>
      </div>
      {abierto && <div className="barra-velo" onClick={() => setAbierto(false)} aria-hidden="true" />}
      <div className="barra-cajon" id="barra-cajon">
      <nav className="barra-nav" aria-label="Secciones">
        <NavLink to="/chat" className={link}>
          <Icono nombre="chat" /> Chat
        </NavLink>

        <div className="barra-grupo" title="Diseñar una pieza para cada canal. Publicarla es otro paso: lo hace quien aprueba.">
          Canales · Diseñar
        </div>
        {canalesMenu.map((c) => (
          <NavLink key={c.clave} to={`/publicar?canal=${c.clave}`} className={"barra-link sub" + (canalActivo === c.clave ? " activo" : "")} title={`Diseñar una pieza para ${c.texto}`}>
            <Icono nombre={c.icono as NombreIcono} /> {c.texto}
          </NavLink>
        ))}
        <NavLink to="/newsletter" className={sub} title="Diseñar un email (el editor del newsletter)">
          <Icono nombre="sobre" /> Email
        </NavLink>
        <span className="barra-link sub pronto" title="Todavía no se puede diseñar para WhatsApp: no hay forma de mandar desde la cuenta común. El prototipo de la frase del día al grupo se ve en Frase del día → un día → «Ver el WhatsApp»">
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
        <NavLink to="/proyectos" className={({ isActive }) => sub({ isActive: (isActive && !carpetaAjena) || (!!desdeId && !carpetaAjena) })} title="Carpetas para agrupar chats, piezas, recortes y newsletters de una misma campaña, y compartirlas con el equipo">
          <Icono nombre="carpeta" /> Mis proyectos
        </NavLink>
        <NavLink to="/compartidos" className={({ isActive }) => sub({ isActive: isActive || carpetaAjena })} title="Los proyectos que otras personas compartieron conmigo">
          <Icono nombre="compartir" /> Compartidos
        </NavLink>

        <div className="barra-grupo">Herramientas</div>
        <NavLink to="/publicaciones" className={subSinCarpeta} title="Lo que diseñé: borradores, pruebas, pendientes de aprobación y publicadas">
          <Icono nombre="lista" /> Mis publicaciones
        </NavLink>
        <NavLink to="/recortes" className={subSinCarpeta} title="Recortes de video de YouTube, con editor">
          <Icono nombre="tijera" /> Mis recortes
        </NavLink>

        {/* (3/11, Franco) «Equipo» no decía qué era: son las herramientas de aprobación y de administración */}
        {(yo?.rol.aprueba || yo?.rol.admin) && <div className="barra-grupo">Gestión</div>}
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
      </div>
    </aside>
  );
}
