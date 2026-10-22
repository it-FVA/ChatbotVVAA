import { useState } from "react";
import { api, ErrorApi } from "../api";
import { useSesion } from "../App";
import { Icono } from "../componentes/Iconos";
import { useToast } from "../componentes/Toasts";

// Mi cuenta (22/10): datos de la sesión y «Cambiar mi contraseña» (POST /cuentas/clave). Si la clave es temporal
// (la puso un admin), App redirige acá hasta que se cambie.
export default function Cuenta() {
  const { yo, setYo } = useSesion();
  const { avisar } = useToast();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [nueva2, setNueva2] = useState("");
  const [ver, setVer] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  if (!yo) return null;

  const reglas = { largo: nueva.length >= 8, mezcla: /[a-zA-Z]/.test(nueva) && /[^a-zA-Z]/.test(nueva), iguales: nueva.length > 0 && nueva === nueva2, distinta: nueva !== actual };
  const listo = actual && reglas.largo && reglas.mezcla && reglas.iguales && reglas.distinta;
  const puede = yo.en_tabla && yo.tiene_clave;

  async function cambiar(e: React.FormEvent) {
    e.preventDefault();
    if (!listo) return;
    setError(null);
    setEnviando(true);
    try {
      await api.cambiarClave(actual, nueva);
      setActual("");
      setNueva("");
      setNueva2("");
      setYo({ ...yo!, debe_cambiar_clave: false });
      avisar("Contraseña cambiada.");
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : "No pude conectarme con la API.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="pagina estrecha">
      <header className="pagina-cabecera">
        <div>
          <h1>Mi cuenta</h1>
          <p className="suave">Tus datos y tu contraseña.</p>
        </div>
      </header>
      {yo.debe_cambiar_clave && (
        <div className="aviso" role="alert">
          <Icono nombre="alerta" tam={18} /> Entraste con una contraseña temporal. Elegí una propia para seguir.
        </div>
      )}
      <section className="tarjeta datos-cuenta">
        <dl>
          <dt>Usuario</dt>
          <dd>{yo.usuario}</dd>
          <dt>Nombre</dt>
          <dd>{yo.nombre || <span className="suave">sin cargar</span>}</dd>
          <dt>Email</dt>
          <dd>{yo.email || <span className="suave">sin cargar</span>}</dd>
          <dt>Rol</dt>
          <dd>{yo.rol.nombre}</dd>
        </dl>
        {!yo.en_tabla && <p className="suave chico">Tu usuario todavía está en la lista vieja de la app: cuando un admin corra la importación vas a poder cambiar la contraseña desde acá.</p>}
      </section>
      <section className="tarjeta">
        <h2>
          <Icono nombre="lapiz" /> Cambiar mi contraseña
        </h2>
        {!puede ? (
          <p className="suave">{yo.en_tabla ? "Tu cuenta entra con Google y no tiene contraseña. Si querés una, creala desde «¿Primera vez?» con tu email." : "Todavía no se puede cambiar desde acá."}</p>
        ) : (
          <form className="formulario" onSubmit={cambiar}>
            <label>
              Contraseña actual
              <input type={ver ? "text" : "password"} value={actual} onChange={(e) => setActual(e.target.value)} autoComplete="current-password" required />
            </label>
            <label>
              Contraseña nueva
              <span className="campo-con-boton">
                <input type={ver ? "text" : "password"} value={nueva} onChange={(e) => setNueva(e.target.value)} autoComplete="new-password" required />
                <button type="button" className="boton sutil chico icono-solo" onClick={() => setVer((v) => !v)} aria-label={ver ? "Ocultar" : "Mostrar"} aria-pressed={ver}>
                  <Icono nombre="ojo" tam={16} />
                </button>
              </span>
            </label>
            <label>
              Repetí la nueva
              <input type={ver ? "text" : "password"} value={nueva2} onChange={(e) => setNueva2(e.target.value)} autoComplete="new-password" required />
            </label>
            <ul className="reglas" aria-label="Requisitos">
              <li className={reglas.largo ? "ok" : ""}>Al menos 8 caracteres</li>
              <li className={reglas.mezcla ? "ok" : ""}>Letras y números (o signos)</li>
              <li className={reglas.iguales ? "ok" : ""}>Las dos iguales</li>
              <li className={nueva && reglas.distinta ? "ok" : ""}>Distinta de la actual</li>
            </ul>
            {error && (
              <div className="aviso error" role="alert">
                <Icono nombre="alerta" tam={18} /> {error}
              </div>
            )}
            <div className="acciones">
              <button type="submit" className="boton primario" disabled={enviando || !listo}>
                {enviando ? "Guardando…" : "Guardar la contraseña"}
              </button>
            </div>
          </form>
        )}
      </section>
    </div>
  );
}
