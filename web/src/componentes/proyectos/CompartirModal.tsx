// «Compartir» (22/10): modal con buscador de personas (tabla usuarios, por nombre, usuario o mail), permiso ver / editar,
// y la lista de con quién ya está compartido (cambiar el permiso o sacar). Sirve para un proyecto o una conversación suelta.
import { useEffect, useRef, useState } from "react";
import { apiProyectos } from "../../apiProyectos";
import { ErrorApi } from "../../api";
import type { PersonaCompartida, UsuarioBuscado } from "../../tiposProyectos";
import { Icono } from "../Iconos";
import Modal from "../Modal";
import { useToast } from "../Toasts";

interface Props {
  tipo: "proyecto" | "conversacion";
  itemId: string;
  nombre: string;
  onCerrar: () => void;
  /** Se llama cuando cambia la lista (para refrescar contadores afuera). */
  onCambio?: () => void;
}

const PERMISO_TXT = { ver: "Solo ver", editar: "Puede editar" } as const;

export default function CompartirModal({ tipo, itemId, nombre, onCerrar, onCambio }: Props) {
  const { avisar } = useToast();
  const [con, setCon] = useState<PersonaCompartida[] | null>(null);
  const [dueno, setDueno] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<UsuarioBuscado[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [elegido, setElegido] = useState<UsuarioBuscado | null>(null);
  const [permiso, setPermiso] = useState<"ver" | "editar">("ver");
  const [guardando, setGuardando] = useState(false);
  const temporizador = useRef<number | null>(null);

  async function cargar() {
    try {
      const r = await apiProyectos.conQuien(tipo, itemId);
      setCon(r.con);
      setDueno(r.dueno);
      setError(null);
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer con quién está compartido.");
      setCon([]);
    }
  }
  useEffect(() => {
    cargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo, itemId]);

  // buscador con pausa de 250 ms
  useEffect(() => {
    if (elegido) return;
    if (temporizador.current) window.clearTimeout(temporizador.current);
    const texto = q.trim();
    if (!texto) {
      setResultados([]);
      return;
    }
    temporizador.current = window.setTimeout(async () => {
      setBuscando(true);
      try {
        const ya = new Set((con || []).map((c) => c.usuario));
        setResultados((await apiProyectos.buscarUsuarios(texto)).filter((u) => !ya.has(u.usuario)));
      } catch {
        setResultados([]);
      } finally {
        setBuscando(false);
      }
    }, 250);
    return () => {
      if (temporizador.current) window.clearTimeout(temporizador.current);
    };
  }, [q, elegido, con]);

  async function compartir() {
    if (!elegido) return;
    setGuardando(true);
    try {
      await apiProyectos.compartir(tipo, itemId, elegido.usuario, permiso);
      avisar(`Compartido con ${elegido.nombre || elegido.usuario} (${PERMISO_TXT[permiso].toLowerCase()}).`);
      setElegido(null);
      setQ("");
      setResultados([]);
      await cargar();
      onCambio?.();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude compartir.", "error");
    } finally {
      setGuardando(false);
    }
  }

  async function cambiarPermiso(p: PersonaCompartida, nuevo: "ver" | "editar") {
    try {
      await apiProyectos.compartir(tipo, itemId, p.usuario, nuevo);
      setCon((l) => (l || []).map((x) => (x.usuario === p.usuario ? { ...x, permiso: nuevo } : x)));
      onCambio?.();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude cambiar el permiso.", "error");
    }
  }

  async function sacar(p: PersonaCompartida) {
    try {
      await apiProyectos.descompartir(tipo, itemId, p.usuario);
      setCon((l) => (l || []).filter((x) => x.usuario !== p.usuario));
      avisar(`${p.nombre || p.usuario} ya no lo ve.`);
      onCambio?.();
    } catch (e) {
      avisar(e instanceof ErrorApi ? e.message : "No pude dejar de compartir.", "error");
    }
  }

  const queEs = tipo === "proyecto" ? "la carpeta" : "la conversación";
  return (
    <Modal titulo={`Compartir ${queEs}`} onCerrar={onCerrar} ancho={500}>
      <p style={{ marginTop: 0 }}>
        <strong>{nombre}</strong>
      </p>
      {error && <div className="aviso error chico">{error}</div>}
      {dueno ? (
        <div className="compartir-alta">
          <div className="compartir-buscar">
            {elegido ? (
              <div className="compartir-elegido">
                <span className="avatar-letra" aria-hidden="true">
                  {(elegido.nombre || elegido.usuario).slice(0, 1).toUpperCase()}
                </span>
                <span>
                  <strong>{elegido.nombre || elegido.usuario}</strong> <span className="suave chico">{elegido.email || elegido.usuario}</span>
                </span>
                <button type="button" className="boton sutil chico icono-solo" onClick={() => setElegido(null)} aria-label="Elegir otra persona">
                  <Icono nombre="cruz" tam={14} />
                </button>
              </div>
            ) : (
              <div className="buscar" style={{ maxWidth: "none" }}>
                <Icono nombre="buscar" tam={16} />
                <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre, usuario o mail" aria-label="Buscar persona" autoFocus />
              </div>
            )}
            {!elegido && (q.trim() || buscando) && (
              <ul className="compartir-resultados" role="listbox" aria-label="Personas">
                {buscando && resultados.length === 0 && <li className="suave chico">Buscando…</li>}
                {!buscando && resultados.length === 0 && <li className="suave chico">No encontré a nadie con ese nombre en la tabla de usuarios.</li>}
                {resultados.map((u) => (
                  <li key={u.usuario} role="option" aria-selected={false}>
                    <button type="button" className="compartir-persona" onClick={() => setElegido(u)}>
                      <span className="avatar-letra" aria-hidden="true">
                        {(u.nombre || u.usuario).slice(0, 1).toUpperCase()}
                      </span>
                      <span>
                        <strong>{u.nombre || u.usuario}</strong>
                        <span className="suave chico"> · {u.email || u.usuario}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="compartir-permiso">
            <label className="chico suave" htmlFor="permiso">
              Permiso
            </label>
            <select id="permiso" value={permiso} onChange={(e) => setPermiso(e.target.value as "ver" | "editar")}>
              <option value="ver">Solo ver</option>
              <option value="editar">Puede editar{tipo === "proyecto" ? " (agregar, sacar, renombrar)" : " (escribir en el chat)"}</option>
            </select>
            <button type="button" className="boton primario" onClick={compartir} disabled={!elegido || guardando}>
              <Icono nombre="compartir" tam={16} /> {guardando ? "…" : "Compartir"}
            </button>
          </div>
        </div>
      ) : (
        <p className="suave chico">Solo quien lo creó puede compartirlo.</p>
      )}

      <h4 className="compartir-sub">Con quién está compartido</h4>
      {con === null && <p className="suave chico">Cargando…</p>}
      {con && con.length === 0 && <p className="suave chico">Todavía con nadie.</p>}
      {con && con.length > 0 && (
        <ul className="compartir-lista">
          {con.map((p) => (
            <li key={p.usuario}>
              <span className="avatar-letra" aria-hidden="true">
                {(p.nombre || p.usuario).slice(0, 1).toUpperCase()}
              </span>
              <span className="compartir-quien">
                <strong>{p.nombre || p.usuario}</strong>
                <span className="suave chico">{p.usuario}</span>
              </span>
              {dueno ? (
                <>
                  <select value={p.permiso} onChange={(e) => cambiarPermiso(p, e.target.value as "ver" | "editar")} aria-label={`Permiso de ${p.usuario}`}>
                    <option value="ver">Solo ver</option>
                    <option value="editar">Puede editar</option>
                  </select>
                  <button type="button" className="boton sutil peligro chico icono-solo" onClick={() => sacar(p)} aria-label={`Dejar de compartir con ${p.usuario}`} title="Dejar de compartir">
                    <Icono nombre="cruz" tam={15} />
                  </button>
                </>
              ) : (
                <span className="chip suave">{PERMISO_TXT[p.permiso]}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
