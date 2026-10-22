import { useEffect, useState } from "react";
import { api, ErrorApi } from "../../api";
import type { Autorizado } from "../../tipos";
import { Icono } from "../../componentes/Iconos";
import Modal from "../../componentes/Modal";
import { Hueso } from "../../componentes/Comunes";
import { useToast } from "../../componentes/Toasts";

// Administración → Lista blanca (22/10): emails de fuera del dominio que pueden crear cuenta (o entrar con Google), con el rol
// que van a tener y una nota. Los del dominio de la Fundación entran siempre y no hace falta listarlos.
const ROLES = ["creador", "aprobador", "admin"] as const;
const ROL_TEXTO: Record<string, string> = { creador: "creador de contenido", aprobador: "aprobador", admin: "admin" };

export default function ListaBlanca() {
  const { avisar } = useToast();
  const [filas, setFilas] = useState<Autorizado[] | null>(null);
  const [dominio, setDominio] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [editando, setEditando] = useState<Autorizado | "nuevo" | null>(null);
  const [aBorrar, setABorrar] = useState<Autorizado | null>(null);

  useEffect(() => {
    api
      .listaBlanca()
      .then((d) => {
        setFilas(d.emails);
        setDominio(d.dominio);
      })
      .catch((e) => {
        setError(e instanceof ErrorApi ? e.message : "No pude leer la lista.");
        setFilas([]);
      });
  }, []);

  return (
    <>
      <div className="seccion-cabecera">
        <h2>
          <Icono nombre="check" /> Lista blanca {filas && <span className="suave chico">({filas.length})</span>}
        </h2>
        <button className="boton primario" onClick={() => setEditando("nuevo")}>
          <Icono nombre="mas" tam={16} /> Agregar email
        </button>
      </div>
      <p className="suave">
        {dominio ? (
          <>
            Las cuentas <strong>@{dominio}</strong> pueden crear su cuenta y entrar con Google siempre. Cualquier otro email, solo si está en esta lista, con el rol que diga acá.
          </>
        ) : (
          "Solo los emails de esta lista pueden crear cuenta o entrar con Google (no hay dominio de la Fundación configurado: DOMINIO_FVA)."
        )}
      </p>
      {error && (
        <div className="aviso error" role="alert">
          <Icono nombre="alerta" tam={18} /> {error}
        </div>
      )}
      {filas === null ? (
        <div className="tarjeta" aria-busy="true">
          {[0, 1].map((i) => (
            <Hueso key={i} alto={38} style={{ marginBottom: 10 }} />
          ))}
        </div>
      ) : (
        <div className="tarjeta tabla-caja">
          <table className="tabla">
            <thead>
              <tr>
                <th>Email</th>
                <th>Rol al entrar</th>
                <th>Nota</th>
                <th>Agregado por</th>
                <th>
                  <span className="visualmente-oculto">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filas.map((a) => (
                <tr key={a.email}>
                  <td data-col="Email">
                    <strong>{a.email}</strong>
                  </td>
                  <td data-col="Rol">{ROL_TEXTO[a.rol] ?? a.rol}</td>
                  <td data-col="Nota">{a.nota || <span className="suave">—</span>}</td>
                  <td data-col="Agregado por" className="suave chico">
                    {a.agregado_por || "—"}
                  </td>
                  <td className="celda-acciones">
                    <button className="boton sutil chico" onClick={() => setEditando(a)} aria-label={`Editar ${a.email}`} title="Editar el rol o la nota">
                      <Icono nombre="lapiz" tam={15} /> <span className="etiqueta">Editar</span>
                    </button>
                    <button className="boton peligro sutil chico" onClick={() => setABorrar(a)} aria-label={`Quitar ${a.email}`} title="Quitar de la lista">
                      <Icono nombre="tacho" tam={15} /> <span className="etiqueta">Quitar</span>
                    </button>
                  </td>
                </tr>
              ))}
              {filas.length === 0 && (
                <tr>
                  <td colSpan={5} className="suave" style={{ textAlign: "center", padding: 24 }}>
                    La lista está vacía. {dominio ? `Por ahora entran solo las cuentas @${dominio}.` : ""}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {editando && (
        <Editar
          fila={editando === "nuevo" ? null : editando}
          onCerrar={() => setEditando(null)}
          onHecho={(f) => {
            setFilas((fs) => {
              const resto = (fs ?? []).filter((x) => x.email !== f.email);
              return [f, ...resto];
            });
            avisar(editando === "nuevo" ? `${f.email} agregado como ${ROL_TEXTO[f.rol]}.` : `${f.email} actualizado.`);
            setEditando(null);
          }}
        />
      )}
      {aBorrar && (
        <Modal titulo={`¿Quitar ${aBorrar.email} de la lista?`} onCerrar={() => setABorrar(null)} peligro>
          <p>No va a poder crear cuenta ni entrar con Google por primera vez. Si ya tiene cuenta, esa cuenta sigue (desactivala desde Usuarios).</p>
          <div className="acciones derecha">
            <button className="boton" onClick={() => setABorrar(null)}>
              Cancelar
            </button>
            <button
              className="boton peligro"
              onClick={async () => {
                try {
                  await api.listaBlancaBaja(aBorrar.email);
                  setFilas((fs) => fs!.filter((x) => x.email !== aBorrar.email));
                  avisar(`${aBorrar.email} quitado de la lista.`);
                  setABorrar(null);
                } catch (e) {
                  avisar(e instanceof ErrorApi ? e.message : "No pude conectarme con la API.", "error");
                }
              }}
            >
              <Icono nombre="tacho" tam={16} /> Quitar
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function Editar({ fila, onCerrar, onHecho }: { fila: Autorizado | null; onCerrar: () => void; onHecho: (f: Autorizado) => void }) {
  const [email, setEmail] = useState(fila?.email ?? "");
  const [rol, setRol] = useState(fila?.rol ?? "creador");
  const [nota, setNota] = useState(fila?.nota ?? "");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  return (
    <Modal titulo={fila ? `Editar ${fila.email}` : "Agregar un email a la lista blanca"} onCerrar={onCerrar}>
      <form
        className="formulario"
        onSubmit={async (e) => {
          e.preventDefault();
          setEnviando(true);
          setError(null);
          try {
            const r = await api.listaBlancaAlta(email.trim().toLowerCase(), rol, nota.trim());
            onHecho(r.fila ?? { email: email.trim().toLowerCase(), rol, nota: nota.trim() || null, agregado_por: null, creado: null });
          } catch (err) {
            setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
          } finally {
            setEnviando(false);
          }
        }}
      >
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={!!fila} autoFocus={!fila} required />
        </label>
        <label>
          Rol con el que va a entrar
          <select value={rol} onChange={(e) => setRol(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROL_TEXTO[r]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Nota <span className="suave chico">(quién es, para qué)</span>
          <input value={nota} onChange={(e) => setNota(e.target.value)} autoFocus={!!fila} />
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
          <button type="submit" className="boton primario" disabled={enviando || !email.trim()}>
            {enviando ? "Guardando…" : fila ? "Guardar" : "Agregar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
