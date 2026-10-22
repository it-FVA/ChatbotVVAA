import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, ErrorApi } from "../api";
import { useSesion } from "../App";
import type { Yo } from "../tipos";

// Login con Google (21/10, noche): Google Identity Services dibuja el botón; al elegir cuenta devuelve un id_token que se manda a
// POST /login/google. La API lo verifica con GOOGLE_CLIENT_ID y admite el dominio de la Fundación (DOMINIO_FVA) o la tabla
// `autorizados`. El client id lo da GET /salud (no es secreto); sin él, el botón queda deshabilitado.
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string; auto_select?: boolean }) => void;
          renderButton: (el: HTMLElement, cfg: Record<string, string | number>) => void;
        };
      };
    };
  }
}

function cargarGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  return new Promise((ok, mal) => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = () => ok();
    s.onerror = () => mal(new Error("No pude cargar el login de Google."));
    document.head.appendChild(s);
  });
}

export default function Login() {
  const { yo, setYo } = useSesion();
  const nav = useNavigate();
  const loc = useLocation();
  const [usuario, setUsuario] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [clientId, setClientId] = useState<string | null>(null);
  const [gisListo, setGisListo] = useState(false);
  const botonGoogle = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.salud().then((s) => setClientId(s.google_client_id)).catch(() => setClientId(null));
  }, []);

  function entrar_ok(y: Yo) {
    setYo(y);
    const desde = (loc.state as { desde?: string } | null)?.desde;
    nav(desde && desde !== "/login" ? desde : "/recortes", { replace: true });
  }

  // Dibuja el botón oficial de Google cuando hay client id
  useEffect(() => {
    if (!clientId || !botonGoogle.current) return;
    let vivo = true;
    cargarGis()
      .then(() => {
        if (!vivo || !window.google || !botonGoogle.current) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          auto_select: false,
          callback: async (r) => {
            setError(null);
            setEnviando(true);
            try {
              entrar_ok(await api.loginGoogle(r.credential));
            } catch (err) {
              setError(err instanceof ErrorApi ? err.message : "No pude entrar con Google.");
            } finally {
              setEnviando(false);
            }
          },
        });
        window.google.accounts.id.renderButton(botonGoogle.current, { theme: "outline", size: "large", text: "signin_with", locale: "es", width: 330 });
        setGisListo(true);
      })
      .catch((e: Error) => setError(e.message));
    return () => {
      vivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  if (yo) return <Navigate to="/recortes" replace />;

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      entrar_ok(await api.login(usuario.trim(), clave));
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="pantalla-centro login">
      <form className="tarjeta login-caja" onSubmit={entrar}>
        <img src="/logo.png" alt="Vivir Agradecidos" className="login-logo" />
        <h1>Asistente de contenido</h1>
        <p className="suave">Entrá con tu usuario de siempre o con la cuenta de Google de la Fundación.</p>
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
        <div className="google-caja">
          <div ref={botonGoogle} style={{ display: gisListo ? "flex" : "none", justifyContent: "center" }} />
          {!gisListo && (
            <button
              type="button"
              className="boton"
              disabled
              title={clientId ? "Cargando el login de Google…" : "Todavía no está configurado: falta GOOGLE_CLIENT_ID en la API."}
            >
              <GoogleIcono /> Entrar con Google
            </button>
          )}
        </div>
        {clientId ? (
          <p className="suave chico">Entran las cuentas @viviragradecidos.org y las que un admin haya habilitado.</p>
        ) : (
          <p className="suave chico">El login con Google se habilita cuando la API tenga el proyecto de Google Cloud.</p>
        )}
        <p className="chico primera-vez">
          ¿Primera vez? <Link to="/primera-vez">Creá tu cuenta</Link>
        </p>
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
