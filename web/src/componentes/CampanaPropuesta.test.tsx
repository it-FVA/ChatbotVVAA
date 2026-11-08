// (8/11, Beto) El recuadro de la campaña que guardó el chat: el link al Proyecto y una fila por pieza con «Abrir en Diseñar».
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Campana } from "../tiposChat";
import CampanaPropuesta from "./CampanaPropuesta";

const CAMPANA: Campana = {
  proyecto_id: "pr1",
  nombre: "Confianza plena en la vida",
  piezas: [
    { id: "b1", canal: "instagram", canal_texto: "Instagram", titulo: "Confiar es soltar", formato: "historia", fuente: "«Gratitud» — Br. David", porque: "La historia conversa con los que ya nos siguen.", url_editar: "/publicar?borrador=b1" },
    { id: "b2", canal: "newsletter", canal_texto: "Newsletter", titulo: "Una semana de confianza", formato: "", fuente: "«Confiar» — Br. David", porque: "El mail es gente propia.", url_editar: "/newsletter?borrador=b2" },
    { id: "b3", canal: "facebook", canal_texto: "Facebook", titulo: "La misma tarjeta", formato: "cuadrado", fuente: "", porque: "", url_editar: "/publicar?borrador=b3" },
  ],
};

describe("CampanaPropuesta", () => {
  it("muestra el nombre, el link al proyecto y una fila por pieza", () => {
    render(<MemoryRouter><CampanaPropuesta campana={CAMPANA} /></MemoryRouter>);
    expect(screen.getByText("Campaña guardada: Confianza plena en la vida")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver el proyecto" })).toHaveAttribute("href", "/proyectos/pr1");
    const filas = screen.getAllByRole("listitem");
    expect(filas).toHaveLength(3);
    expect(within(filas[0]).getByText("Confiar es soltar")).toBeInTheDocument();
    expect(within(filas[0]).getByText(/Instagram · historia/)).toBeInTheDocument();
    expect(within(filas[0]).getByText(/Fuente: «Gratitud» — Br. David/)).toBeInTheDocument();
    expect(within(filas[2]).getByText(/Facebook · posteo cuadrado/)).toBeInTheDocument();
  });

  it("cada botón «Abrir en Diseñar» lleva al borrador de su pieza (el newsletter, a su editor)", () => {
    render(<MemoryRouter><CampanaPropuesta campana={CAMPANA} /></MemoryRouter>);
    const botones = screen.getAllByRole("link", { name: /Abrir en Diseñar/ });
    expect(botones.map((b) => b.getAttribute("href"))).toEqual(["/publicar?borrador=b1", "/newsletter?borrador=b2", "/publicar?borrador=b3"]);
  });
});
