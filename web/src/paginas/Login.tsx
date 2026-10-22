import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useSesion } from "../App";

export default function Login() {
  const { yo, setYo } = useSesion();
  const nav = useNavigate();
  const loc = useLocation();
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [google, setGoogle] = useState(false);

  useEffect(() => {
    api.salud().then((s) => setGoogle(s.login_google)).catch(() => setGoogle(false));
  }, []);

  if (yo) return <Navigate to="/recortes" replace />;

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const y = await api.login(usuario.trim(), clave);
      setYo(y);
      const desde = (loc.state as { desde?: string } | null)?.desde;
      nav(desde && desde !== "/login" ? desde : "/recortes", { replace: true });
    } catch (err) {
      const m = err instanceof ErrorApi ? err.message : "No pude conectarme con la API.";
      setError(m);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="pantalla-centro login">
      <form className="tarjeta login-caja" onSubmit={entrar}>
        <img src="/logo.png" alt="Vivir Agradecidos" className="login-logo" />
        <h1>Asistente de contenido</h1>
        <p className="suave">Entrá con tu usuario de siempre.</p>
        <label>
          Usuario
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="username" autoFocus required />
        </label>
        <label>
          Contraseña
          <input type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="current-password" required />
        </label>
        {error && <div className="aviso error">{error}</div>}
        <button type="submit" className="boton primario" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        <div className="separador">o</div>
        <button
          type="button"
          className="boton"
          disabled={!google}
          title={google ? "Entrar con la cuenta de Google de la Fundación" : "Todavía no está configurado: falta el proyecto de Google Cloud (GOOGLE_CLIENT_ID)."}
        >
          <GoogleIcono /> Entrar con Google
        </button>
        {!google && <p className="suave chico">El login con Google se habilita cuando esté el proyecto de Google Cloud.</p>}
      </form>
    </div>
  );
}

function GoogleIcono() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true" style={{ verticalAlign: "-3px", marginRight: 6 }}>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.5 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.3l7.8 6C12.3 13.6 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4 7.1-10 7.1-17.5z" />
      <path fill="#FBBC05" d="M10.4 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.8-6C.9 16.5 0 20.1 0 24s.9 7.5 2.6 10.7l7.8-6z" />
      <path fill="#34A853" d="M24 48c6.2 0 11.6-2 15.4-5.6l-7.5-5.8c-2.1 1.4-4.8 2.3-7.9 2.3-6.3 0-11.7-4.1-13.6-9.8l-7.8 6C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}
