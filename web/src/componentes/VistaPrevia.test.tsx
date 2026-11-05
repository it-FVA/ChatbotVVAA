// (5/11, Franco) La vista previa del carrusel: la foto actual, flechas, puntitos y el contador.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import VistaPrevia, { type DatosPrevia } from "./VistaPrevia";

const BASE: DatosPrevia = { canal: "instagram", titulo: "", texto: "Un caption", imagenSrc: "https://w/a.jpg", videoUrl: null, formato: "cuadrado", imagenes: ["https://w/a.jpg", "https://w/b.jpg", "https://w/c.jpg"] };

describe("VistaPrevia con carrusel", () => {
  it("pasa de foto con las flechas y los puntitos, con contador", async () => {
    const u = userEvent.setup();
    render(<VistaPrevia d={BASE} />);
    expect(screen.getByText("1/3")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Foto 1 de 3" })).toHaveAttribute("src", "https://w/a.jpg");
    expect(screen.getByRole("button", { name: "Foto anterior" })).toBeDisabled();
    await u.click(screen.getByRole("button", { name: "Foto siguiente" }));
    expect(screen.getByText("2/3")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Foto 2 de 3" })).toHaveAttribute("src", "https://w/b.jpg");
    await u.click(screen.getByRole("button", { name: "Ir a la foto 3" }));
    expect(screen.getByText("3/3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Foto siguiente" })).toBeDisabled();
    await u.click(screen.getByRole("button", { name: "Foto anterior" }));
    expect(screen.getByText("2/3")).toBeInTheDocument();
  });

  it("también en Facebook, y sin frase encima", () => {
    render(<VistaPrevia d={{ ...BASE, canal: "facebook", textoImagen: "no va" }} />);
    expect(screen.getByText("1/3")).toBeInTheDocument();
    expect(screen.queryByAltText(/Foto con la frase/)).not.toBeInTheDocument();
  });

  it("con una sola foto se ve como foto, sin carrusel", () => {
    render(<VistaPrevia d={{ ...BASE, imagenes: ["https://w/a.jpg"] }} />);
    expect(screen.queryByRole("button", { name: "Foto siguiente" })).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Foto de la pieza" })).toBeInTheDocument();
  });
});
