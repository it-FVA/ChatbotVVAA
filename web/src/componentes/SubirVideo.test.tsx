// El modal «Subir un video» con la API simulada (5/11).
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { instalarApi } from "../pruebas/apiSimulada";
import SubirVideo from "./SubirVideo";

describe("Subir un video", () => {
  it("manda archivo, título y formato, y avisa con el id", async () => {
    const api = instalarApi({ "POST /recortes/subir": { ok: true, id: "s1", url: "https://wp/x.mp4", aviso: null } });
    const onSubido = vi.fn();
    render(<SubirVideo onCerrar={() => undefined} onSubido={onSubido} />);
    const boton = screen.getByRole("button", { name: "Subir" });
    expect(boton).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("Archivo"), new File(["0123"], "mi-edicion.mp4", { type: "video/mp4" }));
    expect(screen.getByLabelText("Título")).toHaveValue("mi-edicion");
    await userEvent.click(screen.getByLabelText("Vertical"));
    await userEvent.click(boton);
    await waitFor(() => expect(onSubido).toHaveBeenCalledWith("s1"));
    expect(api.de("POST", "/recortes/subir")).toHaveLength(1);
  });

  it("muestra el error de la API y deja volver a intentar", async () => {
    instalarApi({ "POST /recortes/subir": () => { throw new Error("no se usa"); } });
    const f = vi.fn(async () => new Response(JSON.stringify({ detail: "El video pesa 250 MB; el máximo es 200 MB." }), { status: 413, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", f);
    render(<SubirVideo onCerrar={() => undefined} onSubido={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("Archivo"), new File(["0123"], "a.mp4", { type: "video/mp4" }));
    await userEvent.click(screen.getByRole("button", { name: "Subir" }));
    expect(await screen.findByText(/el máximo es 200 MB/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Subir" })).toBeEnabled();
  });
});
