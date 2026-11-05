import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Ayuda, { SECCIONES } from "./Ayuda";
import LinkAyuda from "../componentes/LinkAyuda";

const palabras = (t: string) => t.split(/\s+/).filter(Boolean).length;

describe("Ayuda", () => {
  it("muestra el índice y una sección por pantalla", () => {
    render(
      <MemoryRouter>
        <Ayuda />
      </MemoryRouter>,
    );
    for (const t of ["Chat", "Diseñar", "Mis publicaciones", "Mis recortes", "Newsletter", "Frase del día", "Proyectos y Compartidos", "Aprobación y Administración", "Si algo falla"]) {
      expect(screen.getByRole("heading", { level: 2, name: t })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: t })).toHaveAttribute("href", expect.stringMatching(/^#/));
    }
    expect(screen.getAllByText("Paso a paso")).toHaveLength(SECCIONES.length);
  });

  it("cada sección tiene de 3 a 6 pasos y hasta 120 palabras", () => {
    for (const s of SECCIONES) {
      expect(s.pasos.length).toBeGreaterThanOrEqual(3);
      expect(s.pasos.length).toBeLessThanOrEqual(6);
      expect(palabras([s.que, ...(s.lista || []), ...s.pasos].join(" "))).toBeLessThanOrEqual(120);
    }
  });

  it("LinkAyuda apunta a la sección", () => {
    render(
      <MemoryRouter>
        <LinkAyuda seccion="recortes" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "¿Cómo se usa?" })).toHaveAttribute("href", "/ayuda#recortes");
  });
});
