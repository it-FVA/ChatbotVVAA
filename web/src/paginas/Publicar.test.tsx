// El flujo de Diseñar con la API simulada: entrar desde el menú «Canales · Diseñar», completar el formulario, pasar al paso 2 y al 3
// y apretar «Ver simulado» (revisión 3/11, 5.3 punto 19).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "../componentes/Toasts";
import { instalarApi } from "../pruebas/apiSimulada";
import type { CanalOpcion, OpcionesPublicar, RespuestaEnvio } from "../tiposPublicar";
import Publicar from "./Publicar";

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
  publica: true,
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
  formatos: { cuadrado: [1080, 1080] },
  formato_por_canal: { facebook: "cuadrado", instagram: "cuadrado" },
  firma_defecto: "Vivir Agradecidos",
  zona: "America/Argentina/Buenos_Aires",
};

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

function pantalla(ruta: string) {
  const api = instalarApi({
    "GET /publicar/opciones": OPCIONES,
    "GET /banco": [],
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
    const siguiente = await screen.findByRole("button", { name: /Siguiente: foto y diseño/ });
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
    await u.click(screen.getByRole("button", { name: /Siguiente: foto y diseño/ }));

    // paso 2: Facebook es una red: se ofrece el texto sobre la imagen y el banco buscó fotos solo
    expect(await screen.findByLabelText(/Texto sobre la imagen/)).toBeInTheDocument();
    expect(api.de("GET", "/banco")).toHaveLength(1);
    await u.click(screen.getByRole("button", { name: /Siguiente: cuándo y enviar/ }));

    // paso 3: «Ver simulado» manda la pieza tal cual con modo simulado
    await u.click(await screen.findByRole("button", { name: /Ver simulado/ }));
    await waitFor(() => expect(api.de("POST", "/publicar/enviar")).toHaveLength(1));
    expect(api.de("POST", "/publicar/enviar")[0].cuerpo).toMatchObject({ canal: "facebook", titulo: "Gratitud de noviembre", texto: "Hoy agradezco el día.", modo: "simulado" });
    // el panel de resultado trae el título y el aviso de la API (la vista previa repite el título: por eso «todos»)
    expect((await screen.findAllByRole("heading", { name: "Así quedaría en Facebook" })).length).toBeGreaterThan(0);
    expect(screen.getByText("Así quedaría el posteo.")).toBeInTheDocument();
  });

  // (4/11, Franco) una rechazada vuelve al circuito: se corrige en el mismo lugar, con la nota del rechazo a la vista
  const RECHAZADA = {
    id: "r1", usuario: "patricio", canal: "facebook", estado: "rechazada", titulo: "Al mismo nivel", texto: "Texto de Patricio",
    rechazada_por: "julian", rechazada_en: "2026-11-04T20:00:00+00:00", nota: "se retorna para colaborar",
    propia: false, retomable: true, corregible: true,
    pieza: { canal: "facebook", titulo: "Al mismo nivel", texto: "Texto de Patricio", imagen_url: "", borrador_id: "r1" },
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

  it("si la API falla al abrir muestra el error y deja reintentar", async () => {
    instalarApi({});
    montar("/publicar?canal=facebook");
    expect(await screen.findByRole("alert")).toHaveTextContent("La prueba no simuló GET /publicar/opciones");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
