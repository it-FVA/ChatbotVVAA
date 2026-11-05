// (5/11) Presencia y aviso de conflicto con la API simulada: los chips de «quién está acá» en Diseñar, y el 409 al guardar un borrador
// que otra persona guardó antes (dos salidas: recargar o guardar igual, pisando).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "../componentes/Toasts";
import { instalarApi } from "../pruebas/apiSimulada";
import type { OpcionesPublicar } from "../tiposPublicar";
import Publicar from "./Publicar";

const OPCIONES = {
  canales: { facebook: { nombre: "Facebook", texto_canal: "Facebook", detalle: "Posteo en Facebook", modo_real: "simulado", modo: "simulado", texto: "simulado", a_aprobar: true, acepta_aprobacion: true, requiere_titulo: false, formato: "cuadrado", va_a_la_cola: true, configurado: true, aviso_sin_fecha: "Se arma.", aviso_con_fecha: "Se programa para {cuando}." } },
  publica: true, aprueba: true, rol: "admin", aprobadores: ["ana"], usuario: "ana", logos: ["Ninguno"], logos_url: {}, posiciones_logo: ["Abajo a la derecha"],
  tipografias: ["Raleway"], tipografia_defecto: "Raleway", pesos: ["Normal"], posiciones: ["Centro"], alineaciones: ["Centro"], formatos: { cuadrado: [1080, 1080] },
  formato_por_canal: { facebook: "cuadrado" }, firma_defecto: "Vivir Agradecidos", zona: "America/Argentina/Buenos_Aires",
} as unknown as OpcionesPublicar;

const BORRADOR = {
  id: "b1", creado: "2026-11-05T12:00:00+00:00", usuario: "ana", canal: "facebook", modo: "borrador", titulo: "Gratitud", texto: "Hoy agradezco.", imagen_url: null, estado: "borrador",
  fecha_programada: null, resultado: null, estado_texto: "Borrador", canal_texto: "Facebook", video_url: null, texto_imagen: null, formato: null, nota: null, propuesta_por: null,
  aprobada_por: null, aprobada_en: null, rechazada_por: null, rechazada_en: null, cancelada_por: null, plantilla: null, ver_url: null, link_editar: null, error_texto: null,
  eliminable: true, retomable: true, propia: true, permiso: "dueño", version: "v1",
  pieza: { canal: "facebook", titulo: "Gratitud", texto: "Hoy agradezco.", texto_imagen: "Gracias", firma: "", imagen_busqueda: "", fecha: "", hora: "", borrador_id: "b1" },
};

const OTRO_GUARDO = new Response(
  JSON.stringify({ detail: "Otra persona guardó esta pieza hace 2 minutos (Julián). Recargá para ver sus cambios antes de guardar los tuyos.", version_actual: "v2", editada_por: "julian" }),
  { status: 409, headers: { "Content-Type": "application/json" } },
);

function abrir(rutas: Record<string, unknown> = {}) {
  const api = instalarApi({
    "GET /publicar/opciones": OPCIONES,
    "GET /banco": [],
    "GET /publicaciones/b1": BORRADOR,
    "POST /presencia/pieza/b1": { presentes: [{ usuario: "julian", nombre: "Julián", modo: "edita", hace_seg: 4 }, { usuario: "pato", nombre: "Pato", modo: "mira", hace_seg: 12 }] },
    "DELETE /presencia/pieza/b1": { ok: true },
    ...rutas,
  });
  render(
    <MemoryRouter initialEntries={["/publicar?borrador=b1"]}>
      <ToastProvider>
        <Publicar />
      </ToastProvider>
    </MemoryRouter>,
  );
  return api;
}

describe("Presencia en Diseñar", () => {
  it("muestra quién está editando y quién mirando, y late como editor de la pieza", async () => {
    const api = abrir();
    expect(await screen.findByText("Julián está editando")).toBeInTheDocument();
    expect(screen.getByText("Pato está mirando")).toBeInTheDocument();
    expect(api.de("POST", "/presencia/pieza/b1")[0].cuerpo).toEqual({ modo: "edita" });
  });

  it("sin guardar todavía no late y explica cuándo aparece", async () => {
    const api = instalarApi({ "GET /publicar/opciones": OPCIONES, "GET /banco": [] });
    render(
      <MemoryRouter initialEntries={["/publicar?canal=facebook"]}>
        <ToastProvider>
          <Publicar />
        </ToastProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText(/Cuando la guardes como borrador/)).toBeInTheDocument();
    expect(api.llamadas.filter((l) => l.ruta.startsWith("/presencia"))).toHaveLength(0);
  });
});

describe("Aviso de conflicto al guardar", () => {
  async function guardar(u: ReturnType<typeof userEvent.setup>) {
    await screen.findByText("Julián está editando");
    await u.click(await screen.findByRole("button", { name: /Siguiente: cuándo y enviar/ }));
    await u.click(await screen.findByRole("button", { name: /Guardar cambios/ }));
  }

  it("manda la versión que cargó y, ante un 409, muestra el aviso; «Guardar igual» reintenta sin versión", async () => {
    const u = userEvent.setup();
    let n = 0;
    const api = abrir({ "POST /publicar/borrador": () => (++n === 1 ? OTRO_GUARDO.clone() : { ok: true, id: "b1", estado: "borrador", version: "v3", mensaje: "Cambios guardados en el mismo borrador." }) });
    await guardar(u);
    const aviso = await screen.findByRole("dialog");
    expect(aviso).toHaveTextContent("Otra persona guardó esta pieza hace 2 minutos (Julián)");
    expect(api.de("POST", "/publicar/borrador")[0].cuerpo).toMatchObject({ borrador_id: "b1", version: "v1" });
    await u.click(screen.getByRole("button", { name: "Guardar igual, pisando" }));
    await waitFor(() => expect(api.de("POST", "/publicar/borrador")).toHaveLength(2));
    expect(api.de("POST", "/publicar/borrador")[1].cuerpo).toMatchObject({ borrador_id: "b1", version: null });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("«Recargar y ver sus cambios» vuelve a pedir la pieza", async () => {
    const u = userEvent.setup();
    const api = abrir({ "POST /publicar/borrador": () => OTRO_GUARDO.clone() });
    await guardar(u);
    await screen.findByRole("dialog");
    expect(api.de("GET", "/publicaciones/b1")).toHaveLength(1);
    await u.click(screen.getByRole("button", { name: "Recargar y ver sus cambios" }));
    await waitFor(() => expect(api.de("GET", "/publicaciones/b1")).toHaveLength(2));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
