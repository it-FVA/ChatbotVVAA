// Controles de estilo de los subtítulos (los mismos que «Editar recorte → Estilo» en Streamlit, con las listas de
// recortar_clip que llegan por GET /recortes/opciones), tres presets con nombre y el CSS que imita a libass sobre el reproductor.
import type { CSSProperties } from "react";
import type { Estilo, Opciones } from "../tipos";
import { Icono } from "./Iconos";

/** Presets: solo se ofrecen si sus valores existen en las listas de la API (así un cambio en recortar_clip no rompe nada). */
export function presets(op: Opciones): { nombre: string; descripcion: string; estilo: Estilo }[] {
  const base = op.estilo_equipo ?? op.estilo_defecto;
  const candidatos: { nombre: string; descripcion: string; estilo: Estilo }[] = [
    { nombre: "El de la Fundación", descripcion: op.estilo_equipo ? "El estilo por defecto que fijó el equipo" : "El estilo por defecto", estilo: base },
    {
      nombre: "Negrita amarilla",
      descripcion: "Letras amarillas en negrita, con la sombra oscura de siempre",
      estilo: { ...base, tipografia: "Raleway", color: "amarillo de la marca", fondo: "sombra oscura", negrita: true },
    },
    { nombre: "Caja negra", descripcion: "Letras blancas sobre una caja negra casi opaca", estilo: { ...base, tipografia: "Raleway", color: "blanco", fondo: "caja negra", negrita: false } },
  ];
  return candidatos.filter((c) => op.tipografias.includes(c.estilo.tipografia) && c.estilo.color in op.colores && c.estilo.fondo in op.fondos && c.estilo.tamano in op.tamanos && op.posiciones.includes(c.estilo.posicion));
}

const igual = (a: Estilo, b: Estilo) => (["tipografia", "tamano", "color", "fondo", "negrita", "posicion"] as const).every((k) => a[k] === b[k]);

export function ControlesEstilo({ estilo, opciones, onCambio }: { estilo: Estilo; opciones: Opciones; onCambio: (e: Estilo) => void }) {
  const set = (k: keyof Estilo, v: string | boolean) => onCambio({ ...estilo, [k]: v });
  const lista = presets(opciones);
  return (
    <div className="estilo">
      <div className="presets" role="group" aria-label="Estilos listos">
        {lista.map((pr) => {
          const activo = igual(pr.estilo, estilo);
          const muestra = cssSubtitulo(pr.estilo, opciones, "vertical", 120);
          return (
            <button key={pr.nombre} type="button" className={"preset" + (activo ? " activo" : "")} onClick={() => onCambio(pr.estilo)} title={pr.descripcion} aria-pressed={activo}>
              <span className="preset-muestra">
                <span style={{ ...muestra.texto, fontSize: 11, padding: "2px 6px" }}>Aa gratitud</span>
              </span>
              <span className="preset-nombre">
                {activo && <Icono nombre="check" tam={13} />}
                {pr.nombre}
              </span>
            </button>
          );
        })}
      </div>
      <div className="estilo-controles">
        <label>
          Tipografía
          <select value={estilo.tipografia} onChange={(e) => set("tipografia", e.target.value)} title="Raleway es la de la Fundación.">
            {opciones.tipografias.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Tamaño
          <select value={estilo.tamano} onChange={(e) => set("tamano", e.target.value)}>
            {Object.keys(opciones.tamanos).map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Color del texto
          <select value={estilo.color} onChange={(e) => set("color", e.target.value)}>
            {Object.keys(opciones.colores).map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Fondo o borde
          <select value={estilo.fondo} onChange={(e) => set("fondo", e.target.value)} title="«sombra oscura» es lo de siempre: una caja negra translúcida detrás de cada línea.">
            {Object.keys(opciones.fondos).map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label>
          Posición
          <select value={estilo.posicion} onChange={(e) => set("posicion", e.target.value)}>
            {opciones.posiciones.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="casilla">
          <input type="checkbox" checked={estilo.negrita} onChange={(e) => set("negrita", e.target.checked)} /> Negrita
        </label>
      </div>
    </div>
  );
}

/** CSS de una línea de subtítulo como la dibuja libass (recortar_clip.estilo_ass): tamaños sobre PlayResY=288, escalados al alto
 *  real del video en pantalla. Es la misma traducción que publicar_ui._vista_previa_estilo, pero sobre el video de verdad. */
export function cssSubtitulo(estilo: Estilo, opciones: Opciones, formato: "horizontal" | "vertical", altoPx: number): { caja: CSSProperties; texto: CSSProperties } {
  const base = formato === "vertical" ? 17 : 13;
  const margen = formato === "vertical" ? 46 : 24;
  const factor = opciones.tamanos[estilo.tamano] ?? 1;
  const k = altoPx / 288;
  const tam = Math.max(8, base * factor) * k * 1.15; // libass dibuja un poco más grande que el font-size nominal
  const familia = estilo.tipografia === "Lato" ? "Lato, sans-serif" : "Raleway, sans-serif";
  const peso = estilo.negrita ? 700 : estilo.tipografia === "Raleway" ? 600 : 400;
  const color = "#" + (opciones.colores[estilo.color] || "FFFFFF");
  const f = opciones.fondos[estilo.fondo] || { tipo: "caja", color: "000000", alpha: "90" };
  const texto: CSSProperties = { fontFamily: familia, fontWeight: peso, fontSize: tam, lineHeight: 1.3, color, textAlign: "center" };
  if (f.tipo === "caja" && f.color) {
    const op = 1 - parseInt(f.alpha, 16) / 255;
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(f.color!.slice(i, i + 2), 16));
    Object.assign(texto, {
      background: `rgba(${r},${g},${b},${op.toFixed(2)})`,
      padding: `${0.15 * tam}px ${0.4 * tam}px`,
      borderRadius: 3 * k,
      boxDecorationBreak: "clone",
      WebkitBoxDecorationBreak: "clone",
    });
  } else if (f.tipo === "borde" && f.color) {
    const c = "#" + f.color;
    const o = Math.max(1, 2 * k);
    texto.textShadow = [`-${o}px -${o}px 0 ${c}`, `${o}px -${o}px 0 ${c}`, `-${o}px ${o}px 0 ${c}`, `${o}px ${o}px 0 ${c}`, `0 ${o}px 0 ${c}`, `0 -${o}px 0 ${c}`, `${o}px 0 0 ${c}`, `-${o}px 0 0 ${c}`].join(",");
  }
  const caja: CSSProperties = {
    position: "absolute",
    left: 14 * k,
    right: 14 * k,
    display: "flex",
    justifyContent: "center",
    pointerEvents: "none",
  };
  if (estilo.posicion === "abajo") caja.bottom = margen * k;
  else if (estilo.posicion === "arriba") caja.top = margen * k;
  else {
    caja.top = "50%";
    caja.transform = "translateY(-50%)";
  }
  return { caja, texto };
}
