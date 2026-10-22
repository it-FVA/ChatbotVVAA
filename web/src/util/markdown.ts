// Markdown de las respuestas → HTML seguro. marked (GFM: tablas, listas, citas, links) + DOMPurify; los links abren aparte.
import { marked } from "marked";
import DOMPurify from "dompurify";

marked.setOptions({ gfm: true, breaks: true });

DOMPurify.addHook("afterSanitizeAttributes", (nodo) => {
  if (nodo.tagName === "A") {
    nodo.setAttribute("target", "_blank");
    nodo.setAttribute("rel", "noopener noreferrer");
  }
});

export function aHtml(md: string): string {
  const crudo = marked.parse(md || "", { async: false }) as string;
  return DOMPurify.sanitize(crudo, { USE_PROFILES: { html: true }, ADD_ATTR: ["target"] });
}

/** ¿Tiene al menos una tabla markdown (una fila |…| seguida de la línea |---|)? Misma idea que documentos.tablas_md. */
export function tieneTablas(md: string): boolean {
  return /^\s*\|.*\|\s*\n\s*\|?\s*:?-{2,}/m.test(md || "");
}
