import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Ayuda from "./Ayuda";
import { todasLasAyudas } from "../ayuda";
import LinkAyuda from "../componentes/LinkAyuda";

const palabras = (t: string) => t.split(/\s+/).filter(Boolean).length;

describe("Ayuda", () => {
  it("muestra el índice y una sección por pantalla", () => {
    render(
      <MemoryRouter>
        <Ayuda />
      </MemoryRouter>,
    );
    for (const t of ["Chat", "Diseñar", "Mis publicaciones", "Mis recortes", "Newsletter", "Frase del día", "Proyectos", "Compartidos", "Aprobación", "Administración", "Si algo falla"]) {
      expect(screen.getByRole("heading", { level: 2, name: t })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: t })).toHaveAttribute("href", expect.stringMatching(/^#/));
    }
    expect(screen.getAllByText("Paso a paso")).toHaveLength(todasLasAyudas().length);
  });

  it("cada sección tiene de 1 a 6 pasos y hasta 120 palabras", () => {
    for (const [, s] of todasLasAyudas()) {
      expect(s.pasos.length).toBeGreaterThanOrEqual(1);
      expect(s.pasos.length).toBeLessThanOrEqual(6);
      expect(palabras([s.que, ...(s.lista || []), ...s.pasos.map((p) => p.texto)].join(" ")), s.titulo).toBeLessThanOrEqual(120);
    }
  });

  it("LinkAyuda ofrece la guía y «Leer la ayuda», que apunta a la sección", async () => {
    const u = userEvent.setup();
    render(
      <MemoryRouter>
        <LinkAyuda pantalla="recortes" />
      </MemoryRouter>,
    );
    await u.click(screen.getByRole("button", { name: /¿Cómo se usa\?/ }));
    expect(screen.getByRole("menuitem", { name: /Guía en pantalla/ })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Leer la ayuda/ })).toHaveAttribute("href", "/ayuda#recortes");
  });
});
