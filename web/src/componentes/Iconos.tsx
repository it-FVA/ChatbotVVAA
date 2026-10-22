// Set chico de iconos SVG propios (trazo de 2 px, 24×24, color = currentColor). Sin librerías: alcanza con estos.
import type { CSSProperties } from "react";

const TRAZOS: Record<string, string> = {
  reproducir: "M7 5v14l11-7z",
  pausar: "M7 5h4v14H7zM13 5h4v14h-4z",
  tijera: "M6 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm0 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12",
  tacho: "M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6",
  lapiz: "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z",
  externo: "M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5",
  deshacer: "M3 7v6h6M3.5 13a9 9 0 1 0 2.1-7.1L3 7",
  regenerar: "M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6",
  lupaMas: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4M8 11h6M11 8v6",
  lupaMenos: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4M8 11h6",
  ajustar: "M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5M8 8h8v8H8z",
  teclado: "M3 7h18v10H3zM6 10h1M9 10h1M12 10h1M15 10h1M18 10h0M6 13h1M9 13h1M12 13h1M15 13h1M18 13h0M8 16h8",
  check: "M5 12l4 4L19 7",
  cruz: "M6 6l12 12M18 6L6 18",
  mas: "M12 5v14M5 12h14",
  menos: "M5 12h14",
  flechaIzq: "M19 12H5M11 18l-6-6 6-6",
  chevron: "M9 6l6 6-6 6",
  alerta: "M12 3l10 18H2zM12 10v4M12 17.5v.5",
  reloj: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3 2",
  buscar: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-6-6",
  pelicula: "M3 5h18v14H3zM7 5v14M17 5v14M3 10h4M3 14h4M17 10h4M17 14h4",
  usuarios: "M16 19v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM22 19v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  salir: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  chat: "M21 12a8 8 0 0 1-11.6 7.2L4 21l1.8-5.4A8 8 0 1 1 21 12z",
  megafono: "M3 10v4a1 1 0 0 0 1 1h3l6 4V5L7 9H4a1 1 0 0 0-1 1zM17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12",
  celular: "M7 2h10a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM11 18h2",
  marcaIni: "M6 4v16M6 12h10l-3-3M16 12l-3 3",
  marcaFin: "M18 4v16M18 12H8l3-3M8 12l3 3",
  ojo: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v5M12 8v.5",
  pregunta: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.7M12 17v.5",
  paleta: "M12 3a9 9 0 0 0 0 18c1 0 1.5-.6 1.5-1.3 0-.8-.6-1-.6-1.8 0-.9.7-1.4 1.6-1.4H16a5 5 0 0 0 5-5c0-4.6-4-8.5-9-8.5zM7.5 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM10.5 7.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM14.5 7.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM17 11a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  subtitulos: "M3 5h18v14H3zM6 12h6M14 12h4M6 15h3M11 15h7",
  tramo: "M4 6v12M20 6v12M4 12h16M9 9l-3 3 3 3M15 9l3 3-3 3",
};

export type NombreIcono = keyof typeof TRAZOS;

export function Icono({ nombre, tam = 18, style, relleno = false }: { nombre: NombreIcono; tam?: number; style?: CSSProperties; relleno?: boolean }) {
  return (
    <svg
      className="icono"
      width={tam}
      height={tam}
      viewBox="0 0 24 24"
      fill={relleno ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={relleno ? 0 : 2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      style={style}
    >
      <path d={TRAZOS[nombre]} />
    </svg>
  );
}
