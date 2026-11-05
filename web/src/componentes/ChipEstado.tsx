// (5/11, QA visual) El chip de estado de una pieza o un recorte, igual en Mis publicaciones, Aprobación, el detalle de una pieza,
// Mis recortes y el chat. Cinco tonos: espera (ámbar), programada (verde claro), listo (verde), error (rojo) y neutro (gris).
// El texto lo manda la API (estado_texto); acá solo se traduce «simulada/simulado» a «prueba», que es como lo ve el equipo.
import { Icono, type NombreIcono } from "./Iconos";

const TONO: Record<string, string> = {
  a_aprobar: "espera",
  pendiente_aprobacion: "espera",
  pedido: "espera",
  proceso: "espera",
  regenerando: "espera",
  enviando: "espera",
  pendiente: "programada",
  programada: "programada",
  aprobada: "programada",
  publicada: "listo",
  publicado: "listo",
  lista: "listo",
  listo: "listo",
  rechazada: "error",
  error: "error",
};

const ICONO: Record<string, NombreIcono> = {
  a_aprobar: "reloj",
  pendiente_aprobacion: "reloj",
  pedido: "reloj",
  proceso: "reloj",
  regenerando: "reloj",
  enviando: "reloj",
  pendiente: "calendario",
  programada: "calendario",
  aprobada: "calendario",
  publicada: "check",
  publicado: "check",
  lista: "check",
  listo: "check",
  draft: "lapiz",
  borrador: "lapiz",
  rechazada: "cruz",
  cancelada: "cruz",
  error: "alerta",
  prueba: "ojo",
  simulada: "ojo",
  simulado: "ojo",
};

export function textoEstado(estado: string | null | undefined, texto?: string | null): string {
  const clave = (estado || "").toLowerCase();
  if (clave === "simulada" || clave === "simulado") return "prueba";
  return texto || estado || "";
}

export default function ChipEstado({ estado, texto, icono = true, title, className }: { estado: string | null | undefined; texto?: string | null; icono?: boolean; title?: string; className?: string }) {
  const clave = (estado || "").toLowerCase();
  const t = textoEstado(estado, texto);
  if (!t) return null;
  const nombre = ICONO[clave];
  return (
    <span className={"estado " + (TONO[clave] ?? "neutro") + (className ? " " + className : "")} title={title}>
      {icono && nombre && <Icono nombre={nombre} tam={13} />} {t}
    </span>
  );
}
