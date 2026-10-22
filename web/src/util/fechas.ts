// Fechas relativas para la lista de conversaciones («hace 5 min», «ayer», «12/10»), en es/en/de.
const TXT = {
  es: { ahora: "recién", min: (n: number) => `hace ${n} min`, h: (n: number) => `hace ${n} h`, ayer: "ayer", dias: (n: number) => `hace ${n} días` },
  en: { ahora: "just now", min: (n: number) => `${n} min ago`, h: (n: number) => `${n} h ago`, ayer: "yesterday", dias: (n: number) => `${n} days ago` },
  de: { ahora: "gerade eben", min: (n: number) => `vor ${n} Min.`, h: (n: number) => `vor ${n} Std.`, ayer: "gestern", dias: (n: number) => `vor ${n} Tagen` },
};

export type Idioma = "es" | "en" | "de";

export function relativa(iso: string, idioma: Idioma = "es", ahora = Date.now()): string {
  const t = TXT[idioma] || TXT.es;
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "";
  const seg = Math.max(0, (ahora - d) / 1000);
  if (seg < 60) return t.ahora;
  if (seg < 3600) return t.min(Math.floor(seg / 60));
  if (seg < 86400) return t.h(Math.floor(seg / 3600));
  const dias = Math.floor(seg / 86400);
  if (dias === 1) return t.ayer;
  if (dias < 7) return t.dias(dias);
  return new Date(iso).toLocaleDateString(idioma === "en" ? "en-GB" : idioma === "de" ? "de-DE" : "es-AR", { day: "2-digit", month: "2-digit", ...(dias > 300 ? { year: "2-digit" } : {}) });
}

/** Grupo de la lista: hoy, ayer, esta semana, antes. */
export function grupo(iso: string, ahora = new Date()): "hoy" | "ayer" | "semana" | "antes" {
  const d = new Date(iso);
  const inicioHoy = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate()).getTime();
  const t = d.getTime();
  if (t >= inicioHoy) return "hoy";
  if (t >= inicioHoy - 86400000) return "ayer";
  if (t >= inicioHoy - 6 * 86400000) return "semana";
  return "antes";
}
