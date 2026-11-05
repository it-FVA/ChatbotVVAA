import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import "../ayuda.css";
import { todasLasAyudas } from "../ayuda";

// (5/11, Franco) Instructivo corto, una sección por pantalla. No se escribe acá: cada pantalla declara su ayuda con definirAyuda
// (ayuda/registro.ts) al lado de su código, y esta página las lee. Máximo 120 palabras por sección (lo verifica Ayuda.test.tsx).
// El id de cada sección es el nombre de la pantalla, el mismo que usa <LinkAyuda pantalla="…" />.

export const SI_ALGO_FALLA = {
  id: "si-algo-falla",
  titulo: "Si algo falla",
  pasos: [
    "Refrescá la página.",
    "Si la primera vez tarda, esperá: el asistente arranca solo en un minuto.",
    "Si sigue sin andar, avisale a Franco con lo que estabas haciendo.",
  ],
};

export default function Ayuda() {
  const { hash } = useLocation();
  const secciones = todasLasAyudas();

  // el link con ancla (/ayuda#recortes) baja a la sección, también cuando se llega desde otra pantalla
  useEffect(() => {
    if (!hash) return;
    document.getElementById(decodeURIComponent(hash.slice(1)))?.scrollIntoView?.({ block: "start" });
  }, [hash]);

  return (
    <div className="pagina ayuda">
      <header className="pagina-cabecera">
        <div>
          <h1>Ayuda</h1>
          <p className="suave">Cómo se usa cada pantalla, en pocos pasos.</p>
        </div>
      </header>

      <nav className="ayuda-indice" aria-label="Índice de la ayuda">
        {[...secciones.map(([id, d]) => ({ id, titulo: d.titulo })), SI_ALGO_FALLA].map((s) => (
          <a key={s.id} href={`#${s.id}`}>
            {s.titulo}
          </a>
        ))}
      </nav>

      {secciones.map(([id, s]) => (
        <section key={id} id={id} className="ayuda-seccion" aria-labelledby={`${id}-t`}>
          <h2 id={`${id}-t`}>{s.titulo}</h2>
          <p>{s.que}</p>
          {s.lista && (
            <ul className="ayuda-lista">
              {s.lista.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          )}
          <h3>Paso a paso</h3>
          <ol>
            {s.pasos.map((p) => (
              <li key={p.texto}>{p.texto}</li>
            ))}
          </ol>
        </section>
      ))}

      <section id={SI_ALGO_FALLA.id} className="ayuda-seccion" aria-labelledby="si-algo-falla-t">
        <h2 id="si-algo-falla-t">{SI_ALGO_FALLA.titulo}</h2>
        <ul>
          {SI_ALGO_FALLA.pasos.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
