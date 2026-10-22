// Piezas chicas compartidas: skeletons de carga, estado vacío con ilustración, migas de pan, tecla (kbd).
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icono } from "./Iconos";

/** Bloque gris animado del tamaño que se le pida. */
export function Hueso({ ancho = "100%", alto = 14, radio = 6, style }: { ancho?: number | string; alto?: number | string; radio?: number; style?: React.CSSProperties }) {
  return <div className="hueso" style={{ width: ancho, height: alto, borderRadius: radio, ...style }} aria-hidden="true" />;
}

/** Tarjeta de recorte «en esqueleto» mientras carga la lista. */
export function TarjetaEsqueleto({ vertical = false }: { vertical?: boolean }) {
  return (
    <div className="tarjeta recorte esqueleto" aria-hidden="true">
      <div className="recorte-mini">
        <Hueso ancho={vertical ? 135 : 200} alto={vertical ? 240 : 112} radio={8} />
      </div>
      <div className="recorte-cuerpo">
        <Hueso ancho="55%" alto={18} />
        <Hueso ancho="40%" style={{ marginTop: 10 }} />
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <Hueso ancho={84} alto={38} radio={10} />
          <Hueso ancho={92} alto={38} radio={10} />
          <Hueso ancho={84} alto={38} radio={10} />
        </div>
      </div>
    </div>
  );
}

/** Esqueleto del editor (video a la izquierda, línea de tiempo y cajas a la derecha). */
export function EditorEsqueleto() {
  return (
    <div className="pagina editor" aria-busy="true" aria-label="Cargando el recorte">
      <Hueso ancho={180} alto={14} />
      <Hueso ancho="50%" alto={26} style={{ margin: "10px 0 18px" }} />
      <div className="editor-grilla">
        <div className="editor-video">
          <Hueso ancho="100%" alto={420} radio={12} />
        </div>
        <div>
          <Hueso ancho="100%" alto={150} radio={12} />
          <Hueso ancho="100%" alto={220} radio={12} style={{ marginTop: 16 }} />
          <Hueso ancho="100%" alto={120} radio={12} style={{ marginTop: 16 }} />
        </div>
      </div>
    </div>
  );
}

/** Ilustración simple (una tira de película con una tijera) para los estados vacíos. */
function Ilustracion() {
  return (
    <svg className="vacio-ilustracion" viewBox="0 0 160 110" width="160" height="110" aria-hidden="true">
      <rect x="14" y="26" width="132" height="58" rx="8" fill="#fff" stroke="#e6e0d4" strokeWidth="2" />
      {[26, 48, 70, 92, 114].map((x) => (
        <rect key={x} x={x} y="32" width="12" height="8" rx="2" fill="#e6efe3" />
      ))}
      {[26, 48, 70, 92, 114].map((x) => (
        <rect key={x} x={x} y="70" width="12" height="8" rx="2" fill="#e6efe3" />
      ))}
      <rect x="40" y="44" width="80" height="22" rx="4" fill="#f4b43c" opacity="0.9" />
      <path d="M58 50l9 9M67 50l-9 9" stroke="#2b2b2b" strokeWidth="2" strokeLinecap="round" />
      <path d="M86 55h22M100 49l8 6-8 6" fill="none" stroke="#3a6b35" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="132" cy="18" r="9" fill="#f4b43c" />
      <path d="M128 18h8M132 14v8" stroke="#2b2b2b" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function EstadoVacio({ titulo, texto, accion }: { titulo: string; texto?: ReactNode; accion?: ReactNode }) {
  return (
    <div className="vacio" role="status">
      <Ilustracion />
      <h3>{titulo}</h3>
      {texto && <p className="suave">{texto}</p>}
      {accion && <div className="acciones" style={{ justifyContent: "center" }}>{accion}</div>}
    </div>
  );
}

export function Migas({ pasos }: { pasos: { texto: string; a?: string }[] }) {
  return (
    <nav className="migas" aria-label="Dónde estás">
      {pasos.map((p, i) => (
        <span key={i} className="miga">
          {i > 0 && <Icono nombre="chevron" tam={14} />}
          {p.a ? <Link to={p.a}>{p.texto}</Link> : <span aria-current="page">{p.texto}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Tecla({ children }: { children: ReactNode }) {
  return <kbd className="tecla">{children}</kbd>;
}
