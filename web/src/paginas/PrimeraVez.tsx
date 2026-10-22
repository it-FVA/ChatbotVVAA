import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useSesion } from "../App";
import { Icono } from "../componentes/Iconos";

// «¿Primera vez? Creá tu cuenta» (22/10). Paso 1: email → POST /cuentas/verificar dice si puede (dominio de la Fundación o
// lista blanca) y si ya hay una cuenta «sin clave» con ese email (la creó un admin). Paso 2: usuario y contraseña →
// POST /cuentas/primera-vez crea la fila (o le pone clave a la existente) y deja la sesión iniciada.
// Sin verificación por mail (no hay servicio de mail): pendiente.
export default function PrimeraVez() {
  const { yo, setYo } = useSesion();
  const nav = useNavigate();
  const [paso, setPaso] = useState<1 | 2>(1);
  const [email, setEmail] = useState("");
  const [usuarioFijo, setUsuarioFijo] = useState<string | null>(null);
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [clave2, setClave2] = useState("");
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  if (yo) return <Navigate to="/recortes" replace />;

  async function verificar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const r = await api.verificarEmail(email.trim());
      if (r.mensaje) {
        setError(r.mensaje);
        return;
      }
      setUsuarioFijo(r.usuario);
      if (!r.usuario) setUsuario(email.trim().toLowerCase().split("@")[0].replace(/[^a-z0-9._-]/g, ""));
      setPaso(2);
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(false);
    }
  }

  const reglas = {
    largo: clave.length >= 8,
    mezcla: /[a-zA-Z]/.test(clave) && /[^a-zA-Z]/.test(clave),
    iguales: clave.length > 0 && clave === clave2,
  };
  const usuarioOk = usuarioFijo ? true : /^[a-z0-9][a-z0-9._-]{2,39}$/.test(usuario);
  const listo = usuarioOk && reglas.largo && reglas.mezcla && reglas.iguales;

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    if (!listo) return;
    setError(null);
    setEnviando(true);
    try {
      const y = await api.primeraVez(email.trim(), usuarioFijo ?? usuario, clave);
      setYo(y);
      nav("/recortes", { replace: true });
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="pantalla-centro login">
      <form className="tarjeta login-caja" onSubmit={paso === 1 ? verificar : crear}>
        <img src="/logo.png" alt="Vivir Agradecidos" className="login-logo" />
        <h1>Creá tu cuenta</h1>
        <ol className="pasos" aria-label="Pasos">
          <li className={paso === 1 ? "activo" : "hecho"}>Tu email</li>
          <li className={paso === 2 ? "activo" : ""}>Usuario y contraseña</li>
        </ol>
        {paso === 1 ? (
          <>
            <p className="suave">Pueden crear cuenta las personas con email de la Fundación y las que un admin haya habilitado.</p>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" autoFocus required />
            </label>
            {error && (
              <div className="aviso error" role="alert">
                <Icono nombre="alerta" tam={18} /> {error}
              </div>
            )}
            <button type="submit" className="boton primario" disabled={enviando || !email.trim()}>
              {enviando ? "Verificando…" : "Continuar"}
            </button>
          </>
        ) : (
          <>
            <p className="suave">
              <strong>{email.trim().toLowerCase()}</strong> puede crear su cuenta.
              {usuarioFijo && " Un admin ya te dejó el usuario armado: solo elegí tu contraseña."}
            </p>
            <label>
              Usuario
              <input
                value={usuarioFijo ?? usuario}
                onChange={(e) => setUsuario(e.target.value.toLowerCase())}
                autoComplete="username"
                disabled={!!usuarioFijo}
                autoFocus={!usuarioFijo}
                required
                aria-describedby="ayuda-usuario"
              />
              <span id="ayuda-usuario" className={"chico " + (usuario && !usuarioOk && !usuarioFijo ? "rojo" : "suave")}>
                De 3 a 40 caracteres: minúsculas, números, punto, guion o guion bajo. Es el nombre con el que vas a entrar.
              </span>
            </label>
            <label>
              Contraseña
              <span className="campo-con-boton">
                <input type={verClave ? "text" : "password"} value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="new-password" autoFocus={!!usuarioFijo} required />
                <button type="button" className="boton sutil chico icono-solo" onClick={() => setVerClave((v) => !v)} aria-label={verClave ? "Ocultar la contraseña" : "Mostrar la contraseña"} aria-pressed={verClave}>
                  <Icono nombre="ojo" tam={16} />
                </button>
              </span>
            </label>
            <label>
              Repetí la contraseña
              <input type={verClave ? "text" : "password"} value={clave2} onChange={(e) => setClave2(e.target.value)} autoComplete="new-password" required />
            </label>
            <ul className="reglas" aria-label="Requisitos de la contraseña">
              <li className={reglas.largo ? "ok" : ""}>Al menos 8 caracteres</li>
              <li className={reglas.mezcla ? "ok" : ""}>Letras y números (o signos)</li>
              <li className={reglas.iguales ? "ok" : ""}>Las dos iguales</li>
            </ul>
            {error && (
              <div className="aviso error" role="alert">
                <Icono nombre="alerta" tam={18} /> {error}
              </div>
            )}
            <button type="submit" className="boton primario" disabled={enviando || !listo}>
              {enviando ? "Creando…" : "Crear mi cuenta y entrar"}
            </button>
            <button type="button" className="boton sutil" onClick={() => { setPaso(1); setError(null); }}>
              Cambiar el email
            </button>
          </>
        )}
        <p className="suave chico">
          ¿Ya tenés cuenta? <Link to="/login">Entrá</Link>
        </p>
      </form>
    </div>
  );
}
