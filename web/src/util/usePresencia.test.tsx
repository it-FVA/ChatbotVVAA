// (5/11) El latido: cada 20 s, no late con la pestaña oculta, vuelve a latir al volver, y avisa que salió al desmontar.
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { instalarApi } from "../pruebas/apiSimulada";
import { LATIDO_MS, usePresencia } from "./usePresencia";

function pestana(oculta: boolean) {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => oculta });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("usePresencia", () => {
  afterEach(() => {
    vi.useRealTimers();
    pestana(false);
  });

  it("late al entrar y cada 20 s, calla con la pestaña oculta, late al volver y manda DELETE al salir", async () => {
    vi.useFakeTimers();
    const api = instalarApi({
      "POST /presencia/recorte/r1": { presentes: [{ usuario: "pato", nombre: "Pato", modo: "mira", hace_seg: 3 }] },
      "DELETE /presencia/recorte/r1": { ok: true },
    });
    const { result, unmount } = renderHook(() => usePresencia("recorte", "r1", "edita"));
    await act(async () => {});
    expect(api.de("POST", "/presencia/recorte/r1")).toHaveLength(1);
    expect(result.current.map((p) => p.nombre)).toEqual(["Pato"]);
    await act(async () => {
      vi.advanceTimersByTime(LATIDO_MS);
    });
    expect(api.de("POST", "/presencia/recorte/r1")).toHaveLength(2);
    act(() => pestana(true));
    await act(async () => {
      vi.advanceTimersByTime(LATIDO_MS * 3);
    });
    expect(api.de("POST", "/presencia/recorte/r1")).toHaveLength(2); // oculta: no late
    await act(async () => pestana(false));
    expect(api.de("POST", "/presencia/recorte/r1")).toHaveLength(3); // al volver, late enseguida
    unmount();
    expect(api.de("DELETE", "/presencia/recorte/r1")).toHaveLength(1);
  });

  it("sin id no late ni avisa", async () => {
    const api = instalarApi({});
    const { unmount } = renderHook(() => usePresencia("pieza", null, "edita"));
    unmount();
    expect(api.llamadas).toHaveLength(0);
  });
});
