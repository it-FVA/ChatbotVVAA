// El flujo de Diseñar con la API simulada: entrar desde el menú «Canales · Diseñar», completar el formulario, pasar al paso 2 y al 3
// y apretar «Ver simulado» (revisión 3/11, 5.3 punto 19).
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "../componentes/Toasts";
import { instalarApi } from "../pruebas/apiSimulada";
import type { CanalOpcion, OpcionesPublicar, RespuestaEnvio } from "../tiposPublicar";
import Publicar from "./Publicar";

const RECORTE = { id: "c1", titulo: "Un corte", estado: "listo", url: "https://v/c1.mp4", miniatura: null, formato: "vertical", inicio_ms: 0, fin_ms: 30000, propio: true, subido: false };

function canal(nombre: string, extra: Partial<CanalOpcion> = {}): CanalOpcion {
  return {
    nombre,
    texto_canal: nombre,
    detalle: `Posteo en ${nombre}`,
    modo_real: "simulado",
    modo: "simulado",
    texto: `${nombre}: está en simulado, no sale nada de verdad.`,
    a_aprobar: true,
    acepta_aprobacion: true,
    requiere_titulo: false,
    formato: "cuadrado",
    va_a_la_cola: true,
    configurado: true,
    aviso_sin_fecha: `Se arma como saldría en ${nombre}; no sale nada.`,
    aviso_con_fecha: `Se programa en ${nombre} para {cuando}; no sale nada.`,
    ...extra,
  };
}

const OPCIONES: OpcionesPublicar = {
  canales: { facebook: canal("Facebook"), instagram: canal("Instagram"), wordpress: canal("Blogpost", { requiere_titulo: true, formato: null }) },
  publica: false, // (5/11) nadie publica directo, tampoco el admin
  aprueba: true,
  rol: "admin",
  aprobadores: ["ana"],
  usuario: "ana",
  logos: ["Ninguno"],
  logos_url: {},
  posiciones_logo: ["Abajo a la derecha"],
  tipografias: ["Raleway"],
  tipografia_defecto: "Raleway",
  pesos: ["Normal"],
  posiciones: ["Centro"],
  alineaciones: ["Centro"],
  formatos: { cuadrado: [1080, 1080], vertical: [1080, 1350], historia: [1080, 1920] },
  formato_por_canal: { facebook: "cuadrado", instagram: "cuadrado" },
  firma_defecto: "Vivir Agradecidos",
  zona: "America/Argentina/Buenos_Aires",
};

const FOTO = { id: 7, url: "https://w/amanecer.jpg", miniatura: "https://w/amanecer-m.jpg", titulo: "amanecer-sierras" };

const SIMULADO: RespuestaEnvio = { ok: true, modo: "simulado", simulado: true, encolada: false, imagen_url: null, avisos: [], aviso: "Así quedaría el posteo.", pieza: {}, texto_final: "Hoy agradezco el día.", formato: "cuadrado", video_url: null };

function montar(ruta: string) {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <ToastProvider>
        <Publicar />
      </ToastProvider>
    </MemoryRouter>,
  );
}

// (5/11, Franco) paso 2 con dos caminos: se elige la tarjeta Foto, y de ahí una foto del banco
async function elegirFoto(u: ReturnType<typeof userEvent.setup>) {
  await u.click(await screen.findByRole("button", { name: /^Foto/ }));
  await u.click(await screen.findByRole("radio", { name: /amanecer-sierras/ }));
}

function pantalla(ruta: string) {
  const api = instalarApi({
    "GET /publicar/opciones": OPCIONES,
    "GET /banco": [FOTO],
    "GET /recortes": [RECORTE],
    "POST /publicar/enviar": SIMULADO,
  });
  montar(ruta);
  return api;
}

describe("Diseñar", () => {
  it("desde el menú entra con el canal elegido y fijo", async () => {
    pantalla("/publicar?canal=facebook");
    // mientras carga hay un título «Diseñar» sin canal: se espera al que ya trae el canal elegido
    expect(await screen.findByRole("heading", { level: 1, name: "Diseñar · Facebook" })).toBeInTheDocument();
    // el canal ya está elegido: no se ofrece la lista de canales para cambiarlo
    expect(screen.queryByRole("group", { name: "Canal" })).not.toBeInTheDocument();
    expect(screen.getByText("Posteo en Facebook")).toBeInTheDocument();
  });

  it("sin canal en el menú ofrece los canales y no deja seguir hasta elegir uno", async () => {
    const u = userEvent.setup();
    pantalla("/publicar");
    const siguiente = await screen.findByRole("button", { name: /Siguiente: qué va en la pieza/ });
    expect(screen.getByRole("group", { name: "Canal" })).toBeInTheDocument();
    expect(siguiente).toBeDisabled();
    await u.click(screen.getByRole("radio", { name: /Instagram/ }));
    expect(siguiente).toBeEnabled();
  });

  it("completa el formulario, pasa al paso 2 y al 3 y muestra el simulado", async () => {
    const u = userEvent.setup();
    const api = pantalla("/publicar?canal=facebook");

    // paso 1: título y texto
    await u.type(await screen.findByLabelText(/^Título/), "Gratitud de noviembre");
    await u.type(screen.getByLabelText(/Texto de la pieza/), "Hoy agradezco el día.");
    expect(screen.getByText(/21 caracteres/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Siguiente: qué va en la pieza/ }));

    // paso 2: primero se elige Foto; Facebook es una red: se ofrece el texto sobre la imagen y el banco buscó fotos solo
    await u.click(await screen.findByRole("button", { name: /^Foto/ }));
    expect(await screen.findByLabelText(/Texto sobre la imagen/)).toBeInTheDocument();
    await u.click(await screen.findByRole("radio", { name: /amanecer-sierras/ }));
    expect(api.de("GET", "/banco")).toHaveLength(1);
    await u.click(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ }));

    // paso 3: «Ver simulado» manda la pieza tal cual con modo simulado
    await u.click(await screen.findByRole("button", { name: /Ver cómo quedaría/ }));
    await waitFor(() => expect(api.de("POST", "/publicar/enviar")).toHaveLength(1));
    expect(api.de("POST", "/publicar/enviar")[0].cuerpo).toMatchObject({ canal: "facebook", titulo: "Gratitud de noviembre", texto: "Hoy agradezco el día.", modo: "simulado" });
    // el panel de resultado trae el título y el aviso de la API (la vista previa repite el título: por eso «todos»)
    expect((await screen.findAllByRole("heading", { name: "Así quedaría en Facebook" })).length).toBeGreaterThan(0);
    expect(screen.getByText("Así quedaría el posteo.")).toBeInTheDocument();
  });

  // (5/11, Franco) nadie publica directo: un aprobador (o admin) ve «Enviar a aprobación» y nunca «Publicar en <canal>»
  it("un aprobador no ve «Publicar en»: manda a aprobación como todos", async () => {
    const u = userEvent.setup();
    const api = pantalla("/publicar?canal=facebook");
    await u.type(await screen.findByLabelText(/^Título/), "Gratitud de noviembre");
    await u.type(screen.getByLabelText(/Texto de la pieza/), "Hoy agradezco el día.");
    await u.click(screen.getByRole("button", { name: /Siguiente: qué va en la pieza/ }));
    await elegirFoto(u);
    await u.click(await screen.findByRole("button", { name: /Siguiente: cuándo y enviar/ }));
    expect(await screen.findByRole("button", { name: /Enviar a aprobación/ })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Publicar en/ })).toBeNull();
    expect(screen.getByText(/Vos también lo aprobás desde Aprobación/)).toBeInTheDocument();
    expect(api.de("POST", "/publicar/enviar")).toHaveLength(0);
  });

  // (4/11, Franco) una rechazada vuelve al circuito: se corrige en el mismo lugar, con la nota del rechazo a la vista
  const RECHAZADA = {
    id: "r1", usuario: "patricio", canal: "facebook", estado: "rechazada", titulo: "Al mismo nivel", texto: "Texto de Patricio",
    rechazada_por: "julian", rechazada_en: "2026-11-04T20:00:00+00:00", nota: "se retorna para colaborar",
    propia: false, retomable: true, corregible: true,
    pieza: { canal: "facebook", titulo: "Al mismo nivel", texto: "Texto de Patricio", imagen_url: "https://w/foto.jpg", borrador_id: "r1" },
  };

  it("una rechazada ajena con permiso editar se corrige en el mismo lugar y se reenvía con el mismo id", async () => {
    const u = userEvent.setup();
    const api = instalarApi({
      "GET /publicar/opciones": { ...OPCIONES, publica: false, aprueba: false, rol: "creador" },   // quien no publica directo manda a aprobación
      "GET /banco": [],
      "GET /publicaciones/r1": { ...RECHAZADA, permiso: "editar" },
      "POST /publicar/a-aprobar": { ok: true, id: "r1", estado: "a_aprobar", modo: "aprobacion", imagen_url: null, avisos: [], mensaje: "Quedó pendiente de aprobación (ana)." },
    });
    montar("/publicar?borrador=r1");
    expect(await screen.findByRole("note")).toHaveTextContent("La rechazó julian");
    expect(screen.getByRole("note")).toHaveTextContent("«se retorna para colaborar»");
    expect(screen.getByText(/Corrigiendo una pieza rechazada de patricio/)).toBeInTheDocument();
    // al retomar, el formulario arranca con el paso 1 hecho
    await u.click(await screen.findByRole("button", { name: /Siguiente: cuándo y enviar/ }));
    // (4/11) sobre algo que ya existe, el botón de guardar dice «Guardar cambios»
    expect(screen.getByRole("button", { name: /Guardar cambios/ })).toBeInTheDocument();
    await u.click(await screen.findByRole("button", { name: /Enviar a aprobación/ }));
    await waitFor(() => expect(api.de("POST", "/publicar/a-aprobar")).toHaveLength(1));
    expect(api.de("POST", "/publicar/a-aprobar")[0].cuerpo).toMatchObject({ borrador_id: "r1", canal: "facebook", texto: "Texto de Patricio" });
  });

  it("una rechazada ajena con permiso ver se abre como copia, sin la nota ni el id", async () => {
    instalarApi({ "GET /publicar/opciones": OPCIONES, "GET /banco": [], "GET /publicaciones/r1": { ...RECHAZADA, permiso: "ver", retomable: false } });
    montar("/publicar?borrador=r1");
    expect(await screen.findByText(/Una copia de una pieza de/)).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  // (5/11, Franco) Instagram son tres entradas del menú: Posteo, Reel e Historia, cada una con su formulario acotado
  describe("Instagram por tipo", () => {
    function pantallaIG(ruta: string) {
      const api = instalarApi({
        "GET /publicar/opciones": OPCIONES,
        "GET /banco": [FOTO],
        "GET /recortes": [RECORTE],
        "POST /publicar/a-aprobar": { ok: true, id: "p1", estado: "a_aprobar", modo: "aprobacion", imagen_url: null, avisos: [], mensaje: "Quedó pendiente de aprobación (ana)." },
      });
      montar(ruta);
      return api;
    }

    it("posteo: foto con la frase y caption, sin video", async () => {
      const u = userEvent.setup();
      pantallaIG("/publicar?canal=instagram&tipo=posteo");
      expect(await screen.findByRole("heading", { level: 1, name: "Diseñar · Instagram · Posteo" })).toBeInTheDocument();
      expect(screen.getByLabelText(/Texto de la pieza/)).toBeInTheDocument();
      await u.click(screen.getByRole("button", { name: /Siguiente: qué va en la pieza/ }));
      await u.click(await screen.findByRole("button", { name: /^Foto/ }));
      expect(await screen.findByLabelText(/Texto sobre la imagen/)).toBeInTheDocument();
      expect(screen.queryByText(/O usá un video vertical/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Usar este/)).not.toBeInTheDocument();
    });

    it("reel: sin video no deja enviar; con un recorte, sí, y manda formato vertical", async () => {
      const u = userEvent.setup();
      const api = pantallaIG("/publicar?canal=instagram&tipo=reel");
      expect(await screen.findByRole("heading", { level: 1, name: "Diseñar · Instagram · Reel" })).toBeInTheDocument();
      await u.type(screen.getByLabelText(/Texto de la pieza/), "Un caption");
      await u.click(screen.getByRole("button", { name: /Siguiente: qué va en la pieza/ }));
      // el reel solo lleva video: sin elección, directo a los recortes, sin foto ni frase
      expect(screen.queryByRole("button", { name: /^Foto/ })).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/Texto sobre la imagen/)).not.toBeInTheDocument();
      expect(screen.queryByRole("radiogroup", { name: "Elegí una foto" })).not.toBeInTheDocument();
      // sin video el paso 3 espera
      expect(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ })).toBeDisabled();
      // se elige un recorte
      await u.click(await screen.findByRole("button", { name: "Usar este" }));
      await u.click(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ }));
      const enviar = await screen.findByRole("button", { name: /Enviar a aprobación/ });
      expect(enviar).toBeEnabled();
      await u.click(enviar);
      await waitFor(() => expect(api.de("POST", "/publicar/a-aprobar")).toHaveLength(1));
      expect(api.de("POST", "/publicar/a-aprobar")[0].cuerpo).toMatchObject({ canal: "instagram", texto: "Un caption", video_url: "https://v/c1.mp4", formato: "vertical", vfmt: "reel" });
    });

    it("historia: sin caption, con el aviso de 24 horas; manda formato historia", async () => {
      const u = userEvent.setup();
      const api = pantallaIG("/publicar?canal=instagram&tipo=historia");
      expect(await screen.findByRole("heading", { level: 1, name: "Diseñar · Instagram · Historia" })).toBeInTheDocument();
      expect(screen.queryByLabelText(/Texto de la pieza/)).not.toBeInTheDocument();
      expect(screen.getByText(/dura 24 horas y no lleva caption/)).toBeInTheDocument();
      // sin foto ni video todavía no se puede enviar
      await u.click(screen.getByRole("button", { name: /Siguiente: qué va en la pieza/ }));
      // la historia tiene la misma elección que los demás canales, sin carrusel
      expect(screen.getByRole("button", { name: /^Video/ })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /Varias fotos/ })).not.toBeInTheDocument();
      await u.click(screen.getByRole("button", { name: /^Foto/ }));
      expect(screen.queryByLabelText(/^Formato/)).not.toBeInTheDocument();
      // sin foto ni video no se puede seguir
      expect(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ })).toBeDisabled();
      expect(api.de("POST", "/publicar/a-aprobar")).toHaveLength(0);
    });

    it("al cambiar de tipo desde el menú se conserva el texto escrito", async () => {
      const u = userEvent.setup();
      instalarApi({ "GET /publicar/opciones": OPCIONES, "GET /banco": [], "GET /recortes": [RECORTE] });
      render(
        <MemoryRouter initialEntries={["/publicar?canal=instagram&tipo=posteo"]}>
          <ToastProvider>
            <Link to="/publicar?canal=instagram&tipo=reel">ir al reel</Link>
            <Link to="/publicar?canal=instagram&tipo=historia">ir a la historia</Link>
            <Publicar />
          </ToastProvider>
        </MemoryRouter>,
      );
      await u.type(await screen.findByLabelText(/Texto de la pieza/), "Mi caption");
      await u.click(screen.getByText("ir al reel"));
      expect(await screen.findByRole("heading", { level: 1, name: "Diseñar · Instagram · Reel" })).toBeInTheDocument();
      expect(screen.getByLabelText(/Texto de la pieza/)).toHaveValue("Mi caption");
      // la historia no lleva caption: el campo se oculta, pero el texto no se pierde al volver
      await u.click(screen.getByText("ir a la historia"));
      expect(await screen.findByRole("heading", { level: 1, name: "Diseñar · Instagram · Historia" })).toBeInTheDocument();
      expect(screen.queryByLabelText(/Texto de la pieza/)).not.toBeInTheDocument();
      await u.click(screen.getByText("ir al reel"));
      expect(await screen.findByLabelText(/Texto de la pieza/)).toHaveValue("Mi caption");
    });
  });

  // (5/11, Franco) paso 2 nuevo, «Qué va en la pieza»: primero se elige Foto o Video
  describe("Paso 2: Foto o Video", () => {
    async function aPaso2(u: ReturnType<typeof userEvent.setup>, ruta: string) {
      const api = pantalla(ruta);
      const siguiente = await screen.findByRole("button", { name: /Siguiente: qué va en la pieza/ });
      const texto = screen.queryByLabelText(/Texto de la pieza/); // la historia no lleva caption
      if (texto) await u.type(texto, "Hoy agradezco el día.");
      await u.click(siguiente);
      return api;
    }

    it("al abrir el paso sin nada elegido se ven las tarjetas Foto y Video, y el paso 3 espera", async () => {
      const u = userEvent.setup();
      await aPaso2(u, "/publicar?canal=facebook");
      expect(screen.getByText("Qué va en la pieza")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^Foto/ })).toBeEnabled();
      expect(screen.getByRole("button", { name: /^Video/ })).toBeEnabled();
      expect(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ })).toBeDisabled();
    });

    it("elegir Foto muestra las tres solapas", async () => {
      const u = userEvent.setup();
      await aPaso2(u, "/publicar?canal=facebook");
      await u.click(screen.getByRole("button", { name: /^Foto/ }));
      expect(screen.getByRole("tab", { name: "Banco de la Fundación" })).toHaveAttribute("aria-selected", "true");
      expect(screen.getByRole("tab", { name: "Subir de mi compu" })).toBeInTheDocument();
      await u.click(screen.getByRole("tab", { name: "Pegar un link" }));
      expect(screen.getByLabelText(/Link de una imagen/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cambiar a video" })).toBeInTheDocument();
    });

    it("elegir Video muestra los recortes listos y subir un video, también en Blogpost", async () => {
      const u = userEvent.setup();
      await aPaso2(u, "/publicar?canal=wordpress");
      await u.click(screen.getByRole("button", { name: /^Video/ }));
      expect(screen.getByRole("tab", { name: "Recortes listos" })).toHaveAttribute("aria-selected", "true");
      expect(screen.getByRole("tab", { name: "Subir un video mío" })).toBeInTheDocument();
      await u.click(await screen.findByRole("button", { name: "Usar este" }));
      expect(screen.getByText(/El video va al principio de la entrada/)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ })).toBeEnabled();
      await u.click(screen.getByRole("tab", { name: "Subir un video mío" }));
      expect(screen.getByText("Arrastrá un video o elegilo")).toBeInTheDocument();
    });

    it("«Varias fotos» aparece solo en Instagram posteo y Facebook, y está deshabilitada", async () => {
      const u = userEvent.setup();
      for (const [ruta, aparece] of [["/publicar?canal=facebook", true], ["/publicar?canal=instagram&tipo=posteo", true], ["/publicar?canal=wordpress", false], ["/publicar?canal=instagram&tipo=historia", false]] as const) {
        await aPaso2(u, ruta);
        const varias = screen.queryByRole("button", { name: /Varias fotos/ });
        if (aparece) {
          expect(varias).toBeDisabled();
          expect(varias).toHaveTextContent("pronto");
        } else expect(varias).not.toBeInTheDocument();
        cleanup();
      }
    });

    it("cambiar de camino limpia lo elegido pero conserva el texto y la fecha", async () => {
      const u = userEvent.setup();
      await aPaso2(u, "/publicar?canal=facebook");
      await elegirFoto(u);
      // la fecha del paso 3
      await u.click(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ }));
      await u.click(await screen.findByLabelText(/Programar para una fecha/));
      await u.click(screen.getByRole("button", { name: /Qué va en la pieza/ }));
      await u.click(screen.getByRole("button", { name: "Cambiar a video" }));
      // lo elegido de la foto se limpió: el paso 3 vuelve a esperar
      expect(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ })).toBeDisabled();
      await u.click(screen.getByRole("button", { name: "Cambiar a foto" }));
      expect(await screen.findByRole("radio", { name: /amanecer-sierras/ })).toHaveAttribute("aria-checked", "false");
      // el texto del paso 1 sigue
      await u.click(screen.getByRole("button", { name: /Volver/ }));
      expect(screen.getByLabelText(/Texto de la pieza/)).toHaveValue("Hoy agradezco el día.");
      // y la fecha también
      await u.click(screen.getByRole("button", { name: /Siguiente: qué va en la pieza/ }));
      await u.click(await screen.findByRole("radio", { name: /amanecer-sierras/ }));
      await u.click(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ }));
      expect(await screen.findByLabelText(/Programar para una fecha/)).toBeChecked();
    });

    it("una pieza que llega con un recorte abre el paso 2 directo en Video", async () => {
      const u = userEvent.setup();
      instalarApi({ "GET /publicar/opciones": OPCIONES, "GET /banco": [FOTO], "GET /recortes": [RECORTE], "GET /recortes/c1": RECORTE });
      montar("/publicar?recorte=c1");
      await u.click(await screen.findByRole("button", { name: /Qué va en la pieza/ }));
      expect(screen.getByRole("tab", { name: "Recortes listos" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Cambiar a foto" })).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /^Foto/ })).not.toBeInTheDocument();
    });
  });

  it("si la API falla al abrir muestra el error y deja reintentar", async () => {
    instalarApi({});
    montar("/publicar?canal=facebook");
    expect(await screen.findByRole("alert")).toHaveTextContent("La prueba no simuló GET /publicar/opciones");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
