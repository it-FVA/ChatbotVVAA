import { useCallback, useEffect, useState } from "react";
import { api, ErrorApi } from "../../api";
import { useSesion } from "../../App";
import type { Cambio, Usuario } from "../../tipos";
import { Icono } from "../../componentes/Iconos";
import Modal from "../../componentes/Modal";
import { Hueso } from "../../componentes/Comunes";
import { useToast } from "../../componentes/Toasts";

// Administración → Usuarios (22/10): tabla de cuentas con cambiar rol, renombrar (actualiza el historial), activar/desactivar,
// resetear la contraseña (temporal mostrada UNA vez, o «sin clave» para que la cree desde «Primera vez»), borrar y crear.
// La API protege al propio admin y al último admin activo; acá solo se deshabilitan los botones.
const ROLES = ["creador", "aprobador", "admin"] as const;
const ROL_TEXTO: Record<string, string> = { creador: "creador de contenido", aprobador: "aprobador", admin: "admin" };

type Accion = { tipo: "renombrar" | "clave" | "borrar"; u: Usuario } | { tipo: "nuevo" } | null;

function fecha(iso: string | null) {
  if (!iso) return "nunca";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", year: "2-digit" }) + " " + d.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
}

export default function Usuarios() {
  const { yo, setYo } = useSesion();
  const { avisar } = useToast();
  const [filas, setFilas] = useState<Usuario[] | null>(null);
  const [enSecrets, setEnSecrets] = useState<string[]>([]);
  const [cambios, setCambios] = useState<Cambio[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [accion, setAccion] = useState<Accion>(null);
  const [buscar, setBuscar] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const d = await api.adminUsuarios();
      setFilas(d.usuarios);
      setEnSecrets(d.en_secrets);
      setError(null);
      api.adminCambios().then(setCambios).catch(() => {});
    } catch (e) {
      setError(e instanceof ErrorApi ? e.message : "No pude leer los usuarios.");
      setFilas([]);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function mensaje(e: unknown) {
    return e instanceof ErrorApi ? e.message : "No pude conectarme con la API.";
  }

  async function editar(u: Usuario, datos: { rol?: string; activo?: boolean }) {
    setOcupado(u.id);
    try {
      const r = await api.adminEditar(u.id, datos);
      setFilas((fs) => fs!.map((f) => (f.id === u.id ? r.usuario : f)));
      avisar(datos.rol ? `${u.usuario} ahora es ${ROL_TEXTO[datos.rol]}.` : datos.activo ? `${u.usuario} activado.` : `${u.usuario} desactivado.`);
      api.adminCambios().then(setCambios).catch(() => {});
    } catch (e) {
      avisar(mensaje(e), "error");
    } finally {
      setOcupado(null);
    }
  }

  const soy = (u: Usuario) => u.usuario === yo?.usuario;
  const lista = (filas ?? []).filter((u) => {
    const q = buscar.trim().toLowerCase();
    return !q || [u.usuario, u.nombre, u.email, u.rol].some((x) => (x || "").toLowerCase().includes(q));
  });

  return (
    <>
      <div className="seccion-cabecera">
        <h2>
          <Icono nombre="usuarios" /> Usuarios {filas && <span className="suave chico">({filas.length})</span>}
        </h2>
        <div className="acciones">
          <label className="buscar">
            <Icono nombre="buscar" tam={16} />
            <input type="search" placeholder="Buscar por usuario, nombre o email" value={buscar} onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar usuarios" />
          </label>
          <button className="boton primario" onClick={() => setAccion({ tipo: "nuevo" })}>
            <Icono nombre="mas" tam={16} /> Nuevo usuario
          </button>
        </div>
      </div>
      {error && (
        <div className="aviso error" role="alert">
          <Icono nombre="alerta" tam={18} /> {error}
        </div>
      )}
      {filas === null ? (
        <div className="tarjeta" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <Hueso key={i} alto={38} style={{ marginBottom: 10 }} />
          ))}
        </div>
      ) : (
        <div className="tarjeta tabla-caja">
          <table className="tabla ancha">
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Nombre</th>
                <th>Email</th>
                <th>Rol</th>
                <th>Activo</th>
                <th>Último ingreso</th>
                <th>
                  <span className="visualmente-oculto">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {lista.map((u) => (
                <tr key={u.id} className={!u.activo ? "inactivo" : ""}>
                  <td data-col="Usuario">
                    <strong>{u.usuario}</strong>
                    {soy(u) && <span className="chip chico">vos</span>}
                    {!u.tiene_clave && (
                      <span className="chip chico suave" title="Entra con Google, o todavía no creó su contraseña desde «Primera vez»">
                        sin clave
                      </span>
                    )}
                    {u.clave_temporal && (
                      <span className="chip chico amarillo" title="Tiene una clave temporal: la cambia al entrar">
                        temporal
                      </span>
                    )}
                  </td>
                  <td data-col="Nombre" title={u.nombre ?? undefined}>
                    {u.nombre || <span className="suave">—</span>}
                  </td>
                  <td data-col="Email" title={u.email ?? undefined}>
                    {u.email || <span className="suave">—</span>}
                  </td>
                  <td data-col="Rol">
                    <select value={u.rol} onChange={(e) => editar(u, { rol: e.target.value })} disabled={soy(u) || ocupado === u.id} aria-label={`Rol de ${u.usuario}`} title={soy(u) ? "No podés cambiar tu propio rol" : undefined}>
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {ROL_TEXTO[r]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td data-col="Activo">
                    <label className="interruptor">
                      <input type="checkbox" checked={u.activo} onChange={(e) => editar(u, { activo: e.target.checked })} disabled={soy(u) || ocupado === u.id} aria-label={`${u.usuario} activo`} />
                      <span>{u.activo ? "sí" : "no"}</span>
                    </label>
                  </td>
                  <td data-col="Último ingreso" className="suave chico">
                    {fecha(u.ultimo_login)}
                  </td>
                  <td data-col="" className="celda-acciones">
                    <button className="boton sutil chico" onClick={() => setAccion({ tipo: "renombrar", u })} aria-label={`Renombrar a ${u.usuario}`} title="Cambiar el nombre de usuario (se actualiza en el historial)">
                      <Icono nombre="lapiz" tam={15} /> <span className="etiqueta">Renombrar</span>
                    </button>
                    <button className="boton sutil chico" onClick={() => setAccion({ tipo: "clave", u })} aria-label={`Resetear la contraseña de ${u.usuario}`} title="Resetear la contraseña">
                      <Icono nombre="regenerar" tam={15} /> <span className="etiqueta">Clave</span>
                    </button>
                    <button className="boton peligro sutil chico" onClick={() => setAccion({ tipo: "borrar", u })} disabled={soy(u)} aria-label={`Borrar a ${u.usuario}`} title={soy(u) ? "No podés borrar tu propia cuenta" : "Eliminar la cuenta"}>
                      <Icono nombre="tacho" tam={15} /> <span className="etiqueta">Borrar</span>
                    </button>
                  </td>
                </tr>
              ))}
              {lista.length === 0 && (
                <tr>
                  <td colSpan={7} className="suave" style={{ textAlign: "center", padding: 24 }}>
                    {buscar ? "Nadie coincide con la búsqueda." : "Todavía no hay usuarios en la tabla."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {enSecrets.length > 0 && (
        <div className="aviso" role="status">
          <Icono nombre="info" tam={18} />
          <span>
            Todavía entran por la lista vieja de la app (sin importar a la tabla): <strong>{enSecrets.join(", ")}</strong>. Se pasan con{" "}
            <code>python api/importar_usuarios.py</code>.
          </span>
        </div>
      )}
      {cambios.length > 0 && (
        <details className="tarjeta cambios">
          <summary>
            <Icono nombre="reloj" tam={16} /> Últimos cambios ({cambios.length})
          </summary>
          <ul>
            {cambios.slice(0, 30).map((c) => (
              <li key={c.id}>
                <span className="suave chico">{fecha(c.cuando)}</span> <strong>{c.quien}</strong> · {c.accion} · {c.usuario}
                {c.detalle && Object.keys(c.detalle).length > 0 && <span className="suave chico"> {JSON.stringify(c.detalle)}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}

      {accion?.tipo === "nuevo" && (
        <NuevoUsuario
          onCerrar={() => setAccion(null)}
          onHecho={(r) => {
            setFilas((fs) => [...(fs ?? []), r.usuario].sort((a, b) => a.usuario.localeCompare(b.usuario)));
            if (!r.clave_temporal) {
              setAccion(null);
              avisar(`Cuenta ${r.usuario.usuario} creada sin clave: la crea desde «¿Primera vez?» con su email.`);
            }
          }}
        />
      )}
      {accion?.tipo === "renombrar" && (
        <Renombrar
          u={accion.u}
          onCerrar={() => setAccion(null)}
          onHecho={(r, viejo) => {
            setFilas((fs) => fs!.map((f) => (f.id === r.usuario.id ? r.usuario : f)));
            const t = Object.entries(r.tablas)
              .filter(([, n]) => typeof n === "number" && n > 0)
              .map(([k, n]) => `${n} en ${k}`)
              .join(", ");
            avisar(`${viejo} ahora se llama ${r.usuario.usuario}.${t ? " Historial actualizado: " + t + "." : ""}`);
            if (r.sesion_propia && yo) setYo({ ...yo, usuario: r.usuario.usuario });
            setAccion(null);
          }}
        />
      )}
      {accion?.tipo === "clave" && (
        <ResetClave
          u={accion.u}
          onCerrar={() => setAccion(null)}
          onHecho={(modo) => {
            setFilas((fs) => fs!.map((f) => (f.id === accion.u.id ? { ...f, tiene_clave: modo === "temporal", clave_temporal: modo === "temporal" } : f)));
          }}
        />
      )}
      {accion?.tipo === "borrar" && (
        <Modal titulo={`¿Borrar la cuenta ${accion.u.usuario}?`} onCerrar={() => setAccion(null)} peligro>
          <p>
            La persona no va a poder entrar más. Sus conversaciones, recortes y publicaciones quedan con su nombre. Si solo querés que no entre por un tiempo, mejor <strong>desactivala</strong>.
          </p>
          <div className="acciones derecha">
            <button className="boton" onClick={() => setAccion(null)}>
              Cancelar
            </button>
            <button
              className="boton peligro"
              onClick={async () => {
                try {
                  await api.adminBorrar(accion.u.id);
                  setFilas((fs) => fs!.filter((f) => f.id !== accion.u.id));
                  avisar(`Cuenta ${accion.u.usuario} borrada.`);
                  setAccion(null);
                } catch (e) {
                  avisar(mensaje(e), "error");
                }
              }}
            >
              <Icono nombre="tacho" tam={16} /> Borrar la cuenta
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function ClaveTemporal({ clave, usuario }: { clave: string; usuario: string }) {
  const [copiada, setCopiada] = useState(false);
  return (
    <div className="clave-temporal">
      <p>
        Contraseña temporal de <strong>{usuario}</strong>. Se muestra <strong>una sola vez</strong>: pasásela por un canal seguro. Al entrar va a tener que elegir una propia.
      </p>
      <div className="clave-caja">
        <code>{clave}</code>
        <button
          className="boton chico"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(clave);
              setCopiada(true);
            } catch {
              /* sin portapapeles */
            }
          }}
        >
          {copiada ? "Copiada" : "Copiar"}
        </button>
      </div>
    </div>
  );
}

function NuevoUsuario({ onCerrar, onHecho }: { onCerrar: () => void; onHecho: (r: { usuario: Usuario; clave_temporal: string | null }) => void }) {
  const [usuario, setUsuario] = useState("");
  const [email, setEmail] = useState("");
  const [nombre, setNombre] = useState("");
  const [rol, setRol] = useState("creador");
  const [clave, setClave] = useState<"sin" | "temporal">("sin");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<{ usuario: Usuario; clave_temporal: string | null } | null>(null);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const r = await api.adminCrear({ usuario: usuario.trim().toLowerCase(), email: email.trim() || null, nombre: nombre.trim() || null, rol, clave });
      onHecho(r);
      if (r.clave_temporal) setResultado(r);
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal titulo={resultado ? "Cuenta creada" : "Nuevo usuario"} onCerrar={onCerrar}>
      {resultado ? (
        <>
          <ClaveTemporal clave={resultado.clave_temporal!} usuario={resultado.usuario.usuario} />
          <div className="acciones derecha">
            <button className="boton primario" onClick={onCerrar}>
              Listo
            </button>
          </div>
        </>
      ) : (
        <form className="formulario" onSubmit={crear}>
          <label>
            Usuario
            <input value={usuario} onChange={(e) => setUsuario(e.target.value.toLowerCase())} required pattern="[a-z0-9][a-z0-9._\-]{2,39}" title="De 3 a 40 caracteres: minúsculas, números, punto, guion o guion bajo" />
          </label>
          <label>
            Email <span className="suave chico">(necesario si va a crear su clave desde «Primera vez» o entrar con Google)</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Nombre
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </label>
          <label>
            Rol
            <select value={rol} onChange={(e) => setRol(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROL_TEXTO[r]}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="opciones">
            <legend>Contraseña</legend>
            <label className="radio">
              <input type="radio" name="clave" checked={clave === "sin"} onChange={() => setClave("sin")} />
              <span>
                <strong>La crea la persona</strong> desde «¿Primera vez? Creá tu cuenta», con su email (o entra con Google).
              </span>
            </label>
            <label className="radio">
              <input type="radio" name="clave" checked={clave === "temporal"} onChange={() => setClave("temporal")} />
              <span>
                <strong>Clave temporal</strong>: se la pasás vos y la cambia al entrar.
              </span>
            </label>
          </fieldset>
          {error && (
            <div className="aviso error" role="alert">
              <Icono nombre="alerta" tam={18} /> {error}
            </div>
          )}
          <div className="acciones derecha">
            <button type="button" className="boton" onClick={onCerrar}>
              Cancelar
            </button>
            <button type="submit" className="boton primario" disabled={enviando || !usuario.trim() || (clave === "sin" && !email.trim())}>
              {enviando ? "Creando…" : "Crear la cuenta"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function Renombrar({ u, onCerrar, onHecho }: { u: Usuario; onCerrar: () => void; onHecho: (r: { usuario: Usuario; tablas: Record<string, number | string>; sesion_propia?: boolean }, viejo: string) => void }) {
  const [nuevo, setNuevo] = useState(u.usuario);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const ok = /^[a-z0-9][a-z0-9._-]{2,39}$/.test(nuevo) && nuevo !== u.usuario;
  return (
    <Modal titulo={`Renombrar a ${u.usuario}`} onCerrar={onCerrar}>
      <form
        className="formulario"
        onSubmit={async (e) => {
          e.preventDefault();
          setEnviando(true);
          setError(null);
          try {
            onHecho(await api.adminRenombrar(u.id, nuevo), u.usuario);
          } catch (err) {
            setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
          } finally {
            setEnviando(false);
          }
        }}
      >
        <p className="suave chico">Cambia el nombre con el que entra. Sus conversaciones, publicaciones y recortes pasan al nombre nuevo, así no pierde el historial.</p>
        <label>
          Nombre de usuario nuevo
          <input value={nuevo} onChange={(e) => setNuevo(e.target.value.toLowerCase())} autoFocus required />
        </label>
        {error && (
          <div className="aviso error" role="alert">
            <Icono nombre="alerta" tam={18} /> {error}
          </div>
        )}
        <div className="acciones derecha">
          <button type="button" className="boton" onClick={onCerrar}>
            Cancelar
          </button>
          <button type="submit" className="boton primario" disabled={!ok || enviando}>
            {enviando ? "Renombrando…" : "Renombrar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ResetClave({ u, onCerrar, onHecho }: { u: Usuario; onCerrar: () => void; onHecho: (modo: "temporal" | "sin_clave") => void }) {
  const { avisar } = useToast();
  const [modo, setModo] = useState<"temporal" | "sin_clave">("temporal");
  const [temporal, setTemporal] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  return (
    <Modal titulo={temporal ? "Contraseña reseteada" : `Resetear la contraseña de ${u.usuario}`} onCerrar={onCerrar}>
      {temporal ? (
        <>
          <ClaveTemporal clave={temporal} usuario={u.usuario} />
          <div className="acciones derecha">
            <button className="boton primario" onClick={onCerrar}>
              Listo
            </button>
          </div>
        </>
      ) : (
        <form
          className="formulario"
          onSubmit={async (e) => {
            e.preventDefault();
            setEnviando(true);
            setError(null);
            try {
              const r = await api.adminResetClave(u.id, modo);
              onHecho(modo);
              if (r.clave_temporal) setTemporal(r.clave_temporal);
              else {
                avisar(`${u.usuario} quedó sin clave: la crea desde «¿Primera vez?» con ${u.email}.`);
                onCerrar();
              }
            } catch (err) {
              setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
            } finally {
              setEnviando(false);
            }
          }}
        >
          <fieldset className="opciones">
            <legend>Cómo</legend>
            <label className="radio">
              <input type="radio" name="modo" checked={modo === "temporal"} onChange={() => setModo("temporal")} />
              <span>
                <strong>Clave temporal</strong>: la ves una sola vez, se la pasás y la cambia al entrar.
              </span>
            </label>
            <label className="radio">
              <input type="radio" name="modo" checked={modo === "sin_clave"} onChange={() => setModo("sin_clave")} disabled={!u.email} />
              <span>
                <strong>Dejar sin clave</strong>: la crea desde «¿Primera vez? Creá tu cuenta» con su email{u.email ? ` (${u.email})` : ""}.
                {!u.email && <span className="suave chico"> Necesita tener un email cargado.</span>}
              </span>
            </label>
          </fieldset>
          {error && (
            <div className="aviso error" role="alert">
              <Icono nombre="alerta" tam={18} /> {error}
            </div>
          )}
          <div className="acciones derecha">
            <button type="button" className="boton" onClick={onCerrar}>
              Cancelar
            </button>
            <button type="submit" className="boton primario" disabled={enviando}>
              {enviando ? "Reseteando…" : "Resetear"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
