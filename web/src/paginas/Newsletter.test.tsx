// (4/11, Franco) El newsletter con la misma lógica que las piezas: un newsletter de otra persona, rechazado, compartido con permiso
// «editar» por una carpeta, se abre en su editor con la nota del rechazo, se guarda en la misma fila y se reenvía con el mismo id.
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../componentes/Toasts";
import { instalarApi } from "../pruebas/apiSimulada";
import { PLANTILLAS_NEWSLETTER } from "../pruebas/plantillasNewsletter";
import Newsletter from "./Newsletter";

const vacio = PLANTILLAS_NEWSLETTER.vacios.mensual;

// jsdom no trae ResizeObserver y la vista previa del mail lo usa para medirse
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
});

function montar(ruta: string) {
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <ToastProvider>
        <Newsletter />
      </ToastProvider>
    </MemoryRouter>,
  );
}

function pantalla(borrador: Record<string, unknown>) {
  return instalarApi({
    "GET /newsletter/plantillas": PLANTILLAS_NEWSLETTER,
    "GET /banco": [],
    "POST /newsletter/html": { html: "<html></html>", titulo: "Octubre" },
    "GET /newsletter/borradores/n1": { id: "n1", titulo: "Octubre", plantilla: "mensual", datos: { ...vacio, asunto: "Octubre" }, creado: null, ...borrador },
    "POST /newsletter/borrador": { ok: true, id: "n1", estado: "borrador", mensaje: "Cambios guardados. El newsletter sigue siendo de patricio y queda en la misma carpeta." },
    "POST /newsletter/a-aprobar": { ok: true, id: "n1", estado: "a_aprobar", mensaje: "Quedó pendiente de aprobación (ana)." },
  });
}

describe("Newsletter", () => {
  it("uno ajeno y rechazado se corrige en el mismo lugar: muestra la nota, de quién es, «Guardar cambios» y reenvía con el mismo id", async () => {
    const u = userEvent.setup();
    const api = pantalla({ estado: "rechazada", duena: "patricio", propia: false, rechazo: { por: "julian", en: "2026-11-04T20:00:00+00:00", nota: "falta la agenda" } });
    montar("/newsletter?borrador=n1");
    expect(await screen.findByRole("note")).toHaveTextContent("Lo rechazó julian");
    expect(screen.getByRole("note")).toHaveTextContent("«falta la agenda»");
    expect(screen.getByText(/Estás editando un newsletter de patricio/)).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: /Guardar cambios/ }));
    await waitFor(() => expect(api.de("POST", "/newsletter/borrador")).toHaveLength(1));
    expect(api.de("POST", "/newsletter/borrador")[0].cuerpo).toMatchObject({ borrador_id: "n1", plantilla: "mensual" });

    await u.click(screen.getByRole("button", { name: /Enviar a aprobación/ }));
    await waitFor(() => expect(api.de("POST", "/newsletter/a-aprobar")).toHaveLength(1));
    expect(api.de("POST", "/newsletter/a-aprobar")[0].cuerpo).toMatchObject({ borrador_id: "n1" });
  });

  it("uno nuevo dice «Guardar borrador» y no muestra nota de rechazo", async () => {
    instalarApi({ "GET /newsletter/plantillas": PLANTILLAS_NEWSLETTER, "GET /banco": [], "POST /newsletter/html": { html: "<html></html>", titulo: "Newsletter" } });
    montar("/newsletter");
    expect(await screen.findByRole("button", { name: /Guardar borrador/ })).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
