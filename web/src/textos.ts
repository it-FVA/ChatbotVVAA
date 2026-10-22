// Textos de la pantalla de chat en los tres idiomas de las cuentas (es/en/de), como la tabla _T de app.py.
// Lo que no está traducido cae al español. Los botones de recortes y la pieza se muestran solo en español (como Streamlit).
import type { Idioma } from "./util/fechas";

const T = {
  nueva: { es: "Nueva conversación", en: "New conversation", de: "Neues Gespräch" },
  tus: { es: "Tus conversaciones", en: "Your conversations", de: "Deine Gespräche" },
  buscar: { es: "Buscar en tus conversaciones", en: "Search your conversations", de: "Gespräche durchsuchen" },
  sinConversaciones: { es: "Todavía no tenés conversaciones", en: "No conversations yet", de: "Noch keine Gespräche" },
  sinResultados: { es: "Ninguna conversación coincide", en: "No conversation matches", de: "Kein Gespräch passt" },
  renombrar: { es: "Renombrar", en: "Rename", de: "Umbenennen" },
  borrar: { es: "Borrar", en: "Delete", de: "Löschen" },
  borrarTitulo: { es: "¿Borrar esta conversación?", en: "Delete this conversation?", de: "Dieses Gespräch löschen?" },
  borrarTexto: {
    es: "Va a la papelera 30 días: la podés recuperar enseguida con «Deshacer», y después un aprobador desde el Panel admin.",
    en: "It goes to the trash for 30 days: you can undo right away, and later an approver can restore it from the admin panel.",
    de: "Es kommt 30 Tage in den Papierkorb: du kannst es sofort rückgängig machen, später kann es ein Freigeber wiederherstellen.",
  },
  siBorrar: { es: "Sí, borrar", en: "Yes, delete", de: "Ja, löschen" },
  cancelar: { es: "Cancelar", en: "Cancel", de: "Abbrechen" },
  borrada: { es: "Conversación borrada.", en: "Conversation deleted.", de: "Gespräch gelöscht." },
  deshacer: { es: "Deshacer", en: "Undo", de: "Rückgängig" },
  restaurada: { es: "Conversación recuperada.", en: "Conversation restored.", de: "Gespräch wiederhergestellt." },
  hoy: { es: "Hoy", en: "Today", de: "Heute" },
  ayer: { es: "Ayer", en: "Yesterday", de: "Gestern" },
  semana: { es: "Últimos 7 días", en: "Last 7 days", de: "Letzte 7 Tage" },
  antes: { es: "Anteriores", en: "Earlier", de: "Früher" },
  titulo: { es: "Asistente de contenido", en: "Content assistant", de: "Content-Assistent" },
  sub: {
    es: "Búsqueda y armado fundados solo en el material real de la Fundación. Los borradores son para revisión del equipo.",
    en: "Search and drafting grounded only in the Foundation's real material (Br. David and facilitators). Drafts are for the team's review. Quotes are shown in their original language.",
    de: "Suche und Entwürfe gründen ausschließlich auf dem echten Material der Stiftung (Br. David und Begleiter). Entwürfe sind zur Durchsicht. Zitate erscheinen in ihrer Originalsprache.",
  },
  placeholder: {
    es: "Escribí acá… (ej: 'estoy pensando una campaña sobre gratitud, ¿por dónde arrancarías?')",
    en: "Write here… (e.g. 'what does Br. David say about hope and expectation?')",
    de: "Hier schreiben… (z. B. 'Was sagt Bruder David über Dankbarkeit und Angst?')",
  },
  enviar: { es: "Enviar", en: "Send", de: "Senden" },
  detener: { es: "Detener", en: "Stop", de: "Stoppen" },
  ayudaEntrada: { es: "Enter envía · Shift+Enter, nueva línea · / enfoca el cuadro", en: "Enter sends · Shift+Enter, new line · / focuses the box", de: "Enter sendet · Shift+Enter neue Zeile · / fokussiert das Feld" },
  pensando: { es: "Pensando…", en: "Thinking…", de: "Denke nach…" },
  buscando: { es: "Buscando en el material…", en: "Searching the material…", de: "Suche im Material…" },
  trabajando: { es: "Trabajando…", en: "Working…", de: "Arbeite…" },
  escribiendo: { es: "Escribiendo…", en: "Writing…", de: "Schreibe…" },
  despertando: { es: "La API está despertando: puede tardar un minuto. Tu mensaje se manda solo cuando esté lista.", en: "The API is waking up: it can take a minute. Your message is sent as soon as it is ready.", de: "Die API wacht gerade auf: das kann eine Minute dauern. Deine Nachricht wird gesendet, sobald sie bereit ist." },
  noDesperto: { es: "La API no respondió en dos minutos. Probá de nuevo en un rato.", en: "The API did not answer within two minutes. Try again in a while.", de: "Die API hat zwei Minuten lang nicht geantwortet. Versuch es später noch einmal." },
  cortado: { es: "Se cortó la respuesta. Podés volver a mandar el mensaje.", en: "The answer was cut off. You can send the message again.", de: "Die Antwort wurde unterbrochen. Du kannst die Nachricht erneut senden." },
  detenido: { es: "Detuviste la respuesta.", en: "You stopped the answer.", de: "Du hast die Antwort gestoppt." },
  reintentar: { es: "Reintentar", en: "Retry", de: "Erneut versuchen" },
  noCargo: { es: "No pude abrir esa conversación.", en: "I could not open that conversation.", de: "Ich konnte dieses Gespräch nicht öffnen." },
  noLista: { es: "No pude leer tus conversaciones.", en: "I could not read your conversations.", de: "Ich konnte deine Gespräche nicht lesen." },
  vacioTitulo: { es: "¿Por dónde arrancamos?", en: "Where do we start?", de: "Womit fangen wir an?" },
  vacioTexto: {
    es: "Preguntale al asistente por el material de Br. David y los facilitadores: busca en artículos, libros y videos, arma piezas y te muestra las fuentes.",
    en: "Ask the assistant about Br. David's and the facilitators' material: it searches articles, books and videos, drafts pieces and shows you the sources.",
    de: "Frag den Assistenten nach dem Material von Bruder David und den Begleitern: er durchsucht Artikel, Bücher und Videos, entwirft Beiträge und zeigt dir die Quellen.",
  },
  ejemplos: {
    es: ["¿Qué dice Br. David sobre la gratitud y el miedo?", "Buscame un video corto sobre la esperanza", "Armame un posteo de Instagram sobre la alegría"],
    en: ["What does Br. David say about gratitude and fear?", "Find me a short video about hope", "Draft an Instagram post about joy"],
    de: ["Was sagt Bruder David über Dankbarkeit und Angst?", "Such mir ein kurzes Video über Hoffnung", "Entwirf einen Instagram-Beitrag über Freude"],
  },
  fuentes: { es: "Fuentes", en: "Sources", de: "Quellen" },
  citada: { es: (n: number) => `${n} citada${n > 1 ? "s" : ""} en la respuesta`, en: (n: number) => `${n} cited in the answer`, de: (n: number) => `${n} in der Antwort zitiert` },
  citadaBadge: { es: "citada en la respuesta", en: "cited in the answer", de: "in der Antwort zitiert" },
  verFuente: { es: "Ver fuente ↗", en: "View source ↗", de: "Quelle öffnen ↗" },
  traduccion: { es: "", en: "translation", de: "Übersetzung" },
  word: { es: "Word", en: "Word", de: "Word" },
  excel: { es: "Excel", en: "Excel", de: "Excel" },
  descargaWord: { es: "Descarga esta respuesta como documento de Word.", en: "Download this answer as a Word document.", de: "Diese Antwort als Word-Dokument herunterladen." },
  descargaExcel: { es: "Descarga las planillas de esta respuesta como Excel, una hoja por tabla.", en: "Download this answer's tables as Excel, one sheet per table.", de: "Die Tabellen dieser Antwort als Excel herunterladen, ein Blatt pro Tabelle." },
  abrirLista: { es: "Conversaciones", en: "Conversations", de: "Gespräche" },
  cerrar: { es: "Cerrar", en: "Close", de: "Schließen" },
  bajar: { es: "Ir al final", en: "Jump to the end", de: "Zum Ende springen" },
  conversacion: { es: "Conversación", en: "Conversation", de: "Gespräch" },
};

export type ClaveTexto = keyof typeof T;

export function textos(idioma: string) {
  const i = (["es", "en", "de"].includes(idioma) ? idioma : "es") as Idioma;
  return function t<K extends ClaveTexto>(k: K): (typeof T)[K]["es"] {
    const fila = T[k] as Record<string, unknown>;
    return (fila[i] ?? fila.es) as (typeof T)[K]["es"];
  };
}

export const TAGS: Record<string, Record<string, string>> = {
  en: { ARTÍCULO: "ARTICLE", CLIP: "CLIP", LIBRO: "BOOK", "pág.": "p." },
  de: { ARTÍCULO: "ARTIKEL", CLIP: "CLIP", LIBRO: "BUCH", "pág.": "S." },
};
