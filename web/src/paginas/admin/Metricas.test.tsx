// (8/11, Franco) Pantalla Métricas con la API simulada (contrato: web/maquetas/metricas-contrato.md).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { instalarApi } from "../../pruebas/apiSimulada";

vi.mock("../../App", () => ({
  useSesion: () => ({ yo: { usuario: "ana", rol: { nombre: "admin", admin: true, aprueba: true, publica: true, etiqueta: "Administrador" } }, cargando: false, setYo: () => {} }),
}));

import Administracion from "./Administracion";
import Metricas from "./Metricas";

const ahora = new Date().toISOString();
const G0 = { publicada: 0, programada: 0, en_aprobacion: 0, borrador: 0, prueba: 0, no_salio: 0 };
const CAMPANAS = {
  periodo: { tipo: "dias", dias: 90, desde: "2026-08-10", hasta: null, texto: "últimos 90 días" },
  campanas: [
    {
      id: "c1", nombre: "Lo común nos convoca", emoji: "🤝", color: "#3a6b35", dueno: "pato", creado: ahora, piezas_total: 2,
      por_canal: { instagram: { ...G0, publicada: 1, programada: 1 } }, por_estado: { ...G0, publicada: 1, programada: 1 }, primera: ahora, ultima: ahora,
      piezas: [
        { id: "p1", canal: "instagram", canal_texto: "Instagram", titulo: "Gratitud en casa", estado: "publicada", estado_grupo: "publicada", fecha: "2026-11-05T12:00:00+00:00", ver_url: "https://instagram.com/p/x", formato: "cuadrado", usuario: "pato", modo: "real", metricas: { alcance: 120, me_gusta: 14, fuente: "api", capturado: ahora } },
        { id: "p2", canal: "instagram", canal_texto: "Instagram", titulo: "Mañana sale", estado: "pendiente", estado_grupo: "programada", fecha: "2026-11-09T12:00:00+00:00", ver_url: null, formato: "historia", usuario: "pato", modo: "real", metricas: null },
      ],
    },
  ],
  sueltas: { id: "sueltas", nombre: "Sin campaña", emoji: null, color: null, dueno: null, creado: null, piezas_total: 0, por_canal: {}, por_estado: G0, primera: null, ultima: null, piezas: [] },
  totales: { piezas: 2, ...G0, publicada: 1, programada: 1, por_canal: { instagram: 2 } },
};
const CANALES = {
  actualizado: ahora,
  canales: [
    { clave: "instagram", texto: "Instagram", icono: "instagram", modo: "real", configurado: true, api: "sin_permiso", nota_api: "Falta el permiso instagram_manage_insights", enlace: "https://business.facebook.com/latest/insights/overview", enlace_texto: "Ver en Meta Business Suite", ultima: null, manual: { datos: { alcance: 1500 }, periodo_desde: "2026-10-01", periodo_hasta: "2026-10-31", capturado: ahora, nota: "Del panel", por: "franco" } },
    { clave: "facebook", texto: "Facebook", icono: "facebook", modo: "real", configurado: true, api: "disponible", nota_api: null, enlace: null, enlace_texto: null, ultima: { datos: { alcance: 1200, seguidores: 3400 }, periodo_desde: "2026-10-10", periodo_hasta: "2026-11-08", capturado: ahora, fuente: "api" }, manual: null },
    { clave: "mail", texto: "Mail", icono: "sobre", modo: "real", configurado: true, api: "no_hay", nota_api: "Perfit: los reportes se ven en la plataforma", enlace: "https://app.myperfit.com/", enlace_texto: "Abrir Perfit", ultima: null, manual: null },
  ],
};
const RESUMEN = { ref: "c1", nombre: "Lo común nos convoca", texto: "Le fue **bien** en Instagram.", fuentes: ["Instagram (desde la plataforma, 8/11)"], falto: ["YouTube: sin datos"], comparado_con: "Polarizaciones", modelo: "gpt", capturado: ahora };

const APERTURA = { texto: "Esta semana se movió **Lo común**.", fuentes: ["Instagram (desde la plataforma, 8/11)"], falto: [], capturado: ahora, nuevo: true };

function abrir(extra: Record<string, unknown> = {}, ruta = "/administracion/metricas") {
  const api = instalarApi({ "GET /admin/metricas/campanas": CAMPANAS, "GET /admin/metricas/canales": CANALES, "GET /admin/metricas/resumen/c1": null, "GET /admin/metricas/asesor/apertura": APERTURA, "GET /admin/resumen": { salud: { estado: "ok" }, costo: null, registro_desde: "" }, ...extra });
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/administracion" element={<Administracion />}>
          <Route path="metricas" element={<Metricas />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  return api;
}

describe("Métricas", () => {
  it("muestra canales y campañas; sin permiso dice «falta un permiso»", async () => {
    abrir();
    const ig = await screen.findByRole("article", { name: "Instagram" });
    expect(within(ig).getByText("falta un permiso")).toBeInTheDocument();
    expect(within(ig).getByText("Anotado a mano")).toBeInTheDocument();
    expect(within(ig).getByRole("link", { name: /Ver en Meta Business Suite/ })).toHaveAttribute("target", "_blank");
    const fb = screen.getByRole("article", { name: "Facebook" });
    expect(within(fb).getByText("conectado")).toBeInTheDocument();
    expect(within(fb).getByText("3.400")).toBeInTheDocument();
    expect(await screen.findByText(/Lo común nos convoca/)).toBeInTheDocument();
    expect(screen.getByText("Gratitud en casa")).toBeInTheDocument();
    expect(screen.getByText(/alcance 120 · me gusta 14 · desde Instagram/)).toBeInTheDocument();
  });

  it("el asesor muestra la apertura al entrar y responde preguntas con el body esperado", async () => {
    const u = userEvent.setup();
    const api = abrir({ "POST /admin/metricas/asesor": { texto: "Conviene **Instagram**.", fuentes: ["Guía de canales"], falto: ["YouTube: sin datos"] } });
    expect(await screen.findByText("Lo común")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "¿Qué campaña rindió mejor?" })).toBeInTheDocument();
    await u.type(screen.getByLabelText("Tu pregunta"), "¿Qué canal conviene?{Enter}");
    expect(await screen.findByText("Instagram", { selector: "strong" })).toBeInTheDocument();
    expect(api.de("POST", "/admin/metricas/asesor")[0].cuerpo).toEqual({ mensajes: [{ rol: "usuario", texto: "¿Qué canal conviene?" }], dias: 90 });
    expect(screen.getByText("Guía de canales")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "¿Qué campaña rindió mejor?" })).not.toBeInTheDocument();
  });

  it("anotar números manda PUT /admin/metricas/manual y recarga", async () => {
    const u = userEvent.setup();
    const api = abrir({ "PUT /admin/metricas/manual": { id: "m1" } });
    const mail = await screen.findByRole("article", { name: "Mail" });
    await u.click(within(mail).getByRole("button", { name: /Anotar números/ }));
    await u.type(within(mail).getByLabelText("Enviados"), "300");
    await u.type(within(mail).getByLabelText("Aperturas"), "120");
    await u.type(within(mail).getByLabelText("Nota"), "Reporte de Perfit");
    await u.click(within(mail).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(api.de("PUT", "/admin/metricas/manual")).toHaveLength(1));
    expect(api.de("PUT", "/admin/metricas/manual")[0].cuerpo).toEqual({ ambito: "canal", ref: "mail", canal: "mail", periodo_desde: null, periodo_hasta: null, datos: { enviados: 300, aperturas: 120 }, nota: "Reporte de Perfit" });
    await waitFor(() => expect(api.de("GET", "/admin/metricas/canales")).toHaveLength(2));
  });

  it("«¿Cómo le fue?» muestra el texto, las fuentes y lo que faltó", async () => {
    const u = userEvent.setup();
    const api = abrir({ "POST /admin/metricas/resumen": RESUMEN });
    await u.click(await screen.findByRole("button", { name: "¿Cómo le fue?" }));
    expect((await screen.findAllByText("bien")).length).toBeGreaterThan(0);
    expect(screen.getByText("¿Cómo le fue a Lo común nos convoca?")).toBeInTheDocument(); // también queda en la conversación del asesor
    expect(screen.getAllByText("De dónde salen los números").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Instagram (desde la plataforma, 8/11)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lo que faltó").length).toBeGreaterThan(0);
    expect(screen.getAllByText("YouTube: sin datos").length).toBeGreaterThan(0);
    expect(screen.getByText(/Polarizaciones/)).toBeInTheDocument();
    expect(api.de("POST", "/admin/metricas/resumen")[0].cuerpo).toEqual({ ref: "c1", dias: 90 });
    expect(screen.getByRole("button", { name: "Volver a resumir" })).toBeInTheDocument();
  });

  it("un resumen guardado aparece con su fecha y el botón dice «Volver a resumir»", async () => {
    abrir({ "GET /admin/metricas/resumen/c1": RESUMEN });
    expect(await screen.findByRole("button", { name: "Volver a resumir" })).toBeInTheDocument();
    expect(screen.getByText(/Resumido el/)).toBeInTheDocument();
  });

  it("actualizar muestra el resultado por canal", async () => {
    const u = userEvent.setup();
    abrir({ "POST /admin/metricas/actualizar": { capturado: ahora, instagram: { ok: true, piezas: 4, error: null }, facebook: { ok: false, piezas: 0, error: "Falta el permiso read_insights" }, youtube: { ok: false, piezas: 2, error: "Falta autorizar la lectura de estadísticas de YouTube (correr autorizar_youtube.py de nuevo)" } } });
    await u.click(await screen.findByRole("button", { name: /Actualizar desde Instagram, Facebook y YouTube/ }));
    expect(await screen.findByText(/Instagram: 4 piezas leídas/)).toBeInTheDocument();
    expect(screen.getByText(/Facebook: falta un permiso en la conexión/)).toBeInTheDocument();
    expect(screen.getByText(/YouTube: falta un permiso en la conexión/)).toBeInTheDocument();
  });

  it("el menú de Administración no muestra «Métricas», pero la ruta directa abre la pantalla", async () => {
    abrir();
    expect(await screen.findByRole("article", { name: "Instagram" })).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Administración" })).queryByText("Métricas")).not.toBeInTheDocument();
  });
});
