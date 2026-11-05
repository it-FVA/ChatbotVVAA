// (5/11, Franco) La prueba que mantiene viva la ayuda: se renderiza cada pantalla con la API simulada y se compara el DOM con el
// registro (ayuda/registro.ts). Falla en dos casos:
//   1) un paso de la ayuda tiene `id` pero ningún escenario de esa pantalla muestra un elemento data-ayuda="<pantalla>.<id>"
//      (se renombró o se borró el botón, y la guía apuntaría a la nada);
//   2) hay un data-ayuda en el DOM que ningún definirAyuda declara (se agregó el botón pero no se explicó).
// Una pantalla puede tener varios escenarios: lo que solo aparece con datos (las fuentes de una respuesta, las piezas) se cubre con uno que los tenga.
// Quedan afuera de esta prueba las pantallas que no están acá (ver el README): las vigila scripts/verificar-ayuda.mjs, que compara el código.
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../componentes/Toasts";
import { ProyectosProvider } from "../componentes/proyectos/ProyectosContexto";
import { instalarApi, type Manejador } from "../pruebas/apiSimulada";
import { PLANTILLAS_NEWSLETTER } from "../pruebas/plantillasNewsletter";
import { ayudaDe, todasLasAyudas } from "./index";

// Quien mira es un aprobador y administrador: así se ven también Aprobación y Administración.
vi.mock("../App", () => ({
  useSesion: () => ({
    yo: {
      usuario: "ana",
      origen: "prueba",
      idioma: "es",
      rol: { nombre: "admin", aprueba: true, publica: true, admin: true, etiqueta: "Administrador" },
      nombre: "Ana",
      email: "ana@ejemplo.org",
      en_tabla: true,
      tiene_clave: true,
      debe_cambiar_clave: false,
      canales: [{ clave: "facebook", nombre: "Facebook", texto: "Facebook", detalle: "Posteo en Facebook", icono: "megafono", en_disenar: true, formato: "cuadrado", requiere_titulo: false, acepta_aprobacion: true }],
    },
    cargando: false,
    setYo: () => {},
  }),
}));

import Chat from "../paginas/Chat";
import Publicar from "../paginas/Publicar";
import Publicaciones from "../paginas/Publicaciones";
import Recortes from "../paginas/Recortes";
import Newsletter from "../paginas/Newsletter";
import FraseDelDia from "../paginas/frase/FraseDelDia";
import Proyectos from "../paginas/Proyectos";
import Compartidos from "../paginas/Compartidos";
import Aprobacion, { ParaAprobar } from "../paginas/Aprobacion";
import Administracion from "../paginas/admin/Administracion";

const hoy = "2026-11-05T12:00:00+00:00";

const TARJETA = { tag: "Charla", titulo: "La gratitud", texto: "Agradecer cambia la mirada.", autor: "Ana", fuente: "youtube", url: "https://youtu.be/x", doc: "x", inicio_ms: 1000, fin_ms: 9000, pagina: null, ir: "https://youtu.be/x?t=1", citada: true, traduccion: null, recortes: { horizontal: null, vertical: null } };
const PIEZA = { canal: "facebook", fecha: "", hora: "", titulo: "", texto: "Hoy agradezco.", texto_imagen: "Gracias", firma: "", imagen_busqueda: "" };

const PUBLICACION = {
  id: "p1", creado: hoy, canal: "facebook", modo: "simulado", titulo: "Una pieza", texto: "Hoy agradezco.", imagen_url: null, estado: "rechazada", fecha_programada: null, resultado: null,
  estado_texto: "Rechazada", canal_texto: "Facebook", video_url: null, texto_imagen: null, formato: "cuadrado", nota: "Falta el logo", propuesta_por: "ana", aprobada_por: null, aprobada_en: null,
  rechazada_por: "julian", rechazada_en: hoy, cancelada_por: null, plantilla: null, ver_url: null, link_editar: null, error_texto: null, eliminable: true, retomable: true, propio: true,
};

const RECORTE = {
  id: "r1", creado: hoy, video_id: "x", inicio_ms: 0, fin_ms: 9000, formato: "horizontal", titulo: "Un recorte", pedido_por: "ana", estado: "listo", url: "https://ejemplo.org/r1.mp4", error: null, procesado_en: hoy,
  srt: null, edicion: null, nota: null, estilo: null, propio: true, puede_editar: true, puede_borrar: true, compartido: false, puede_compartir: true, regenerando: false, estado_texto: "Listo",
  miniatura: null, duracion_ms: 9000, sin_pausas: null, segmentos_hechos: null,
};

function canal(nombre: string) {
  return {
    nombre, texto_canal: nombre, detalle: `Posteo en ${nombre}`, modo_real: "simulado", modo: "simulado", texto: `${nombre}: simulado.`, a_aprobar: true, acepta_aprobacion: true, requiere_titulo: false,
    formato: "cuadrado", va_a_la_cola: true, configurado: true, aviso_sin_fecha: "Se arma.", aviso_con_fecha: "Se programa para {cuando}.",
  };
}
const OPCIONES_PUBLICAR = {
  canales: { facebook: canal("Facebook") }, publica: true, aprueba: true, rol: "admin", aprobadores: ["ana"], usuario: "ana", logos: ["Ninguno"], logos_url: {}, posiciones_logo: ["Abajo a la derecha"],
  tipografias: ["Raleway"], tipografia_defecto: "Raleway", pesos: ["Normal"], posiciones: ["Centro"], alineaciones: ["Centro"], formatos: { cuadrado: [1080, 1080] }, formato_por_canal: { facebook: "cuadrado" },
  firma_defecto: "Vivir Agradecidos", zona: "America/Argentina/Buenos_Aires",
};

const PROYECTO = { id: "c1", nombre: "Campaña", dueno: "ana", permiso: "dueño", color: null, emoji: null, descripcion: null, padre_id: null, n_items: 0, creado: hoy, actualizado: hoy };

interface Escenario {
  pantalla: string;
  ruta: string;
  rutas: Record<string, Manejador>;
  /** Cómo se monta (por defecto, la pantalla en la ruta). */
  elemento: ReactElement;
  /** Algo que solo existe cuando terminó de cargar. */
  listo: () => Promise<unknown>;
  rutaDeLaPantalla?: string;
}

// quien pide cambios (aprueba: false) ve siempre el panel «Mis solicitudes»
const RUTAS_FRASE = {
  "GET /frases/resumen": { disponible: true, admin: false, aprueba: false, conteos: {}, activa: true, hoy: "2026-11-05", hora: "07:00", canales: [], avisos: [], manana: { fecha: "2026-11-06", fecha_texto: "6 de noviembre", dia: "viernes", frase: null, en_cola: false, canales: [] } },
  "GET /frases/proximas": [],
  "GET /frases/mes/2026/11": { anio: 2026, mes: 11, dias: 30, hoy: "2026-11-05", primer_dia_semana: 6, frases: {} },
  "GET /frases/solicitudes": { aprueba: false, pendientes: [], resueltas: [] },
};

const PROYECTOS_VACIOS = { "GET /proyectos": { proyectos: [], ubicaciones: {} }, "GET /conversaciones": [] };

const ESCENARIOS: Escenario[] = [
  { pantalla: "chat", ruta: "/chat", rutaDeLaPantalla: "/chat", rutas: PROYECTOS_VACIOS, elemento: <Chat />, listo: () => screen.findByRole("textbox") },
  {
    pantalla: "chat",
    ruta: "/chat/c1",
    rutaDeLaPantalla: "/chat/:id",
    rutas: {
      ...PROYECTOS_VACIOS,
      "GET /conversaciones/c1": { id: "c1", titulo: "Gratitud", mensajes: [{ role: "user", content: "¿Qué dice sobre la gratitud?" }, { role: "assistant", content: "Dice mucho.", tarjetas: [TARJETA], pieza: PIEZA }] },
      "GET /conversaciones/c1/recortes": [],
      "GET /publicaciones/modos": { modos: {}, todos: [] },
    },
    elemento: <Chat />,
    listo: () => screen.findByText("Dice mucho."),
  },
  { pantalla: "disenar", ruta: "/publicar?canal=facebook", rutaDeLaPantalla: "/publicar", rutas: { "GET /publicar/opciones": OPCIONES_PUBLICAR, "GET /banco": [] }, elemento: <Publicar />, listo: () => screen.findByRole("heading", { level: 1, name: "Diseñar · Facebook" }) },
  { pantalla: "disenar", ruta: "/publicar", rutaDeLaPantalla: "/publicar", rutas: { "GET /publicar/opciones": OPCIONES_PUBLICAR, "GET /banco": [] }, elemento: <Publicar />, listo: () => screen.findByText("Canal") },
  { pantalla: "publicaciones", ruta: "/publicaciones", rutas: { ...PROYECTOS_VACIOS, "GET /publicaciones": { piezas: [], solapas: {} }, "GET /publicaciones/modos": { modos: {}, todos: [] } }, elemento: <Publicaciones />, listo: () => screen.findByText("Todavía no mandaste ninguna pieza") },
  { pantalla: "publicaciones", ruta: "/publicaciones", rutas: { ...PROYECTOS_VACIOS, "GET /publicaciones": { piezas: [PUBLICACION], solapas: { Rechazadas: [PUBLICACION] } }, "GET /publicaciones/modos": { modos: {}, todos: [] } }, elemento: <Publicaciones />, listo: () => screen.findByText("Una pieza") },
  { pantalla: "recortes", ruta: "/recortes", rutas: { ...PROYECTOS_VACIOS, "GET /recortes": [RECORTE] }, elemento: <Recortes />, listo: () => screen.findByText("Un recorte") },
  {
    pantalla: "newsletter",
    ruta: "/newsletter",
    rutas: { "GET /newsletter/plantillas": PLANTILLAS_NEWSLETTER, "GET /banco": [], "POST /newsletter/html": { html: "<html></html>", titulo: "Newsletter" } },
    elemento: <Newsletter />,
    listo: () => screen.findByRole("button", { name: /Enviar a aprobación/ }),
  },
  { pantalla: "frase-del-dia", ruta: "/frase-del-dia", rutas: RUTAS_FRASE, elemento: <FraseDelDia />, listo: () => screen.findByRole("heading", { level: 1, name: "Frase del día" }) },
  { pantalla: "proyectos", ruta: "/proyectos", rutas: { "GET /proyectos": { proyectos: [PROYECTO], ubicaciones: {} } }, elemento: <Proyectos />, listo: () => screen.findByRole("button", { name: /Nueva carpeta/ }) },
  {
    pantalla: "proyectos",
    ruta: "/proyectos/c1",
    rutaDeLaPantalla: "/proyectos/:id",
    rutas: {
      "GET /proyectos": { proyectos: [PROYECTO], ubicaciones: {} },
      "GET /proyectos/c1": { proyecto: PROYECTO, permiso: "dueño", migas: [], subcarpetas: [], items: [], compartido_con: [] },
    },
    elemento: <Proyectos />,
    listo: () => screen.findAllByRole("button", { name: "Agregar" }),
  },
  { pantalla: "compartidos", ruta: "/compartidos", rutas: { ...PROYECTOS_VACIOS, "GET /compartidos-conmigo": { proyectos: [{ ...PROYECTO, compartido_por: "julian", permiso: "ver" }], conversaciones: [] } }, elemento: <Compartidos />, listo: () => screen.findByText("Campaña") },
  { pantalla: "aprobacion", ruta: "/aprobacion", rutas: { "GET /aprobacion/para-aprobar": { piezas: [{ ...PUBLICACION, estado: "a_aprobar", fecha_sugerida: "2026-11-06", hora_sugerida: "09:00" }], modos: { facebook: "simulado" } } }, elemento: <Aprobacion />, listo: () => screen.findByRole("button", { name: /Aprobar y programar/ }) },
  { pantalla: "administracion", ruta: "/administracion", rutas: { "GET /admin/salud": { estado: "sin_dato" } }, elemento: <Administracion />, listo: () => screen.findByRole("heading", { level: 1, name: "Administración" }) },
];

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  Element.prototype.scrollIntoView = () => {};
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, onchange: null, dispatchEvent: () => false }));
});

function montar(e: Escenario) {
  const pantalla = e.elemento;
  render(
    <MemoryRouter initialEntries={[e.ruta]}>
      <ToastProvider>
        <ProyectosProvider>
          <Routes>
            <Route path="/aprobacion" element={pantalla}>
              <Route index element={<ParaAprobar />} />
            </Route>
            <Route path={e.rutaDeLaPantalla ?? e.ruta.split("?")[0]} element={pantalla} />
            <Route path="*" element={pantalla} />
          </Routes>
        </ProyectosProvider>
      </ToastProvider>
    </MemoryRouter>,
  );
}

const presentes = () => new Set([...document.querySelectorAll("[data-ayuda]")].map((el) => el.getAttribute("data-ayuda")!));

describe("la ayuda coincide con las pantallas", () => {
  const declarados = new Set<string>();
  for (const [pantalla, d] of todasLasAyudas()) for (const p of d.pasos) if (p.id) declarados.add(`${pantalla}.${p.id}`);

  const vistos = new Map<string, Set<string>>(); // pantalla → data-ayuda que apareció en algún escenario

  for (const e of ESCENARIOS) {
    it(`${e.pantalla} (${e.ruta}): todo lo que tiene data-ayuda está explicado`, async () => {
      instalarApi(e.rutas);
      montar(e);
      await e.listo();
      await waitFor(() => expect(presentes().size).toBeGreaterThan(0));
      const en = presentes();
      const mios = vistos.get(e.pantalla) ?? new Set<string>();
      en.forEach((v) => mios.add(v));
      vistos.set(e.pantalla, mios);
      const sinDeclarar = [...en].filter((v) => !declarados.has(v));
      expect(sinDeclarar, `data-ayuda sin explicar en el registro: ${sinDeclarar.join(", ")}`).toEqual([]);
    });
  }

  it("todo paso con id apunta a un elemento que alguna pantalla muestra", () => {
    const faltan: string[] = [];
    for (const [pantalla, d] of todasLasAyudas()) {
      expect(ayudaDe(pantalla)).toBeDefined();
      for (const p of d.pasos) if (p.id && !vistos.get(pantalla)?.has(`${pantalla}.${p.id}`)) faltan.push(`${pantalla}.${p.id}`);
    }
    expect(faltan, `pasos de la ayuda sin elemento en la pantalla: ${faltan.join(", ")}`).toEqual([]);
  });
});
