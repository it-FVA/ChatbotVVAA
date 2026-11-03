// Helpers y constantes de la Frase del día que comparten la página, los paneles y las solapas (3/11: antes todo en FraseDelDia.tsx).
import type { DragEvent } from "react";
import { ErrorApi } from "../../api";

export const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

export const DIAS = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"];

export const ICONO_ESTADO: Record<string, string> = { programada: "calendario", publicada: "megafono", simulada: "ojo", saltada: "chevron" };

export type Arrastre = { id: string; desde: string | null; texto: string };

export type Deshacer = { texto: string; hacer: () => Promise<void> };

export function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function fechaLarga(s: string) {
  const [y, m, d] = s.split("-").map(Number);
  return `${d} de ${MESES[m - 1]} de ${y}`;
}

export function fechaCorta(s: string) {
  const [, m, d] = s.split("-").map(Number);
  return `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}

/** (2/11) "2026-11-03T10:00:00+00:00" → "03/11 07:00" en hora Argentina (la cola guarda en UTC y la pantalla mostraba las 10:00). */
export function horaArgentina(iso?: string | null) {
  if (!iso) return "";
  const f = new Date(iso);
  if (isNaN(f.getTime())) return String(iso).slice(0, 16).replace("T", " ");
  return f.toLocaleString("es-AR", { timeZone: "America/Argentina/Buenos_Aires", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).replace(",", "");
}

// (2/11) nombres cortos de los canales de la frase para el checklist de la cabecera (los largos tienen el detalle entre paréntesis)
export const CANAL_CORTO: Record<string, string> = { historia: "Historia de Instagram", instagram: "Posteo de Instagram", facebook: "Facebook", mail: "Mail", home: "Sitio web", whatsapp: "WhatsApp" };

export function recortar(t: string, n: number) {
  // (2/11) muchas frases del Sheet ya vienen entre «»: se sacan, porque la pantalla las vuelve a poner («« » se veía doble)
  t = (t || "").replace(/\s+/g, " ").trim().replace(/^[«"“]+\s*/, "").replace(/\s*[»"”]+$/, "");
  return t.length <= n ? t : t.slice(0, n - 1).trimEnd() + "…";
}

export function mensajeDe(e: unknown) {
  return e instanceof ErrorApi ? e.message : "No pude conectarme con la API.";
}

export function mesVecino(c: { anio: number; mes: number }, paso: number) {
  let m = c.mes + paso;
  let y = c.anio;
  if (m > 12) (m = 1), (y += 1);
  if (m < 1) (m = 12), (y -= 1);
  return { anio: y, mes: m };
}

export function empezarArrastre(e: DragEvent, a: Arrastre, set: (a: Arrastre) => void) {
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", a.id);
  set(a);
}

/** La firma de `correr` del detalle del día: ejecuta una acción, avisa, refresca y ofrece deshacer. */
export type Correr = (a: () => Promise<string | void>, despues?: string | null, deshacer?: Deshacer) => Promise<void>;
