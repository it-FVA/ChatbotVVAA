// La tarjeta «Mañana» de Frase del día: qué sale mañana y por dónde, para quien aprueba y para quien solo ve
// (revisión 3/11, 5.3 punto 19).
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CanalManana, Frase, Resumen } from "../../../apiFrases";
import { MananaCard } from "./MananaCard";

const FRASE: Frase = {
  id: "f1",
  texto: "La gratitud es la llave de la alegría",
  autor: "Anónimo",
  fecha: "2026-11-04",
  estado: "programada",
  estado_texto: "programada",
  validada: true,
  imagen_url: null,
  publicacion_id: null,
  fuente: null,
  tema: null,
  orden: 1,
  ultima_publicada: null,
  veces_publicada: 0,
  repetida: false,
  cerrada: false,
};

const CANALES: CanalManana[] = [
  { canal: "facebook", nombre: "Facebook (página)", prendido: true, modo: "real", pieza: { id: "p1", estado: "pendiente", fecha_programada: "2026-11-04T10:00:00+00:00" } },
  { canal: "instagram", nombre: "Instagram (posteo)", prendido: false, modo: "real", pieza: null },
  { canal: "whatsapp", nombre: "WhatsApp (grupo)", prendido: true, modo: "simulado", pieza: null },
  { canal: "mail", nombre: "Mail por Perfit", prendido: true, modo: "apagado", pieza: null },
];

function resumen(extra: Partial<Resumen> = {}, manana: Partial<NonNullable<Resumen["manana"]>> = {}): Resumen {
  return {
    disponible: true,
    admin: true,
    aprueba: true,
    conteos: {},
    activa: true,
    hora: "07:00",
    avisos: [],
    manana: { fecha: "2026-11-04", fecha_texto: "4 de noviembre", dia: "miércoles", frase: FRASE, en_cola: false, canales: CANALES, ...manana },
    ...extra,
  };
}

function tarjeta(r: Resumen, aprueba = true) {
  const acciones = { onActiva: vi.fn(), onCanales: vi.fn(), onEncolar: vi.fn(), onFrenar: vi.fn(), onVerDia: vi.fn(), onVerMail: vi.fn(), onVerWa: vi.fn(), onProbarMail: vi.fn(), onDetallesMail: vi.fn() };
  render(<MananaCard resumen={r} aprueba={aprueba} ocupado={false} {...acciones} />);
  return acciones;
}

/** La fila de la tabla de canales por el nombre corto que muestra la pantalla. */
function fila(nombreCorto: string) {
  return screen.getByText(nombreCorto).closest("tr") as HTMLElement;
}

describe("Tarjeta Mañana", () => {
  it("muestra el día, la frase y el estado de cada canal", () => {
    tarjeta(resumen());
    expect(screen.getByRole("heading", { name: "Mañana, miércoles 4 de noviembre" })).toBeInTheDocument();
    expect(screen.getByText(/La gratitud es la llave de la alegría/)).toBeInTheDocument();
    // la cola guarda en UTC y la pantalla lo muestra en hora Argentina: 10:00 UTC = 07:00 (el cero del día depende del navegador)
    expect(within(fila("Facebook")).getByText(/^en cola · sale 0?4\/11 07:00$/)).toBeInTheDocument();
    expect(within(fila("Posteo de Instagram")).getByText("apagado", { selector: "td" })).toBeInTheDocument();
    expect(within(fila("WhatsApp")).getByText("se encola en la próxima pasada (sale 07:00)")).toBeInTheDocument();
    expect(within(fila("Mail")).getByText("el canal está apagado en la API")).toBeInTheDocument();
  });

  it("quien aprueba puede encolar mañana y prender o apagar canales", async () => {
    const u = userEvent.setup();
    const a = tarjeta(resumen());
    await u.click(screen.getByRole("button", { name: /Encolar mañana/ }));
    expect(a.onEncolar).toHaveBeenCalledTimes(1);
    // apagar Facebook deja prendidos los otros dos
    await u.click(within(fila("Facebook")).getByRole("checkbox"));
    expect(a.onCanales).toHaveBeenCalledWith(["whatsapp", "mail"]);
    // el mail tiene Ver, Probar y Detalles
    await u.click(within(fila("Mail")).getByRole("button", { name: /Probar/ }));
    expect(a.onProbarMail).toHaveBeenCalledTimes(1);
  });

  it("con la Frase del día apagada no deja encolar", () => {
    tarjeta(resumen({ activa: false }));
    expect(screen.getByRole("button", { name: /Encolar mañana/ })).toBeDisabled();
    expect(screen.getByText(/Apagada: no sale nada por ningún canal/)).toBeInTheDocument();
  });

  it("si ya está en la cola ofrece frenar en vez de encolar", async () => {
    const u = userEvent.setup();
    const a = tarjeta(resumen({}, { en_cola: true }));
    expect(screen.queryByRole("button", { name: /Encolar mañana/ })).not.toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Frenar mañana/ }));
    expect(a.onFrenar).toHaveBeenCalledTimes(1);
  });

  it("quien solo ve no tiene interruptores ni acciones, pero puede pedir un cambio", async () => {
    const u = userEvent.setup();
    const a = tarjeta(resumen({ aprueba: false }), false);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Encolar mañana/ })).not.toBeInTheDocument();
    expect(within(fila("Facebook")).getByText("sí")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Pedir un cambio/ }));
    expect(a.onVerDia).toHaveBeenCalledWith("2026-11-04");
  });

  it("sin frase asignada avisa y no muestra la imagen", () => {
    tarjeta(resumen({}, { frase: null }));
    expect(screen.getByText(/Mañana no tiene frase asignada/)).toBeInTheDocument();
    expect(screen.queryByAltText("Así saldría la imagen de mañana")).not.toBeInTheDocument();
  });
});
