// (5/11, QA visual) El chip de estado: un tono por familia de estados y «prueba» en lugar de «simulada/simulado».
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ChipEstado, { textoEstado } from "./ChipEstado";

describe("ChipEstado", () => {
  it("usa el mismo tono para los estados de una misma familia", () => {
    const { container } = render(
      <>
        <ChipEstado estado="a_aprobar" texto="a aprobar" />
        <ChipEstado estado="programada" texto="aprobada · programada" />
        <ChipEstado estado="publicada" texto="publicada" />
        <ChipEstado estado="rechazada" texto="rechazada" />
        <ChipEstado estado="borrador" texto="borrador" />
        <ChipEstado estado="listo" texto="listo" />
      </>,
    );
    const clases = [...container.querySelectorAll(".estado")].map((e) => e.className);
    expect(clases).toEqual(["estado espera", "estado programada", "estado listo", "estado error", "estado neutro", "estado listo"]);
  });

  it("traduce «simulada» y «simulado» a «prueba» y no dibuja nada sin texto", () => {
    expect(textoEstado("simulada", "simulada")).toBe("prueba");
    expect(textoEstado("simulado", "simulado")).toBe("prueba");
    expect(textoEstado("publicada", "publicada")).toBe("publicada");
    const { container } = render(
      <>
        <ChipEstado estado="simulada" texto="simulada" />
        <ChipEstado estado="" texto="" />
      </>,
    );
    expect(screen.getByText("prueba")).toHaveClass("estado", "neutro");
    expect(container.querySelectorAll(".estado")).toHaveLength(1);
  });
});
