// Carrusel de fotos (5/11, Franco): la foto actual, flechas a los lados, puntitos abajo y un contador «1/5». Lo usan la vista previa
// de Diseñar, Aprobación, el detalle de la pieza y Mis publicaciones. Sin frase ni logo encima: son las fotos tal cual.
import { useEffect, useState } from "react";

export default function Carrusel({ imagenes, ratio = "1 / 1", nombre = "Carrusel" }: { imagenes: string[]; ratio?: string; nombre?: string }) {
  const [i, setI] = useState(0);
  const n = imagenes.length;
  // si se quitan fotos mientras se mira la última, se vuelve a una que exista
  useEffect(() => {
    if (i > n - 1) setI(Math.max(0, n - 1));
  }, [i, n]);
  const actual = Math.min(i, Math.max(0, n - 1));
  return (
    <div className="carrusel" role="group" aria-roledescription="carrusel" aria-label={nombre} style={{ aspectRatio: ratio }}>
      <img src={imagenes[actual]} alt={`Foto ${actual + 1} de ${n}`} />
      <span className="carrusel-contador" aria-live="polite">
        {actual + 1}/{n}
      </span>
      <button type="button" className="carrusel-flecha anterior" aria-label="Foto anterior" disabled={actual === 0} onClick={() => setI(actual - 1)}>
        ‹
      </button>
      <button type="button" className="carrusel-flecha siguiente" aria-label="Foto siguiente" disabled={actual >= n - 1} onClick={() => setI(actual + 1)}>
        ›
      </button>
      <div className="carrusel-puntos">
        {imagenes.map((_, k) => (
          <button key={k} type="button" className={"carrusel-punto" + (k === actual ? " on" : "")} aria-label={`Ir a la foto ${k + 1}`} aria-current={k === actual ? "true" : undefined} onClick={() => setI(k)} />
        ))}
      </div>
    </div>
  );
}
