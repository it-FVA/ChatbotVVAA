import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import "../ayuda.css";

// (5/11, Franco) Instructivo corto, una sección por pantalla. Cada botón que se nombra está en el código de esa pantalla.
// Máximo 120 palabras por sección (lo verifica Ayuda.test.tsx). Los ids son los que usa <LinkAyuda seccion="…" />.

export interface SeccionAyuda {
  id: string;
  titulo: string;
  que: string;
  pasos: string[];
  /** Una línea por canal u opción, entre «qué es» y el paso a paso. */
  lista?: string[];
}

export const SECCIONES: SeccionAyuda[] = [
  {
    id: "chat",
    titulo: "Chat",
    que: "Le preguntás al asistente y busca en el material de la Fundación: libros, videos y charlas. Cada respuesta muestra las fuentes y, debajo, se puede diseñar una pieza.",
    pasos: [
      "Escribí tu pregunta y enviala.",
      "Abrí las fuentes para ver de dónde sale cada cosa.",
      "Si es un video, usá «Pedir el recorte» o «Pedir en vertical».",
      "Para publicar, tocá el botón de la pieza propuesta: se abre Diseñar con todo cargado.",
      "«Compartir» le da la conversación a otra persona.",
    ],
  },
  {
    id: "disenar",
    titulo: "Diseñar",
    que: "Se arma la pieza de un canal: foto con la frase encima, texto y fecha. Diseñar no publica: la pieza va a aprobación y la publica quien aprueba. Cada canal tiene lo suyo:",
    lista: [
      "Instagram: foto cuadrada o vertical, historia (dura 24 horas y no lleva texto) o reel.",
      "Facebook: foto con la frase y el texto.",
      "Blogpost: entrada de la web, con título, texto largo y foto destacada.",
      "YouTube: un recorte, con título. Sube privado: se publica desde YouTube Studio.",
      "Email: es el Newsletter.",
    ],
    pasos: ["Elegí el canal en la barra.", "Cargá título, texto y foto.", "Elegí cuándo sale.", "Mirá la vista previa.", "«Enviar a aprobación» (o «Guardar borrador» para seguir después)."],
  },
  {
    id: "publicaciones",
    titulo: "Mis publicaciones",
    que: "Todo lo que diseñaste, con su estado: borrador (todavía no la mandaste), a aprobar, aprobada (espera su fecha), publicada o rechazada.",
    pasos: [
      "Elegí la solapa del estado.",
      "Con un borrador, «Retomar» para seguir.",
      "Si la rechazaron, leé la nota y tocá «Editar».",
      "Corregila y volvé a mandarla a aprobación.",
      "«Eliminar» borra lo que ya no sirve.",
    ],
  },
  {
    id: "recortes",
    titulo: "Mis recortes",
    que: "Los pedazos de video que pediste desde el chat. Tardan unos 15 minutos en estar listos, y aparecen acá solos.",
    pasos: [
      "En el chat, debajo de un video, tocá «Pedir el recorte» o «Pedir en vertical».",
      "Esperá a que aparezca el video acá.",
      "«Editar» cambia los tramos, quita pausas largas y corrige los subtítulos. Después, «Regenerar el recorte».",
      "«Descargar» baja el video. «Diseñar» arma una pieza con él.",
      "«Subir un video» sirve para un video editado afuera: entra como un recorte más.",
    ],
  },
  {
    id: "newsletter",
    titulo: "Newsletter",
    que: "El email a la comunidad, armado bloque por bloque con la plantilla de la Fundación. El mail no sale de acá: el HTML aprobado se pega en Perfit.",
    pasos: [
      "Elegí la plantilla.",
      "Escribí el tema para que el asistente redacte los textos.",
      "Cargá la agenda, las fotos y los links.",
      "«Guardar borrador» para seguir otro día («Retomar un borrador» lo recupera).",
      "«Enviar a aprobación». Aprobado, se descarga el HTML y se pega en Perfit.",
    ],
  },
  {
    id: "frase-del-dia",
    titulo: "Frase del día",
    que: "Una frase por día, con foto de fondo, que sale sola cada mañana por mail y redes. La tarjeta «Mañana» muestra qué sale y por dónde.",
    pasos: [
      "Mirá el calendario y la tarjeta «Mañana».",
      "Abrí un día para ver la frase y su diseño.",
      "Si querés otra frase ese día, usá «Pedir un cambio para este día».",
      "Quien aprueba acepta o rechaza el pedido.",
    ],
  },
  {
    id: "proyectos",
    titulo: "Proyectos y Compartidos",
    que: "Un proyecto es una carpeta con conversaciones, piezas y recortes de una misma campaña. En Compartidos están las carpetas que otras personas te dieron.",
    pasos: [
      "En Mis proyectos, «Nueva carpeta».",
      "Arrastrá conversaciones o agregá piezas y recortes.",
      "«Compartir» y elegí a quién.",
      "Con permiso de ver, se mira y no se toca. Con editar, se edita la misma pieza.",
      "Lo compartido con vos aparece en Compartidos.",
    ],
  },
  {
    id: "gestion",
    titulo: "Aprobación y Administración",
    que: "Solo las ve quien tiene el rol. Aprobación es para quien revisa y publica. Administración es para el equipo técnico.",
    pasos: [
      "Aprobación → «Para aprobar»: mirá la vista previa.",
      "Ajustá la fecha y hora si hace falta.",
      "«Aprobar y programar», o «Rechazar» con una nota que explique por qué.",
      "«En cola» muestra lo que está por salir.",
      "Administración: usuarios, lista blanca, salud y configuración.",
    ],
  },
];

export const SI_ALGO_FALLA = {
  id: "si-algo-falla",
  titulo: "Si algo falla",
  pasos: [
    "Refrescá la página.",
    "Si la primera vez tarda, esperá: la API se despierta sola en un minuto si estuvo dormida.",
    "Si sigue sin andar, avisale a Franco con lo que estabas haciendo.",
  ],
};

export default function Ayuda() {
  const { hash } = useLocation();

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
        {[...SECCIONES, SI_ALGO_FALLA].map((s) => (
          <a key={s.id} href={`#${s.id}`}>
            {s.titulo}
          </a>
        ))}
      </nav>

      {SECCIONES.map((s) => (
        <section key={s.id} id={s.id} className="ayuda-seccion" aria-labelledby={`${s.id}-t`}>
          <h2 id={`${s.id}-t`}>{s.titulo}</h2>
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
              <li key={p}>{p}</li>
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
