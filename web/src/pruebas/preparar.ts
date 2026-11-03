// Preparación común de las pruebas de la web: matchers de jest-dom, limpieza del DOM entre pruebas y lo que jsdom no trae.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom no implementa estas dos: las usa la vista previa (blob de la foto compuesta) y Publicar al enviar.
URL.createObjectURL = () => "blob:prueba";
URL.revokeObjectURL = () => {};
window.scrollTo = () => {};
