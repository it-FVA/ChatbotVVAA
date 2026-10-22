// «Compartidos conmigo» (22/10): las carpetas y las conversaciones sueltas que otras personas compartieron con esta cuenta.
// Una carpeta abre la vista grande; una conversación abre el chat (en modo lectura o edición según el permiso).
// «Dejar de ver» saca a la persona de la lista de compartidos (api DELETE /compartidos/{tipo}/{id}/{yo}).
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ErrorApi } from "../api";
import { apiProyectos } from "../apiProyectos";
import { useSesion } from "../App";
import type { CompartidosConmigo } from "../tiposProyectos";
import { Icono } from "../componentes/Iconos";
import { Hueso } from "../componentes/Comunes";
import { useToast } from "../componentes/Toasts";
import { etiqueta, useProyectos } from "../componentes/proyectos/ProyectosContexto";
import { relativa } from "../util/fechas";
import "../proyectos.css";

export default function Compartidos() {
  const { yo } = useSesion();
  const { avisar } = useToast();
  const nav = useNavigate();
  const { recargar } = useProyectos();
  const [datos, setDatos] = useState<CompartidosConmigo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      setDatos(await apiProyectos.conmigo());
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer lo compartido con vos.");
      setDatos({ proyectos: [], conversaciones: [] });
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  async function dejar(tipo: "proyecto" | "conversacion", id: string, nombre: string) {
    if (!yo) return;
    try {
      await apiProyectos.descompartir(tipo, id, yo.usuario);
      avisar(`Ya no ves «${nombre}».`);
      await Promise.all([cargar(), recargar()]);
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude sacarlo.", "error");
    }
  }

  const vacio = datos && datos.proyectos.length === 0 && datos.conversaciones.length === 0;
  return (
    <div className="pagina">
      <header className="pagina-cabecera">
        <h1>Compartidos conmigo</h1>
        <p className="suave">Carpetas y conversaciones que otras personas del equipo compartieron con vos. Lo que te compartieron «para ver» lo abrís sin poder cambiarlo.</p>
      </header>
      {error && <div className="aviso error">{error}</div>}
      {datos === null && (
        <div className="drive-grilla" aria-busy="true">
          {[1, 2, 3].map((i) => (
            <div key={i} className="ficha esqueleto">
              <Hueso ancho="100%" alto={90} radio={8} />
              <Hueso ancho="70%" alto={14} style={{ marginTop: 10 }} />
            </div>
          ))}
        </div>
      )}
      {vacio && (
        <div className="vacio drive-vacio" role="status">
          <Icono nombre="compartir" tam={42} style={{ color: "var(--amarillo-oscuro)" }} />
          <h3>Todavía nadie compartió nada con vos</h3>
          <p className="suave">Cuando alguien comparta una carpeta o una conversación, aparece acá y en el árbol de proyectos del chat.</p>
          <div className="acciones" style={{ justifyContent: "center" }}>
            <Link className="boton" to="/proyectos">
              <Icono nombre="carpeta" /> Ir a mis proyectos
            </Link>
          </div>
        </div>
      )}
      {datos && datos.proyectos.length > 0 && (
        <section aria-label="Carpetas compartidas">
          <h2 className="drive-seccion">Carpetas</h2>
          <div className="drive-grilla">
            {datos.proyectos.map((p) => (
              <div key={p.id} className="ficha carpeta" role="link" tabIndex={0} onClick={() => nav(`/proyectos/${p.id}`)} onKeyDown={(e) => e.key === "Enter" && nav(`/proyectos/${p.id}`)}>
                <div className="ficha-mini carpeta-grande" style={{ color: p.color || "var(--amarillo-oscuro)" }}>
                  {p.emoji ? <span className="ficha-emoji">{p.emoji}</span> : <Icono nombre="carpeta" tam={54} />}
                </div>
                <div className="ficha-pie">
                  <span className="ficha-nombre">{p.nombre}</span>
                  <span className="ficha-sub suave">
                    de {p.compartido_por} · {p.permiso === "ver" ? "solo ver" : "podés editar"} · {p.n_items ?? 0} elem.
                  </span>
                </div>
                <button type="button" className="boton sutil chico icono-solo ficha-menu" onClick={(e) => (e.stopPropagation(), dejar("proyecto", p.id, etiqueta(p)))} aria-label={`Dejar de ver ${p.nombre}`} title="Dejar de ver">
                  <Icono nombre="cruz" tam={15} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
      {datos && datos.conversaciones.length > 0 && (
        <section aria-label="Conversaciones compartidas">
          <h2 className="drive-seccion">Conversaciones</h2>
          <div className="drive-lista">
            {datos.conversaciones.map((c) => (
              <div key={c.id} className="fila" role="link" tabIndex={0} onClick={() => nav(`/chat/${c.id}`)} onKeyDown={(e) => e.key === "Enter" && nav(`/chat/${c.id}`)}>
                <span />
                <span className="fila-nombre">
                  <Icono nombre="chat" tam={18} style={{ color: "var(--verde)" }} /> {c.titulo}
                </span>
                <span className="suave">
                  de {c.compartido_por} · {c.permiso === "ver" ? "solo lectura" : "podés escribir"}
                </span>
                <span className="suave">{relativa(c.actualizado, "es")}</span>
                <button type="button" className="boton sutil chico icono-solo" onClick={(e) => (e.stopPropagation(), dejar("conversacion", c.id, c.titulo))} aria-label={`Dejar de ver ${c.titulo}`} title="Dejar de ver">
                  <Icono nombre="cruz" tam={15} />
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
