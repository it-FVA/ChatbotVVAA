import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { todasLasAyudas } from "../ayuda";
import LinkAyuda from "./LinkAyuda";

const palabras = (t: string) => t.split(/\s+/).filter(Boolean).length;

// (5/11) antes vivía en paginas/Ayuda.test.tsx; la página se fue, el límite de la ayuda se queda.
describe("Ayuda de cada pantalla", () => {
  it("cada sección tiene de 1 a 6 pasos y hasta 120 palabras", () => {
    for (const [, s] of todasLasAyudas()) {
      expect(s.pasos.length).toBeGreaterThanOrEqual(1);
      expect(s.pasos.length).toBeLessThanOrEqual(6);
      expect(palabras([s.que, ...(s.lista || []), ...s.pasos.map((p) => p.texto)].join(" ")), s.titulo).toBeLessThanOrEqual(120);
    }
  });

  it("«¿Cómo se usa?» abre la guía en pantalla directamente, sin menú", async () => {
    const u = userEvent.setup();
    render(
      <MemoryRouter>
        <LinkAyuda pantalla="recortes" />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /¿Cómo se usa\?/ }));
    expect(screen.queryByRole("menuitem")).not.toBeInTheDocument();
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
