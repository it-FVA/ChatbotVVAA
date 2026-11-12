// (8/11, Franco) Pantalla Métricas con la API simulada (contrato: web/maquetas/metricas-contrato.md).
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { instalarApi } from "../../pruebas/apiSimulada";

vi.mock("../../App", () => ({
  useSesion: () => ({ yo: { usuario: "ana", rol: { nombre: "admin", admin: true, aprueba: true, publica: true, etiqueta: "Administrador" } }, cargando: false, setYo: () => {} }),
}));

import Aprobacion from "../Aprobacion";
import Metricas from "./Metricas";
import RedirigeMetricas from "./RedirigeMetricas";

const ahora = new Date().toISOString();
const G0 = { publicada: 0, programada: 0, en_aprobacion: 0, borrador: 0, prueba: 0, no_salio: 0 };
const CAMPANAS = {
  periodo: { tipo: "dias", dias: 90, desde: "2026-08-10", hasta: null, texto: "últimos 90 días" },
  campanas: [
    {
      id: "c1", nombre: "Lo común nos convoca", emoji: "🤝", color: "#3a6b35", dueno: "pato", creado: ahora, piezas_total: 3,
      por_canal: { instagram: { ...G0, publicada: 1, programada: 1, borrador: 1 } }, por_estado: { ...G0, publicada: 1, programada: 1, borrador: 1 }, primera: ahora, ultima: ahora,
      piezas: [
        { id: "p1", canal: "instagram", canal_texto: "Instagram", titulo: "Gratitud en casa", estado: "publicada", estado_grupo: "publicada", fecha: "2026-11-05T12:00:00+00:00", ver_url: "https://instagram.com/p/x", formato: "cuadrado", usuario: "pato", modo: "real", metricas: { alcance: 120, me_gusta: 14, fuente: "api", capturado: ahora } },
        { id: "p2", canal: "instagram", canal_texto: "Instagram", titulo: "Mañana sale", estado: "pendiente", estado_grupo: "programada", fecha: "2026-11-09T12:00:00+00:00", ver_url: null, formato: "historia", usuario: "pato", modo: "real", metricas: null },
        { id: "p3", canal: "instagram", canal_texto: "Instagram", titulo: "Idea a medias", estado: "borrador", estado_grupo: "borrador", fecha: "2026-11-04T12:00:00+00:00", ver_url: null, formato: null, usuario: "pato", modo: "real", metricas: null },
      ],
    },
    {
      id: "frase_del_dia", nombre: "Frase del día (automática)", emoji: "📅", color: null, dueno: null, creado: null, piezas_total: 1,
      por_canal: { instagram: { ...G0, publicada: 1 } }, por_estado: { ...G0, publicada: 1 }, primera: ahora, ultima: ahora,
      piezas: [{ id: "f1", canal: "instagram", canal_texto: "Instagram", titulo: "Frase de ayer", estado: "publicada", estado_grupo: "publicada", fecha: "2026-11-07T12:00:00+00:00", ver_url: null, formato: "historia", usuario: "frase_del_dia", modo: "real", metricas: null }],
    },
  ],
  sueltas: {
    id: "sueltas", nombre: "Sin campaña", emoji: null, color: null, dueno: null, creado: null, piezas_total: 1, por_canal: { facebook: { ...G0, publicada: 1 } }, por_estado: { ...G0, publicada: 1 }, primera: ahora, ultima: ahora,
    piezas: [{ id: "s1", canal: "facebook", canal_texto: "Facebook", titulo: "Una suelta", estado: "publicada", estado_grupo: "publicada", fecha: "2026-11-06T12:00:00+00:00", ver_url: null, formato: "cuadrado", usuario: "pato", modo: "real", metricas: null }],
  },
  totales: { piezas: 4, ...G0, publicada: 3, programada: 1, borrador: 1, prueba: 2, por_canal: { instagram: 3, facebook: 1 } },
};
const CANALES = {
  actualizado: ahora,
  canales: [
    { clave: "instagram", texto: "Instagram", icono: "instagram", modo: "real", configurado: true, api: "sin_permiso", nota_api: "Falta el permiso instagram_manage_insights", enlace: "https://business.facebook.com/latest/insights/overview", enlace_texto: "Ver en Meta Business Suite", ultima: null, manual: { datos: { alcance: 1500 }, periodo_desde: "2026-10-01", periodo_hasta: "2026-10-31", capturado: ahora, nota: "Del panel", por: "franco" } },
    { clave: "facebook", texto: "Facebook", icono: "facebook", modo: "real", configurado: true, api: "disponible", nota_api: null, enlace: null, enlace_texto: null, ultima: { datos: { alcance: 1200, seguidores: 3400 }, periodo_desde: "2026-10-10", periodo_hasta: "2026-11-08", capturado: ahora, fuente: "api" }, manual: null },
    { clave: "mail", texto: "Mail", icono: "sobre", modo: "real", configurado: true, api: "no_hay", nota_api: "Perfit: los reportes se ven en la plataforma", enlace: "https://app.myperfit.com/", enlace_texto: "Ver en Perfit", ultima: null, manual: null },
  ],
};
const RESUMEN = { ref: "c1", nombre: "Lo común nos convoca", texto: "Le fue **bien** en Instagram.", fuentes: ["Instagram (desde la plataforma, 8/11)"], falto: ["YouTube: sin datos"], comparado_con: "Polarizaciones", modelo: "gpt", capturado: ahora };

const PROYECTOS = {
  proyectos: [
    { id: "pr1", nombre: "Lo común nos convoca", emoji: "🤝", permiso: "dueño", dueno: "pato", padre_id: null, color: null, descripcion: null, creado: ahora, actualizado: ahora },
    { id: "pr2", nombre: "Solo para mirar", emoji: null, permiso: "ver", dueno: "otro", padre_id: null, color: null, descripcion: null, creado: ahora, actualizado: ahora },
  ],
  ubicaciones: {},
};
const APERTURA = { texto: "Esta semana se movió **Lo común**.", fuentes: ["Instagram (desde la plataforma, 8/11)"], falto: [], capturado: ahora, nuevo: true };

function Lugar() {
  const l = useLocation();
  return <p>{l.pathname + l.search}</p>;
}

function abrir(extra: Record<string, unknown> = {}, ruta = "/aprobacion/metricas") {
  const api = instalarApi({ "GET /admin/metricas/campanas": CAMPANAS, "GET /admin/metricas/canales": CANALES, "GET /admin/metricas/resumen/c1": null, "GET /admin/metricas/asesor/apertura": APERTURA, "GET /proyectos": PROYECTOS, "GET /admin/resumen": { salud: { estado: "ok" }, costo: null, registro_desde: "" }, ...extra });
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/aprobacion" element={<Aprobacion />}>
          <Route path="metricas" element={<Metricas />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  return api;
}

describe("Métricas", () => {
  it("vive en Gestión: /aprobacion/metricas muestra la pantalla y el menú ofrece «Métricas» (destapada el 12/11)", async () => {
    abrir();
    expect(await screen.findByRole("article", { name: "Instagram" })).toBeInTheDocument();
    expect(within(screen.getByRole("navigation", { name: "Aprobación" })).getByText("Métricas")).toBeInTheDocument();
  });

  it("/administracion/metricas redirige a /aprobacion/metricas conservando la consulta", async () => {
    render(
      <MemoryRouter initialEntries={["/administracion/metricas?wordpress=ok"]}>
        <Routes>
          <Route path="/administracion/metricas" element={<RedirigeMetricas />} />
          <Route path="/aprobacion/metricas" element={<Lugar />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("/aprobacion/metricas?wordpress=ok")).toBeInTheDocument();
  });

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
    await u.click(within(mail).getByRole("button", { name: /Cargar números a mano/ }));
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
    await u.click((await screen.findAllByRole("button", { name: "¿Cómo le fue?" }))[0]);
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
    abrir({ "POST /admin/metricas/actualizar": { capturado: ahora, instagram: { ok: true, piezas: 4, error: null }, facebook: { ok: false, piezas: 0, error: "Falta el permiso read_insights" }, youtube: { ok: false, piezas: 2, error: "Falta autorizar la lectura de estadísticas de YouTube (correr autorizar_youtube.py de nuevo)" }, sitio: { ok: false, piezas: 0, error: "Falta conectar con WordPress.com (un clic)" }, mail: { ok: true, piezas: 3, error: null } } });
    await u.click(await screen.findByRole("button", { name: /Actualizar desde las plataformas/ }));
    expect(await screen.findByText(/Instagram: 4 piezas leídas/)).toBeInTheDocument();
    expect(screen.getByText(/Facebook: falta un permiso en la conexión/)).toBeInTheDocument();
    expect(screen.getByText(/YouTube: falta un permiso en la conexión/)).toBeInTheDocument();
    expect(screen.getByText(/Mail: 3 piezas leídas/)).toBeInTheDocument();      // (8/11, Franco) Perfit
  });
  it("las tarjetas de canal: el enlace es el chip, y cargar a mano explica para qué", async () => {
    abrir();
    const mail = await screen.findByRole("article", { name: "Mail" });
    expect(within(mail).getAllByRole("link", { name: /Ver en Perfit/ })).toHaveLength(2); // el chip de arriba y el botón de siempre
    expect(within(mail).queryByText("se mira en la plataforma")).not.toBeInTheDocument();
    expect(within(mail).getByText(/Para lo que la plataforma no nos deja leer solo: copiá acá lo que ves en sus estadísticas, con el período\./)).toBeInTheDocument();
    // (8/11, Franco) conectado: no se ofrece cargar a mano (la plataforma los lee sola)
    const fb = screen.getByRole("article", { name: "Facebook" });
    expect(within(fb).queryByText("¿Preferís cargarlos a mano?")).toBeNull();
    expect(within(fb).queryByRole("button", { name: /Cargar números a mano/ })).toBeNull();
  });

  it("los borradores van plegados aparte y los totales no los cuentan", async () => {
    abrir();
    expect(await screen.findByText("1 borrador")).toBeInTheDocument();
    expect(screen.getByText("Idea a medias")).toBeInTheDocument();
    expect(screen.getByText("Aparte: 2 en prueba, 1 borrador.")).toBeInTheDocument();
    expect(screen.getByText("Piezas hechas").closest(".metrica")).toHaveTextContent("4");
    const c1 = screen.getByRole("region", { name: "Lo común nos convoca" });
    expect(within(c1).queryByText("Borradores")).not.toBeInTheDocument(); // ni columna en la tabla
    expect(screen.getByRole("region", { name: "Frase del día (automática)" })).toBeInTheDocument();
  });

  it("«Mover a campaña» mueve una pieza suelta a un Proyecto y recarga las campañas", async () => {
    const u = userEvent.setup();
    const api = abrir({ "POST /proyectos/pr1/items": { ok: true, ya: false, item: {} } });
    const suelta = await screen.findByRole("region", { name: "Sin campaña" });
    await u.click(within(suelta).getByText("Piezas"));
    await u.click(within(suelta).getByRole("button", { name: /Mover a campaña/ }));
    const sel = await within(suelta).findByLabelText("Campaña de destino");
    await waitFor(() => expect(within(sel).getByRole("option", { name: "🤝 Lo común nos convoca" })).toBeInTheDocument());
    expect(within(sel).queryByRole("option", { name: "Solo para mirar" })).not.toBeInTheDocument(); // solo las que se pueden editar
    await u.selectOptions(sel, "pr1");
    await u.click(within(suelta).getByRole("button", { name: "Mover" }));
    await waitFor(() => expect(api.de("POST", "/proyectos/pr1/items")).toHaveLength(1));
    expect(api.de("POST", "/proyectos/pr1/items")[0].cuerpo).toEqual({ tipo: "pieza", item_id: "s1", datos: null });
    await waitFor(() => expect(api.de("GET", "/admin/metricas/campanas")).toHaveLength(2));
  });

  it("«Nueva campaña…» crea el Proyecto y mueve la pieza de la Frase del día", async () => {
    const u = userEvent.setup();
    const api = abrir({ "POST /proyectos": { id: "pr9", nombre: "Noviembre" }, "POST /proyectos/pr9/items": { ok: true, ya: false, item: {} } });
    const frase = await screen.findByRole("region", { name: "Frase del día (automática)" });
    await u.click(within(frase).getByText("Piezas"));
    await u.click(within(frase).getByRole("button", { name: /Mover a campaña/ }));
    await u.selectOptions(await within(frase).findByLabelText("Campaña de destino"), "__nueva");
    await u.type(within(frase).getByLabelText("Nombre de la campaña nueva"), "Noviembre");
    await u.click(within(frase).getByRole("button", { name: "Mover" }));
    await waitFor(() => expect(api.de("POST", "/proyectos/pr9/items")).toHaveLength(1));
    expect((api.de("POST", "/proyectos")[0].cuerpo as { nombre: string }).nombre).toBe("Noviembre");
    expect(api.de("POST", "/proyectos/pr9/items")[0].cuerpo).toEqual({ tipo: "pieza", item_id: "f1", datos: null });
  });

  it("si no puede mover la pieza, muestra el motivo en castellano", async () => {
    const u = userEvent.setup();
    const api = abrir({ "POST /proyectos/pr1/items": new Response(JSON.stringify({ detail: "Este proyecto lo tenés solo para ver: no podés cambiarlo." }), { status: 403, headers: { "Content-Type": "application/json" } }) });
    const suelta = await screen.findByRole("region", { name: "Sin campaña" });
    await u.click(within(suelta).getByText("Piezas"));
    await u.click(within(suelta).getByRole("button", { name: /Mover a campaña/ }));
    await u.selectOptions(await within(suelta).findByLabelText("Campaña de destino"), "pr1");
    await u.click(within(suelta).getByRole("button", { name: "Mover" }));
    expect(await within(suelta).findByText(/lo tenés solo para ver/)).toBeInTheDocument();
    expect(api.de("GET", "/admin/metricas/campanas")).toHaveLength(1); // no recargó
  });
});

const SITIO = { clave: "sitio", texto: "Sitio web", icono: "casa", modo: "real", enlace: "https://wordpress.com/stats/day/viviragradecidos.org", enlace_texto: "Ver en WordPress.com", manual: null };
const conSitio = (c: Record<string, unknown>) => ({ "GET /admin/metricas/canales": { ...CANALES, canales: [...CANALES.canales, { ...SITIO, configurado: true, ultima: null, ...c }] } });

describe("Métricas · Sitio web (WordPress.com)", () => {
  it("falta conectar: botón «Conectar con WordPress.com» que navega a la API, sin Desconectar", async () => {
    abrir(conSitio({ api: "pendiente", nota_api: "Falta conectar con WordPress.com (un clic)", conectado: false, conectar_url: "/admin/metricas/wordpress/autorizar" }));
    const sitio = await screen.findByRole("article", { name: "Sitio web" });
    const boton = within(sitio).getByRole("link", { name: /Conectar con WordPress.com/ });
    expect(boton.getAttribute("href")).toMatch(/\/admin\/metricas\/wordpress\/autorizar$/);
    expect(within(sitio).getByText("Falta conectar con WordPress.com (un clic)")).toBeInTheDocument();
    expect(within(sitio).queryByRole("button", { name: "Desconectar" })).not.toBeInTheDocument();
  });

  it("conectado y leído: muestra los números y «Desconectar» pide confirmación y manda DELETE", async () => {
    const u = userEvent.setup();
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const api = abrir({ ...conSitio({ api: "disponible", nota_api: "", conectado: true, conectar_url: "/admin/metricas/wordpress/autorizar", ultima: { datos: { visitas: 2400, visitantes: 900 }, periodo_desde: "2026-10-11", periodo_hasta: "2026-11-08", capturado: ahora, fuente: "api" } }), "DELETE /admin/metricas/wordpress": { ok: true } });
    const sitio = await screen.findByRole("article", { name: "Sitio web" });
    expect(within(sitio).getByText("conectado")).toBeInTheDocument();
    expect(within(sitio).getByText("2.400")).toBeInTheDocument();
    expect(within(sitio).queryByRole("link", { name: /Conectar con WordPress.com/ })).not.toBeInTheDocument();
    await u.click(within(sitio).getByRole("button", { name: "Desconectar" }));
    expect(confirmar).toHaveBeenCalled();
    await waitFor(() => expect(api.de("DELETE", "/admin/metricas/wordpress")).toHaveLength(1));
    expect(await screen.findByText("Sitio desconectado de WordPress.com.")).toBeInTheDocument();
    confirmar.mockRestore();
  });

  it("sin app registrada: solo el enlace a la plataforma, sin botón de conectar", async () => {
    abrir(conSitio({ api: "no_hay", nota_api: "WordPress.com pide autorizar una app propia para leer las estadísticas; por ahora, el enlace.", conectado: false, conectar_url: null }));
    const sitio = await screen.findByRole("article", { name: "Sitio web" });
    expect(within(sitio).queryByRole("link", { name: /Conectar con WordPress.com/ })).not.toBeInTheDocument();
    expect(within(sitio).getAllByRole("link", { name: /Ver en WordPress.com/ }).length).toBeGreaterThan(0);
  });

  it("al volver de WordPress.com avisa y limpia la dirección", async () => {
    abrir({}, "/aprobacion/metricas?wordpress=ok");
    expect(await screen.findByText("WordPress.com conectado: tocá Actualizar.")).toBeInTheDocument();
  });

  it("al volver con error muestra el motivo", async () => {
    abrir({}, "/aprobacion/metricas?wordpress=error&motivo=WordPress.com%20no%20dio%20el%20permiso.");
    expect(await screen.findByText("WordPress.com no dio el permiso.")).toBeInTheDocument();
  });
});

// ---------------- Métricas v3: datos (12/11, Franco) ----------------
const fila = (datos: Record<string, unknown>) => ({ datos, periodo_desde: "2026-10-15", periodo_hasta: "2026-11-12", capturado: ahora, fuente: "api" });
const canal = (clave: string, texto: string, extra: Record<string, unknown>) => ({ clave, texto, icono: clave, modo: "real", configurado: true, api: "disponible", nota_api: "", enlace: null, enlace_texto: null, manual: null, anterior: null, tasas: {}, ...extra });

describe("Métricas v3: tarjetas con números coherentes", () => {
  it("el mail sin campañas muestra la Frase del día y la lista, y avisa que las aperturas no las da Perfit", async () => {
    abrir({ "GET /admin/metricas/canales": { actualizado: ahora, canales: [canal("mail", "Mail (Newsletter y Frase del día)", { ultima: fila({ enviados: 0, aperturas: 0, clics: 0, enviados_frase: 18867, lista_contactos: 2241 }), tasas: { aperturas_sobre_enviados: null, clics_sobre_enviados: null } })] } });
    const mail = await screen.findByRole("article", { name: /Mail/ });
    expect(within(mail).getByText("18.867")).toBeInTheDocument();
    expect(within(mail).getByText("Frase del día: mails enviados")).toBeInTheDocument();
    expect(within(mail).getByText("2.241")).toBeInTheDocument();
    expect(within(mail).getByText("Lista: contactos")).toBeInTheDocument();
    expect(within(mail).getByText("Las aperturas de la Frase del día no las da Perfit por ahora; las campañas sí.")).toBeInTheDocument();
    expect(within(mail).queryByText(/aperturas =/)).toBeNull();               // sin enviados de campañas no hay tasa
    // los ceros de las campañas no tapan a la Frase del día: salen detrás
    const etiquetas = within(mail).getAllByText(/./, { selector: ".metrica-etiqueta" }).map((e) => e.textContent);
    expect(etiquetas.slice(0, 2)).toEqual(["Frase del día: mails enviados", "Lista: contactos"]);
  });

  it("el sitio muestra visitas y visitantes del período con las visitas por día", async () => {
    abrir({ "GET /admin/metricas/canales": { actualizado: ahora, canales: [canal("sitio", "Sitio web", { ultima: fila({ visitas: 12352, visitantes: 4100 }), tasas: { visitas_por_dia: 441.143 } })] } });
    const sitio = await screen.findByRole("article", { name: "Sitio web" });
    expect(within(sitio).getByText("12.352")).toBeInTheDocument();
    expect(within(sitio).getByText("4.100")).toBeInTheDocument();
    expect(within(sitio).getByText("441 visitas por día")).toBeInTheDocument();
  });

  it("YouTube muestra los minutos vistos y los suscriptores nuevos", async () => {
    abrir({ "GET /admin/metricas/canales": { actualizado: ahora, canales: [canal("youtube", "YouTube", { ultima: fila({ vistas: 3100, minutos_vistos: 9400, seguidores: 1200, seguidores_nuevos: 40, me_gusta: 210 }) })] } });
    const yt = await screen.findByRole("article", { name: "YouTube" });
    expect(within(yt).getByText("Minutos vistos")).toBeInTheDocument();
    expect(within(yt).getByText("9.400")).toBeInTheDocument();
    expect(within(yt).getByText("Suscriptores nuevos")).toBeInTheDocument();
    expect(within(yt).getByText("40")).toBeInTheDocument();
  });

  it("la línea «vs. período anterior» usa solo las claves de los dos períodos y la tasa va en chico", async () => {
    abrir({ "GET /admin/metricas/canales": { actualizado: ahora, canales: [canal("instagram", "Instagram", {
      ultima: fila({ alcance: 3360, seguidores: 10100, vistas: 500 }),
      anterior: { datos: { alcance: 3000, seguidores: 9999, me_gusta: 4 }, periodo_desde: "2026-09-17", periodo_hasta: "2026-10-15", capturado: ahora },
      tasas: { alcance_sobre_seguidores: 0.333, interacciones_sobre_alcance: null } })] } });
    const ig = await screen.findByRole("article", { name: "Instagram" });
    expect(within(ig).getByText("vs. período anterior: alcance +12 %, seguidores +101")).toBeInTheDocument();    // me gusta no está en los dos: no aparece
    expect(within(ig).getByText("alcance = 33,3 % de los seguidores")).toBeInTheDocument();
  });

  it("sin período anterior no hay línea de comparación", async () => {
    abrir();
    const fb = await screen.findByRole("article", { name: "Facebook" });
    expect(within(fb).queryByText(/vs\. período anterior/)).toBeNull();
  });
});

describe("Métricas v3: estados y campañas", () => {
  const G = { ...G0, saliendo: 0, cancelada: 0 };
  const pieza = (id: string, estado: string, grupo: string, titulo: string) => ({ id, canal: "mail", canal_texto: "Mail", titulo, estado, estado_grupo: grupo, fecha: "2026-11-10T12:00:00+00:00", ver_url: null, formato: null, usuario: "frase_del_dia", modo: "real", metricas: null });
  const camp = (id: string, nombre: string, por: Record<string, number>, piezas: ReturnType<typeof pieza>[], extra: Record<string, unknown> = {}) => ({
    id, nombre, emoji: null, color: null, dueno: null, creado: null, descripcion: null, piezas_total: piezas.length, por_canal: { mail: { ...G, ...por } }, por_estado: { ...G, ...por }, primera: ahora, ultima: ahora, piezas, ...extra });

  it("saliendo y cancelada tienen su chip y su columna, con su texto", async () => {
    const f = camp("frase_del_dia", "Frase del día (automática)", { publicada: 3, saliendo: 1, cancelada: 5 },
      [pieza("a", "enviando", "saliendo", "Sale ahora"), pieza("b", "cancelada", "cancelada", "Cancelada por Franco"), pieza("c", "publicada", "publicada", "Ya salió")],
      { descripcion: "La plataforma la arma y la manda sola cada día: historia de Instagram y mail" });
    abrir({ "GET /admin/metricas/campanas": { ...CAMPANAS, campanas: [f], totales: { piezas: 4, ...G, publicada: 3, saliendo: 1, cancelada: 5, por_canal: { mail: 4 } } } });
    const r = await screen.findByRole("region", { name: "Frase del día (automática)" });
    expect(within(r).getByText("1 saliendo")).toBeInTheDocument();
    expect(within(r).getByText("5 canceladas")).toBeInTheDocument();
    expect(within(r).queryByText(/no salieron/)).toBeNull();                       // las canceladas no son «no salió»
    expect(within(r).getByRole("columnheader", { name: "Saliendo" })).toBeInTheDocument();
    expect(within(r).getByRole("columnheader", { name: "Canceladas" })).toBeInTheDocument();
    expect(within(r).getByText("La plataforma la arma y la manda sola cada día: historia de Instagram y mail")).toBeInTheDocument();
    await userEvent.setup().click(within(r).getByText("Piezas"));
    expect(within(r).getByText("saliendo", { selector: ".estado" })).toBeInTheDocument();
  });

  it("una campaña sin nada hecho dice que todavía no salió nada y cuenta lo demás aparte", async () => {
    const v = camp("c9", "Recién empieza", { borrador: 2, cancelada: 1, no_salio: 3 },
      [pieza("d1", "borrador", "borrador", "Idea"), pieza("d2", "cancelada", "cancelada", "Se canceló"), pieza("d3", "error", "no_salio", "Falló")], { usuario: "pato" });
    abrir({ "GET /admin/metricas/campanas": { ...CAMPANAS, campanas: [v] } });
    const r = await screen.findByRole("region", { name: "Recién empieza" });
    expect(within(r).getByText("Todavía no salió nada de esta campaña")).toBeInTheDocument();
    expect(within(r).getByText("2 borradores · 1 cancelada · 3 no salieron")).toBeInTheDocument();
    expect(within(r).queryByRole("table")).toBeNull();
  });
});
